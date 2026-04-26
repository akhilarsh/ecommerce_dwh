"""
BigQuery data loader implementation.

Uses load jobs (free, fast, batched) for all sizes via NEWLINE_DELIMITED_JSON
source format. Per-row INSERT is intentionally not supported — BigQuery rate
limits and round-trip costs make it impractical for fact-table sized loads
(Phase 11 / 12 lesson).

Why JSON source format and not Parquet (`load_table_from_dataframe`)?
The Parquet upload path rejects BigQuery's JSON column type with "Unsupported
field type: JSON". JSON source format handles every BigQuery type natively:
JSON columns take native JSON values, GEOGRAPHY takes WKT strings, BYTES
takes base64, NUMERIC takes string-encoded decimals, DATETIME takes ISO 8601.

Special-type handling:
    home_location, geo_location  (WKT text)  -> uploaded as STRING with the
        target column typed as GEOGRAPHY in the explicit schema. BigQuery
        auto-parses WKT on load. (Decision (B) from phase12_bigquery.md.)
    customer_preferences, event_properties,
        order_tags, shipment_metadata        (JSON strings) -> parsed to dict
        before serializing, column typed JSON in the schema.
    raw_payload                  (base64 ASCII) -> already base64; passed
        through as STRING in the JSON line, column typed BYTES in the schema.
"""

import base64
import io
import json
import time
from datetime import date, datetime, time as dt_time
from decimal import Decimal
from pathlib import Path
from typing import Any, Dict, List, Optional

import pandas as pd

from src.connectors.bigquery_connector import BigQueryConnector
from src.data_loaders.base_loader import (
    BaseDataLoader,
    LoaderConfig,
    LoadMethod,
    LoadResult,
)
from src.utils.logger import get_logger

logger = get_logger("loader.bigquery")


# Columns whose Snowflake / generator representation needs translation
# before being uploaded into BigQuery. Mapping is column_name -> bq_type.
# BigQuery infers most other columns from the DataFrame dtype.
SPECIAL_COLUMN_TYPES: Dict[str, str] = {
    # GEOGRAPHY columns — WKT strings auto-parsed on load
    "home_location": "GEOGRAPHY",
    "geo_location": "GEOGRAPHY",
    # JSON columns — JSON strings parsed on load
    "customer_preferences": "JSON",
    "event_properties": "JSON",
    "order_tags": "JSON",
    "shipment_metadata": "JSON",
    # BYTES columns — base64 ASCII -> bytes before load
    "raw_payload": "BYTES",
}


class BigQueryLoader(BaseDataLoader):
    """
    BigQuery-specific data loader using load jobs.

    Usage:
        with BigQueryConnector() as connector:
            loader = BigQueryLoader(connector)
            result = loader.load_dataframe(df, "dim_customers")
    """

    def __init__(
        self,
        connector: BigQueryConnector,
        config: Optional[LoaderConfig] = None,
    ):
        super().__init__(config)
        self.connector = connector

        if not self.config.database:
            self.config.database = connector.project
        if not self.config.schema:
            self.config.schema = connector.dataset

    @property
    def platform_name(self) -> str:
        return "bigquery"

    def _qualified(self, table_name: str) -> str:
        return f"{self.config.database}.{self.config.schema}.{table_name}"

    def _build_job_schema(self, df: pd.DataFrame, table_name: str):
        """
        Build an explicit BigQuery schema covering every column in `df`.

        DataFrame autodetect maps pandas float64 to FLOAT64, which conflicts
        with NUMERIC(p,s) target columns ("Provided Schema does not match
        Table"). To avoid that and any other dtype-vs-target mismatches, we
        fetch the target table's actual schema from BigQuery and use it as
        the load job's schema.

        Falls back to a special-columns-only schema if the table doesn't
        exist yet (the load_table_from_dataframe call will then create it
        with autodetected types — useful for ad-hoc DataFrame loads).
        """
        from google.cloud import bigquery
        from google.cloud.exceptions import NotFound

        if self.connector.client is None:
            return []

        table_ref = self._qualified(table_name)
        try:
            table = self.connector.client.get_table(table_ref)
        except NotFound:
            self._logger.debug(
                f"{table_name} does not exist; falling back to special-columns "
                "schema and letting BigQuery autodetect the rest"
            )
            schema = []
            for col in df.columns:
                bq_type = SPECIAL_COLUMN_TYPES.get(col)
                if bq_type:
                    schema.append(bigquery.SchemaField(col, bq_type, mode="NULLABLE"))
            return schema

        # Reuse the table's existing schema, restricted to the DataFrame's columns.
        df_cols = set(df.columns)
        schema = [field for field in table.schema if field.name in df_cols]
        return schema

    def _df_to_jsonl(self, df: pd.DataFrame, schema) -> bytes:
        """
        Serialize a DataFrame to UTF-8 NEWLINE_DELIMITED_JSON bytes for upload.

        Per-type rules (driven by the target table's BigQuery schema):
            JSON      -> parse the DataFrame's JSON-string into a dict/list
            NUMERIC   -> stringify so BigQuery preserves precision
            BIGNUMERIC-> stringify
            BYTES     -> already base64 ASCII strings
            GEOGRAPHY -> WKT strings pass through
            DATETIME  -> ISO 8601 with 'T' separator, no timezone
            TIMESTAMP -> ISO 8601 with timezone (assumed UTC)
            DATE      -> YYYY-MM-DD
            TIME      -> HH:MM:SS[.ffffff]
            BOOL      -> true / false
            INT64     -> int
            FLOAT64   -> float

        NaN / None / NaT collapse to JSON null. The schema is required so we
        know how to format each column; columns missing from the schema fall
        back to JSON's default serialization.
        """
        type_by_name = {f.name: f.field_type for f in schema} if schema else {}

        buf = io.BytesIO()
        for row in df.to_dict(orient="records"):
            doc: Dict[str, Any] = {}
            for col, val in row.items():
                doc[col] = _to_json_value(val, type_by_name.get(col))
            buf.write(json.dumps(doc, default=str).encode("utf-8"))
            buf.write(b"\n")
        return buf.getvalue()

    def load_dataframe(
        self,
        df: pd.DataFrame,
        table_name: str,
        **kwargs,
    ) -> LoadResult:
        start_time = time.time()
        started_at = datetime.now()

        validation_errors = self._validate_dataframe(df, table_name)
        if validation_errors:
            return LoadResult(
                table_name=table_name,
                rows_loaded=0,
                success=False,
                method=LoadMethod.DATAFRAME,
                errors=validation_errors,
                started_at=started_at,
                completed_at=datetime.now(),
            )

        method = LoadMethod.DATAFRAME

        try:
            if self.config.truncate_before_load:
                self.truncate_table(table_name)

            result = self._load_via_load_job(df, table_name, method)

            duration = time.time() - start_time
            result.duration_seconds = duration
            result.started_at = started_at
            result.completed_at = datetime.now()

            if self.config.validate_after_load and result.success:
                actual_count = self.get_row_count(table_name)
                if not self.config.truncate_before_load:
                    self._logger.debug(
                        f"{table_name}: {actual_count} total rows after load"
                    )
                elif actual_count != result.rows_loaded:
                    result.warnings.append(
                        f"Row count mismatch: expected {result.rows_loaded}, "
                        f"got {actual_count}"
                    )

            self._logger.info(str(result))
            return result

        except Exception as e:
            duration = time.time() - start_time
            self._logger.error(f"Failed to load {table_name}: {e}")
            return LoadResult(
                table_name=table_name,
                rows_loaded=0,
                success=False,
                method=method,
                duration_seconds=duration,
                errors=[str(e)],
                started_at=started_at,
                completed_at=datetime.now(),
            )

    def _load_via_load_job(
        self,
        df: pd.DataFrame,
        table_name: str,
        method: LoadMethod,
    ) -> LoadResult:
        """
        Run a single load job for the entire DataFrame.

        Uses WRITE_APPEND so callers control truncation explicitly via
        config.truncate_before_load (truncate_table is invoked separately
        when set).
        """
        from google.cloud import bigquery

        if self.connector.client is None:
            raise RuntimeError("BigQuery client is not connected")

        explicit_schema = self._build_job_schema(df, table_name)

        if not explicit_schema:
            raise RuntimeError(
                f"Cannot build schema for {table_name}: target table must exist "
                "before loading via the JSON path"
            )

        job_config = bigquery.LoadJobConfig(
            source_format=bigquery.SourceFormat.NEWLINE_DELIMITED_JSON,
            write_disposition=bigquery.WriteDisposition.WRITE_APPEND,
            schema=explicit_schema,
        )

        qualified = self._qualified(table_name)
        self._logger.debug(
            f"Loading {len(df)} rows to {qualified} via NDJSON load job "
            f"(schema_fields={len(explicit_schema)})"
        )

        ndjson_bytes = self._df_to_jsonl(df, explicit_schema)

        job = self.connector.client.load_table_from_file(
            io.BytesIO(ndjson_bytes),
            qualified,
            job_config=job_config,
            location=self.connector.location,
        )
        job.result()  # blocks until the load completes

        rows_loaded = job.output_rows or len(df)

        return LoadResult(
            table_name=table_name,
            rows_loaded=rows_loaded,
            success=True,
            method=method,
        )

    def load_csv(
        self,
        filepath: Path,
        table_name: str,
        **kwargs,
    ) -> LoadResult:
        start_time = time.time()
        started_at = datetime.now()
        filepath = Path(filepath)

        if not filepath.exists():
            return LoadResult(
                table_name=table_name,
                rows_loaded=0,
                success=False,
                method=LoadMethod.STAGED,
                errors=[f"File not found: {filepath}"],
                started_at=started_at,
                completed_at=datetime.now(),
            )

        try:
            df = pd.read_csv(filepath)
            result = self.load_dataframe(df, table_name, **kwargs)
            result.started_at = started_at
            result.completed_at = datetime.now()
            result.duration_seconds = time.time() - start_time
            return result

        except Exception as e:
            duration = time.time() - start_time
            self._logger.error(f"Failed to load {table_name} from CSV: {e}")
            return LoadResult(
                table_name=table_name,
                rows_loaded=0,
                success=False,
                method=LoadMethod.STAGED,
                duration_seconds=duration,
                errors=[str(e)],
                started_at=started_at,
                completed_at=datetime.now(),
            )

    def truncate_table(self, table_name: str) -> None:
        qualified = self._qualified(table_name)
        sql = f"TRUNCATE TABLE `{qualified}`"

        self._logger.debug(f"Truncating {qualified}")
        self.connector.execute_query(sql)
        self._logger.info(f"Truncated {table_name}")

    def get_row_count(self, table_name: str) -> int:
        qualified = self._qualified(table_name)
        sql = f"SELECT COUNT(*) FROM `{qualified}`"

        result = self.connector.execute_query(sql)
        return result[0][0] if result else 0

    def table_exists(self, table_name: str) -> bool:
        return self.connector.table_exists(table_name, schema=self.config.schema)


def _is_null(v: Any) -> bool:
    """True if value should serialize to JSON null."""
    if v is None:
        return True
    if isinstance(v, float) and pd.isna(v):
        return True
    # pandas NaT for datetimes; pd.isna also covers it but check defensively.
    try:
        if pd.isna(v):
            return True
    except (TypeError, ValueError):
        pass
    return False


def _to_json_value(v: Any, bq_type: Optional[str]) -> Any:
    """
    Convert a Python / pandas value into the JSON representation BigQuery
    expects for the given target column type.

    bq_type is the BigQuery field type from the destination schema. The
    schema API returns legacy aliases (INTEGER / BOOLEAN / FLOAT) rather
    than the standard SQL forms (INT64 / BOOL / FLOAT64); normalize so
    callers can use either spelling. When None, we fall back to a sensible
    default that json.dumps can handle.
    """
    if _is_null(v):
        return None

    # Normalize legacy field-type aliases returned by the schema API.
    if bq_type == "INTEGER":
        bq_type = "INT64"
    elif bq_type == "BOOLEAN":
        bq_type = "BOOL"
    elif bq_type == "FLOAT":
        bq_type = "FLOAT64"

    if bq_type == "JSON":
        # Generators emit JSON-encoded strings; parse so BigQuery sees a
        # native JSON value rather than a quoted string.
        if isinstance(v, (dict, list)):
            return v
        if isinstance(v, str):
            try:
                return json.loads(v)
            except json.JSONDecodeError:
                return v
        return v

    if bq_type in ("NUMERIC", "BIGNUMERIC"):
        # Stringify to preserve precision (json.dumps would otherwise
        # produce float64-rounded values).
        if isinstance(v, Decimal):
            return str(v)
        return str(v)

    if bq_type == "BYTES":
        # Base64 ASCII string — BigQuery's JSON loader expects bytes columns
        # encoded as base64 strings.
        if isinstance(v, (bytes, bytearray)):
            return base64.b64encode(bytes(v)).decode("ascii")
        return str(v)

    if bq_type == "DATETIME":
        if isinstance(v, pd.Timestamp):
            return v.to_pydatetime().strftime("%Y-%m-%dT%H:%M:%S.%f")
        if isinstance(v, datetime):
            return v.strftime("%Y-%m-%dT%H:%M:%S.%f")
        return str(v)

    if bq_type == "TIMESTAMP":
        if isinstance(v, pd.Timestamp):
            return v.to_pydatetime().isoformat()
        if isinstance(v, datetime):
            return v.isoformat()
        return str(v)

    if bq_type == "DATE":
        if isinstance(v, (datetime, pd.Timestamp)):
            return v.strftime("%Y-%m-%d")
        if isinstance(v, date):
            return v.isoformat()
        return str(v)

    if bq_type == "TIME":
        if isinstance(v, dt_time):
            return v.isoformat()
        return str(v)

    if bq_type == "BOOL":
        return bool(v)

    if bq_type == "INT64":
        # numpy int / pandas int / Python int all round-trip via int().
        try:
            return int(v)
        except (TypeError, ValueError):
            return v

    if bq_type == "FLOAT64":
        try:
            return float(v)
        except (TypeError, ValueError):
            return v

    # GEOGRAPHY (WKT string), STRING, and unknown types pass through.
    # numpy scalars need .item() to become JSON-serializable.
    if hasattr(v, "item") and not isinstance(v, (str, bytes, bytearray)):
        try:
            return v.item()
        except (AttributeError, ValueError):
            pass
    return v
