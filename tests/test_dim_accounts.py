"""
Tests for dim_accounts and bridge_account_customers tables.

Covers model validation, data generation, and referential integrity.
"""

import pytest
from datetime import date

from src.models.dimension_tables.dim_accounts import DimAccounts
from src.models.bridge_tables.bridge_account_customers import BridgeAccountCustomers
from src.models.dimension_tables.dim_customers import DimCustomers
from src.data_generators.config import load_config
from src.data_generators.entities.dim_accounts import DimAccountsGenerator
from src.data_generators.entities.bridge_account_customers import BridgeAccountCustomersGenerator
from src.data_generators.entities.dim_customers import DimCustomersGenerator


@pytest.fixture(scope="module")
def config():
    cfg = load_config()
    cfg.volumes.accounts = 30
    cfg.volumes.customers = 50
    cfg.settings.seed = 42
    return cfg


@pytest.fixture(scope="module")
def accounts_data(config):
    gen = DimAccountsGenerator(config)
    return gen.generate(count=30, start_key=1)


@pytest.fixture(scope="module")
def customers_data(config, accounts_data):
    gen = DimCustomersGenerator(config)
    return gen.generate(
        count=50,
        start_key=1,
        account_keys=accounts_data.surrogate_keys
    )


@pytest.fixture(scope="module")
def bridge_data(config, accounts_data, customers_data):
    acct_cust_map = {}
    for _, row in customers_data.data.iterrows():
        ak = int(row["account_key"])
        ck = int(row["customer_key"])
        acct_cust_map.setdefault(ak, []).append(ck)

    gen = BridgeAccountCustomersGenerator(config)
    return gen.generate(start_key=1, account_customer_map=acct_cust_map)


# ============================================================================
# Model Validation
# ============================================================================

class TestDimAccountsModel:
    def test_table_name(self):
        table = DimAccounts()
        assert table.table_name == "dim_accounts"

    def test_primary_key(self):
        table = DimAccounts()
        assert table.primary_key == ["account_key"]

    def test_no_foreign_keys(self):
        table = DimAccounts()
        assert table.foreign_keys == []

    def test_validate_passes(self):
        table = DimAccounts()
        table.validate()

    def test_has_required_columns(self):
        table = DimAccounts()
        col_names = [c.name for c in table.define_columns()]
        required = [
            "account_key", "account_id", "account_name", "account_type",
            "account_status", "registration_date", "is_active",
            "created_at",
        ]
        for col in required:
            assert col in col_names, f"Missing required column: {col}"

    def test_has_billing_address_columns(self):
        table = DimAccounts()
        col_names = [c.name for c in table.define_columns()]
        billing_cols = [
            "billing_address_line1", "billing_city",
            "billing_state", "billing_postal_code", "billing_country",
        ]
        for col in billing_cols:
            assert col in col_names

    def test_has_b2b_columns(self):
        table = DimAccounts()
        col_names = [c.name for c in table.define_columns()]
        b2b_cols = ["company_name", "tax_id", "tax_exempt_status",
                     "payment_terms", "credit_limit"]
        for col in b2b_cols:
            assert col in col_names

    def test_column_count(self):
        table = DimAccounts()
        assert len(table.define_columns()) == 22


class TestBridgeAccountCustomersModel:
    def test_table_name(self):
        table = BridgeAccountCustomers()
        assert table.table_name == "bridge_account_customers"

    def test_primary_key(self):
        table = BridgeAccountCustomers()
        assert table.primary_key == ["account_customer_key"]

    def test_cluster_keys(self):
        table = BridgeAccountCustomers()
        assert table.cluster_keys == ["account_key", "customer_key"]

    def test_foreign_keys(self):
        table = BridgeAccountCustomers()
        fk_cols = {fk.column for fk in table.foreign_keys}
        assert fk_cols == {"account_key", "customer_key"}

    def test_validate_passes(self):
        table = BridgeAccountCustomers()
        table.validate()

    def test_has_role_and_temporal_columns(self):
        table = BridgeAccountCustomers()
        col_names = [c.name for c in table.define_columns()]
        for col in ["role", "is_primary_contact", "effective_date",
                     "end_date", "is_current"]:
            assert col in col_names


class TestDimCustomersAccountFK:
    def test_has_account_key_column(self):
        table = DimCustomers()
        col_names = [c.name for c in table.define_columns()]
        assert "account_key" in col_names

    def test_has_account_fk(self):
        table = DimCustomers()
        fk_targets = {fk.reference_table for fk in table.foreign_keys}
        assert "dim_accounts" in fk_targets

    def test_account_key_is_nullable(self):
        table = DimCustomers()
        acct_col = [c for c in table.define_columns() if c.name == "account_key"][0]
        assert acct_col.nullable is True


# ============================================================================
# Data Generation
# ============================================================================

class TestDimAccountsGenerator:
    def test_generates_correct_count(self, accounts_data):
        assert len(accounts_data.data) == 30
        assert len(accounts_data.surrogate_keys) == 30

    def test_surrogate_keys_sequential(self, accounts_data):
        assert accounts_data.surrogate_keys == list(range(1, 31))

    def test_all_columns_present(self, accounts_data):
        expected = {
            "account_key", "account_id", "account_name", "account_type",
            "company_name", "tax_id", "tax_exempt_status",
            "billing_address_line1", "billing_address_line2",
            "billing_city", "billing_state", "billing_postal_code",
            "billing_country", "payment_terms", "credit_limit",
            "account_status", "account_tier", "registration_date",
            "closure_date", "is_active", "created_at", "updated_at",
        }
        assert set(accounts_data.data.columns) == expected

    def test_account_types_valid(self, accounts_data):
        valid_types = {"Individual", "Household", "Business", "Corporate", "Guest"}
        actual_types = set(accounts_data.data["account_type"].unique())
        assert actual_types.issubset(valid_types)

    def test_b2b_accounts_have_company_name(self, accounts_data):
        df = accounts_data.data
        b2b = df[df["account_type"].isin(["Business", "Corporate"])]
        if not b2b.empty:
            assert b2b["company_name"].notna().all()

    def test_individual_accounts_no_company(self, accounts_data):
        df = accounts_data.data
        individual = df[df["account_type"] == "Individual"]
        if not individual.empty:
            assert individual["company_name"].isna().all()

    def test_business_ids_format(self, accounts_data):
        for _, row in accounts_data.data.iterrows():
            assert row["account_id"].startswith("ACCT")

    def test_zero_count_returns_empty(self, config):
        gen = DimAccountsGenerator(config)
        result = gen.generate(count=0)
        assert len(result.data) == 0
        assert result.surrogate_keys == []


class TestBridgeAccountCustomersGenerator:
    def test_generates_one_row_per_customer(self, bridge_data, customers_data):
        assert len(bridge_data.data) == len(customers_data.data)

    def test_first_customer_per_account_is_owner(self, bridge_data):
        df = bridge_data.data
        for acct_key in df["account_key"].unique():
            acct_rows = df[df["account_key"] == acct_key].sort_values("account_customer_key")
            first_row = acct_rows.iloc[0]
            assert first_row["role"] == "Owner"
            assert bool(first_row["is_primary_contact"]) is True

    def test_all_columns_present(self, bridge_data):
        expected = {
            "account_customer_key", "account_key", "customer_key",
            "role", "is_primary_contact", "effective_date",
            "end_date", "is_current", "created_at",
        }
        assert set(bridge_data.data.columns) == expected

    def test_empty_map_returns_empty(self, config):
        gen = BridgeAccountCustomersGenerator(config)
        result = gen.generate(start_key=1, account_customer_map={})
        assert len(result.data) == 0

    def test_referential_integrity_accounts(self, bridge_data, accounts_data):
        bridge_acct_keys = set(bridge_data.data["account_key"].unique())
        valid_acct_keys = set(accounts_data.surrogate_keys)
        orphans = bridge_acct_keys - valid_acct_keys
        assert len(orphans) == 0, f"Orphan account keys: {orphans}"

    def test_referential_integrity_customers(self, bridge_data, customers_data):
        bridge_cust_keys = set(bridge_data.data["customer_key"].unique())
        valid_cust_keys = set(customers_data.surrogate_keys)
        orphans = bridge_cust_keys - valid_cust_keys
        assert len(orphans) == 0, f"Orphan customer keys: {orphans}"


class TestDimCustomersAccountKeyGeneration:
    def test_customers_have_account_key(self, customers_data):
        assert "account_key" in customers_data.data.columns
        assert customers_data.data["account_key"].notna().all()

    def test_account_keys_reference_valid_accounts(self, customers_data, accounts_data):
        cust_acct_keys = set(customers_data.data["account_key"].unique())
        valid_acct_keys = set(accounts_data.surrogate_keys)
        orphans = cust_acct_keys - valid_acct_keys
        assert len(orphans) == 0

    def test_customers_without_account_keys_get_none(self, config):
        gen = DimCustomersGenerator(config)
        result = gen.generate(count=5, start_key=1, account_keys=None)
        assert result.data["account_key"].isna().all()
