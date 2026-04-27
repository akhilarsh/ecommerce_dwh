"""
Amazon Redshift data loader implementation.

Two strategies, picked at runtime per Phase 13 Q2 decision:

1. **executemany INSERT** — small loads (< 5K rows) and the fallback when
   no S3 staging bucket is configured. Slow at fact-table scale but works
   without any AWS infrastructure.

2. **S3-staged COPY** — preferred for any load >= 5K rows when
   `REDSHIFT_S3_STAGING_BUCKET` is set. DataFrame is serialized to gzipped
   newline-delimited JSON, uploaded to
   `s3://<bucket>/<database>/<schema>/<table>/<utc_iso>-<uuid>.json.gz`
   (mirrors BigQuery's `<project>/<dataset>/<table>` layout), then loaded
   with `COPY <table> FROM 's3://...' IAM_ROLE '<arn>' FORMAT AS JSON 'auto'
   GZIP REGION '<region>'`. Object is deleted on success; left in place on
   failure for debugging.

Per-type encoding (NDJSON path) reuses the BigQuery loader's rules:
    SUPER       -> JSON value (parsed dict/list, not string)
    NUMERIC     -> string  (preserves precision)
    VARBYTE     -> hex     (Redshift COPY accepts hex-encoded bytes)
    GEOGRAPHY   -> WKT string passthrough (auto-cast on COPY)
    TIMESTAMP   -> ISO 8601
    DATE        -> YYYY-MM-DD

Per-type wrapping (INSERT path) follows the same logic but wraps SUPER and
GEOGRAPHY columns at the SQL level: `JSON_PARSE(%s)` and `ST_GeogFromText(%s)`
respectively. VARBYTE columns bind raw bytes via the driver.
"""

import base64
import gzip
import io
import json
import time
import uuid
from datetime import date, datetime, time as dt_time
from decimal import Decimal
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd

from src.connectors.redshift_connector import RedshiftConnector
from src.data_loaders.base_loader import (
    BaseDataLoader,
    LoaderConfig,
    LoadMethod,
    LoadResult,
)
from src.utils.logger import get_logger

logger = get_logger("loader.redshift")


# Threshold below which we keep using INSERT even when COPY is available.
# Set lower than Databricks (10K) because Redshift's leader-node serialisation
# makes INSERT VALUES degrade earlier in practice.
DEFAULT_COPY_THRESHOLD = 5000


# Columns whose Snowflake / generator representation needs translation
# before being uploaded into Redshift. The destination column type drives
# both NDJSON encoding and INSERT wrapping. Reuses the same set as the
# BigQuery loader for cross-platform consistency.
SPECIAL_COLUMN_TYPES: Dict[str, str] = {
    # GEOGRAPHY columns — WKT strings auto-parsed on COPY / ST_GeogFromText on INSERT
    "home_location": "GEOGRAPHY",
    "geo_location": "GEOGRAPHY",
    # SUPER columns — JSON-encoded; loader parses to dict before NDJSON write
    "customer_preferences": "SUPER",
    "event_properties": "SUPER",
    "order_tags": "SUPER",
    "shipment_metadata": "SUPER",
    # VARBYTE columns — base64 ASCII -> hex / bytes
    "raw_payload": "VARBYTE",
}


class RedshiftLoader(BaseDataLoader):
    """
    Redshift-specific data loader with INSERT-or-COPY routing.

    Usage:
        with RedshiftConnector() as connector:
            loader = RedshiftLoader(connector)
            result = loader.load_dataframe(df, "dim_customers")
    """

    def __init__(
        self,
        connector: RedshiftConnector,
        config: Optional[LoaderConfig] = None,
    ):
        super().__init__(config)
        self.connector = connector

        if not self.config.database:
            self.config.database = connector.database
        if not self.config.schema:
            self.config.schema = connector.schema or "ecommerce_dwh"

        import os

        self.staging_bucket = os.getenv("REDSHIFT_S3_STAGING_BUCKET")
        self.copy_iam_role = os.getenv("REDSHIFT_COPY_IAM_ROLE")
        self.aws_region = os.getenv("AWS_REGION", "us-east-1")
        self.copy_threshold = int(
            os.getenv("REDSHIFT_COPY_THRESHOLD", str(DEFAULT_COPY_THRESHOLD))
        )
        # Explicit override: REDSHIFT_LOADER_MODE = "insert" forces INSERT
        # path even when COPY is otherwise available.
        self.forced_mode = (os.getenv("REDSHIFT_LOADER_MODE", "") or "").lower().strip()

        # Cached destination-table schemas keyed by table_name. Populated
        # lazily via _get_table_columns().
        self._schema_cache: Dict[str, List[Tuple[str, str]]] = {}
        self._s3_client = None

    @property
    def platform_name(self) -> str:
        return "redshift"

    @property
    def copy_available(self) -> bool:
        """COPY mode is available when a staging bucket and IAM role are set."""
        return bool(self.staging_bucket and self.copy_iam_role)

    def _get_s3_client(self):
        if self._s3_client is None:
            import boto3

            self._s3_client = boto3.client("s3", region_name=self.aws_region)
        return self._s3_client

    def _qualified(self, table_name: str) -> str:
        return f"{self.config.schema}.{table_name}"

    def _select_strategy(self, row_count: int) -> str:
        """Return 'copy' or 'insert' for the given row count."""
        if self.forced_mode == "insert":
            return "insert"
        if self.forced_mode == "copy":
            if not self.copy_available:
                raise RuntimeError(
                    "REDSHIFT_LOADER_MODE=copy but REDSHIFT_S3_STAGING_BUCKET / "
                    "REDSHIFT_COPY_IAM_ROLE are not set."
                )
            return "copy"
        if self.copy_available and row_count >= self.copy_threshold:
            return "copy"
        return "insert"

    def _get_table_columns(self, table_name: str) -> List[Tuple[str, str]]:
        """Fetch (column_name, data_type) tuples from information_schema."""
        if table_name in self._schema_cache:
            return self._schema_cache[table_name]

        query = """
            SELECT column_name, data_type
            FROM information_schema.columns
            WHERE table_schema = %s AND table_name = %s
            ORDER BY ordinal_position
        """
        rows = self.connector.execute_query(
            query, (self.config.schema, table_name)
        )
        cols = [(r[0], r[1].upper()) for r in (rows or [])]
        self._schema_cache[table_name] = cols
        return cols

    def _resolve_column_types(
        self, df: pd.DataFrame, table_name: str
    ) -> Dict[str, str]:
        """
        Build a mapping of column_name -> normalized type label used for
        encoding / SQL wrapping. Falls back to SPECIAL_COLUMN_TYPES when the
        target table doesn't exist yet (e.g. ad-hoc loads).
        """
        type_map: Dict[str, str] = {}
        try:
            for col, dt in self._get_table_columns(table_name):
                type_map[col] = dt
        except Exception as e:
            self._logger.debug(
                f"Could not introspect {table_name}: {e}. Falling back to "
                f"SPECIAL_COLUMN_TYPES."
            )

        for col in df.columns:
            if col not in type_map and col in SPECIAL_COLUMN_TYPES:
                type_map[col] = SPECIAL_COLUMN_TYPES[col]
        return type_map

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

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

        strategy = self._select_strategy(len(df))
        method = LoadMethod.STAGED if strategy == "copy" else LoadMethod.DATAFRAME

        try:
            if self.config.truncate_before_load:
                self.truncate_table(table_name)

            if strategy == "copy":
                result = self._load_via_copy(df, table_name)
            else:
                result = self._load_via_executemany(df, table_name)

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
            try:
                self.connector.rollback()
            except Exception:
                pass
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
        sql = f"TRUNCATE TABLE {self._qualified(table_name)}"
        self._logger.debug(f"Truncating {table_name}")
        self.connector.execute_query(sql)
        self.connector.commit()
        self._logger.info(f"Truncated {table_name}")

    def get_row_count(self, table_name: str) -> int:
        sql = f"SELECT COUNT(*) FROM {self._qualified(table_name)}"
        result = self.connector.execute_query(sql)
        return result[0][0] if result else 0

    def table_exists(self, table_name: str) -> bool:
        return self.connector.table_exists(table_name, schema=self.config.schema)

    # ------------------------------------------------------------------
    # INSERT path (executemany)
    # ------------------------------------------------------------------

    def _load_via_executemany(
        self,
        df: pd.DataFrame,
        table_name: str,
    ) -> LoadResult:
        """
        Multi-row INSERT path.

        We build ONE statement per chunk with N parenthesized VALUES rows
        (`INSERT ... VALUES (...), (...), (...)`), not N statements via
        cursor.executemany. The executemany approach issues one Bind/Execute
        message per row at the wire level — Redshift's leader-node serialization
        makes that ~3 rows/sec from a remote client. Multi-row VALUES collapses
        N rows into a single round-trip and gets ~100-500x more throughput.

        Chunk size is tuned to stay under Redshift's 32767-parameter limit:
        chunk = min(batch_size, floor(32767 / num_columns)).
        """
        type_map = self._resolve_column_types(df, table_name)
        qualified = self._qualified(table_name)
        col_list = list(df.columns)
        num_cols = len(col_list)

        # Per-column placeholder, with SQL-level wrappers for SUPER / GEOGRAPHY.
        per_row_placeholders: List[str] = []
        for col in col_list:
            t = type_map.get(col, "")
            if t == "SUPER":
                per_row_placeholders.append("JSON_PARSE(%s)")
            elif t == "GEOGRAPHY":
                per_row_placeholders.append("ST_GeogFromText(%s)")
            else:
                per_row_placeholders.append("%s")

        column_list_sql = ", ".join(col_list)
        single_row_template = "(" + ", ".join(per_row_placeholders) + ")"

        rows = [
            tuple(_to_insert_value(v, type_map.get(c)) for c, v in zip(col_list, row))
            for row in df.itertuples(index=False, name=None)
        ]

        # Cap chunk size by both batch_size and the parameter limit. Leave a
        # small headroom (use 32000 instead of 32767) for query-text bytes.
        param_limit_chunk = max(1, 32000 // max(1, num_cols))
        batch = min(max(1, self.config.batch_size), param_limit_chunk)

        self._logger.debug(
            f"Loading {len(df)} rows to {qualified} via multi-row INSERT "
            f"(chunk={batch}, cols={num_cols})"
        )

        rows_loaded = 0
        for i in range(0, len(rows), batch):
            chunk = rows[i : i + batch]

            values_clause = ", ".join([single_row_template] * len(chunk))
            insert_sql = (
                f"INSERT INTO {qualified} ({column_list_sql}) "
                f"VALUES {values_clause}"
            )

            # Flatten all row tuples into a single positional parameter list.
            flat_params: List[Any] = []
            for row in chunk:
                flat_params.extend(row)

            self.connector.cursor.execute(insert_sql, flat_params)
            rows_loaded += len(chunk)

        self.connector.commit()

        return LoadResult(
            table_name=table_name,
            rows_loaded=rows_loaded,
            success=True,
            method=LoadMethod.DATAFRAME,
        )

    # ------------------------------------------------------------------
    # COPY path (S3 staging)
    # ------------------------------------------------------------------

    def _load_via_copy(
        self,
        df: pd.DataFrame,
        table_name: str,
    ) -> LoadResult:
        if not self.copy_available:
            raise RuntimeError(
                "S3 staging not configured: set REDSHIFT_S3_STAGING_BUCKET "
                "and REDSHIFT_COPY_IAM_ROLE."
            )

        type_map = self._resolve_column_types(df, table_name)
        qualified = self._qualified(table_name)

        ndjson_bytes = _df_to_ndjson(df, type_map)
        gz_bytes = gzip.compress(ndjson_bytes)

        key = self._build_s3_key(table_name)
        s3_uri = f"s3://{self.staging_bucket}/{key}"

        self._logger.debug(
            f"Uploading {len(df)} rows to {s3_uri} ({len(gz_bytes)} bytes gzipped)"
        )

        s3 = self._get_s3_client()
        s3.put_object(
            Bucket=self.staging_bucket,
            Key=key,
            Body=gz_bytes,
            ContentType="application/x-ndjson",
            ContentEncoding="gzip",
        )

        # Build COPY statement. Single quotes around literals; IAM role and
        # region are not parameterizable in COPY.
        copy_sql = (
            f"COPY {qualified} "
            f"FROM '{s3_uri}' "
            f"IAM_ROLE '{self.copy_iam_role}' "
            f"FORMAT AS JSON 'auto' "
            f"GZIP "
            f"REGION '{self.aws_region}' "
            f"TIMEFORMAT 'auto' "
            f"DATEFORMAT 'auto'"
        )

        try:
            self.connector.execute_query(copy_sql)
            self.connector.commit()
            # Cleanup on success
            try:
                s3.delete_object(Bucket=self.staging_bucket, Key=key)
            except Exception as cleanup_err:
                self._logger.warning(
                    f"COPY succeeded but S3 cleanup failed for {s3_uri}: "
                    f"{cleanup_err}"
                )
        except Exception:
            # Leave the S3 object in place for post-mortem.
            self._logger.error(
                f"COPY failed; staging object retained at {s3_uri} for debugging."
            )
            raise

        return LoadResult(
            table_name=table_name,
            rows_loaded=len(df),
            success=True,
            method=LoadMethod.STAGED,
        )

    def _build_s3_key(self, table_name: str) -> str:
        ts = datetime.utcnow().strftime("%Y-%m-%dT%H-%M-%SZ")
        suffix = uuid.uuid4().hex[:8]
        # Mirrors BigQuery's <project>/<dataset>/<table> layout.
        return (
            f"{self.config.database}/{self.config.schema}/"
            f"{table_name}/{ts}-{suffix}.json.gz"
        )


# ----------------------------------------------------------------------
# Module-level helpers
# ----------------------------------------------------------------------


def _is_null(v: Any) -> bool:
    if v is None:
        return True
    if isinstance(v, float) and pd.isna(v):
        return True
    try:
        if pd.isna(v):
            return True
    except (TypeError, ValueError):
        pass
    return False


def _df_to_ndjson(df: pd.DataFrame, type_map: Dict[str, str]) -> bytes:
    """Serialize a DataFrame to UTF-8 newline-delimited JSON for COPY."""
    buf = io.BytesIO()
    for row in df.to_dict(orient="records"):
        doc: Dict[str, Any] = {}
        for col, val in row.items():
            doc[col] = _to_json_value(val, type_map.get(col))
        buf.write(json.dumps(doc, default=str).encode("utf-8"))
        buf.write(b"\n")
    return buf.getvalue()


def _to_json_value(v: Any, rs_type: Optional[str]) -> Any:
    """Convert a Python / pandas value into the JSON form Redshift COPY expects."""
    if _is_null(v):
        return None

    t = (rs_type or "").upper()

    if t == "SUPER":
        # Redshift COPY into SUPER expects a native JSON value when using
        # FORMAT AS JSON 'auto'. The generator emits JSON strings; parse
        # so the value lands as JSON, not as an escaped string.
        if isinstance(v, (dict, list)):
            return v
        if isinstance(v, str):
            try:
                return json.loads(v)
            except json.JSONDecodeError:
                return v
        return v

    if t.startswith("NUMERIC") or t.startswith("DECIMAL"):
        if isinstance(v, Decimal):
            return str(v)
        return str(v)

    if t == "VARBYTE":
        # COPY with FORMAT AS JSON expects hex-encoded VARBYTE.
        if isinstance(v, (bytes, bytearray)):
            return bytes(v).hex()
        if isinstance(v, str):
            # Generator emits base64; decode to raw bytes then re-encode hex.
            try:
                return base64.b64decode(v).hex()
            except Exception:
                return v
        return str(v)

    if t in ("TIMESTAMP", "TIMESTAMPTZ"):
        if isinstance(v, pd.Timestamp):
            v = v.to_pydatetime()
        if isinstance(v, datetime):
            return v.isoformat()
        return str(v)

    if t == "DATE":
        if isinstance(v, (datetime, pd.Timestamp)):
            return v.strftime("%Y-%m-%d")
        if isinstance(v, date):
            return v.isoformat()
        return str(v)

    if t == "TIME":
        if isinstance(v, dt_time):
            return v.isoformat()
        return str(v)

    if t == "BOOLEAN":
        return bool(v)

    if t in ("INTEGER", "BIGINT", "SMALLINT"):
        try:
            return int(v)
        except (TypeError, ValueError):
            return v

    if t in ("DOUBLE PRECISION", "REAL"):
        try:
            return float(v)
        except (TypeError, ValueError):
            return v

    # GEOGRAPHY (WKT string), VARCHAR, and anything else: pass through.
    if hasattr(v, "item") and not isinstance(v, (str, bytes, bytearray)):
        try:
            return v.item()
        except (AttributeError, ValueError):
            pass
    return v


def _to_insert_value(v: Any, rs_type: Optional[str]) -> Any:
    """Convert a Python / pandas value into the form executemany expects."""
    if _is_null(v):
        return None

    t = (rs_type or "").upper()

    if t == "SUPER":
        # JSON_PARSE wrapper takes a JSON string. If the generator already
        # produced one, pass it through; otherwise serialize.
        if isinstance(v, str):
            return v
        return json.dumps(v, default=str)

    if t == "GEOGRAPHY":
        # ST_GeogFromText takes a WKT string.
        return str(v)

    if t == "VARBYTE":
        if isinstance(v, (bytes, bytearray)):
            return bytes(v)
        if isinstance(v, str):
            try:
                return base64.b64decode(v)
            except Exception:
                return v
        return v

    # numpy scalars need .item() to round-trip cleanly through pyformat
    # parameter binding.
    if hasattr(v, "item") and not isinstance(v, (str, bytes, bytearray)):
        try:
            return v.item()
        except (AttributeError, ValueError):
            pass
    return v
