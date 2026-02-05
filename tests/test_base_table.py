"""
Tests for base table, Column, and ForeignKey classes.
"""

import pytest
from src.models.base_table import BaseTable, Column, ForeignKey
from src.utils.logger import get_logger

logger = get_logger("test_base_table")


def test_column_basic_definition():
    """Test basic column definition."""
    col = Column(name="test_col", data_type="VARCHAR", length=100)
    sql = col.to_sql()
    logger.info(f"Generated SQL: {sql}")
    
    assert "test_col" in sql
    assert "VARCHAR(100)" in sql


def test_column_with_not_null():
    """Test column with NOT NULL constraint."""
    col = Column(name="required_col", data_type="VARCHAR", length=50, nullable=False)
    sql = col.to_sql()
    logger.info(f"Generated SQL: {sql}")
    
    assert "NOT NULL" in sql


def test_column_number_with_precision():
    """Test NUMBER column with precision."""
    col = Column(name="amount", data_type="NUMBER", precision=18, scale=2)
    sql = col.to_sql()
    logger.info(f"Generated SQL: {sql}")
    
    assert "NUMBER(18,2)" in sql


def test_column_number_surrogate_key():
    """Test NUMBER column for surrogate key."""
    col = Column(name="customer_key", data_type="NUMBER", precision=38, nullable=False)
    sql = col.to_sql()
    
    assert "NUMBER(38)" in sql
    assert "NOT NULL" in sql


def test_column_with_default():
    """Test column with default value."""
    col = Column(name="status", data_type="VARCHAR", length=20, default="'ACTIVE'")
    sql = col.to_sql()
    
    assert "DEFAULT 'ACTIVE'" in sql


def test_column_with_comment():
    """Test column with comment."""
    col = Column(name="id", data_type="NUMBER", precision=38, comment="Primary key")
    sql = col.to_sql()
    
    assert "COMMENT 'Primary key'" in sql


def test_foreign_key_basic():
    """Test basic foreign key definition."""
    fk = ForeignKey(
        column="customer_key",
        reference_table="dim_customers",
        reference_column="customer_key"
    )
    sql = fk.to_sql("fact_sales")
    logger.info(f"Generated FK SQL: {sql}")
    
    assert "ALTER TABLE fact_sales" in sql
    assert "FOREIGN KEY (customer_key)" in sql
    assert "REFERENCES dim_customers(customer_key)" in sql


def test_foreign_key_with_cascade():
    """Test foreign key with CASCADE options."""
    fk = ForeignKey(
        column="product_key",
        reference_table="dim_products",
        reference_column="product_key",
        on_delete="CASCADE"
    )
    sql = fk.to_sql("bridge_order_items")
    
    assert "ON DELETE CASCADE" in sql


def test_foreign_key_custom_constraint_name():
    """Test foreign key with custom constraint name."""
    fk = ForeignKey(
        column="store_key",
        reference_table="dim_stores",
        reference_column="store_key",
        constraint_name="fk_custom_store"
    )
    sql = fk.to_sql("fact_sales")
    
    assert "fk_custom_store" in sql


class TestTable(BaseTable):
    """Test table implementation."""
    
    table_name = "test_table"
    schema_name = "test_schema"
    primary_key = ["id"]
    
    def define_columns(self):
        return [
            Column("id", "NUMBER", precision=38, nullable=False),
            Column("name", "VARCHAR", length=100),
            Column("amount", "NUMBER", precision=18, scale=2)
        ]


def test_base_table_get_full_name():
    """Test getting fully qualified table name."""
    table = TestTable()
    assert table.get_full_table_name() == "test_schema.test_table"


def test_base_table_create_sql():
    """Test CREATE TABLE SQL generation."""
    table = TestTable()
    sql = table.get_create_table_sql()
    logger.info(f"Generated CREATE TABLE SQL:\n{sql}")
    
    assert "CREATE TABLE IF NOT EXISTS test_schema.test_table" in sql
    assert "id NUMBER(38) NOT NULL" in sql
    assert "name VARCHAR(100)" in sql
    assert "amount NUMBER(18,2)" in sql
    assert "PRIMARY KEY (id)" in sql


def test_base_table_with_comment():
    """Test table with comment."""
    
    class CommentedTable(BaseTable):
        table_name = "commented_table"
        schema_name = "test_schema"
        comment = "Test table with comment"
        
        def define_columns(self):
            return [Column("id", "NUMBER", precision=38, nullable=False)]
    
    table = CommentedTable()
    sql = table.get_create_table_sql()
    
    assert "COMMENT = 'Test table with comment'" in sql


def test_base_table_with_cluster_keys():
    """Test table with clustering keys."""
    
    class ClusteredTable(BaseTable):
        table_name = "clustered_table"
        schema_name = "test_schema"
        cluster_keys = ["date_key", "customer_key"]
        
        def define_columns(self):
            return [
                Column("id", "NUMBER", precision=38, nullable=False),
                Column("date_key", "NUMBER", precision=38),
                Column("customer_key", "NUMBER", precision=38)
            ]
    
    table = ClusteredTable()
    sql = table.get_create_table_sql()
    logger.info(f"Generated clustered table SQL:\n{sql}")
    
    assert "CLUSTER BY (date_key, customer_key)" in sql


def test_base_table_with_foreign_keys():
    """Test table with foreign keys."""
    
    class TableWithFK(BaseTable):
        table_name = "table_with_fk"
        schema_name = "test_schema"
        primary_key = ["id"]
        foreign_keys = [
            ForeignKey(
                column="customer_key",
                reference_table="dim_customers",
                reference_column="customer_key"
            )
        ]
        
        def define_columns(self):
            return [
                Column("id", "NUMBER", precision=38, nullable=False),
                Column("customer_key", "NUMBER", precision=38)
            ]
    
    table = TableWithFK()
    fk_statements = table.get_foreign_key_sql()
    logger.info(f"Generated FK statements: {fk_statements}")
    
    assert len(fk_statements) == 1
    assert "ALTER TABLE test_schema.table_with_fk" in fk_statements[0]
    assert "REFERENCES dim_customers(customer_key)" in fk_statements[0]


def test_base_table_validation_success():
    """Test successful table validation."""
    table = TestTable()
    result = table.validate()
    logger.info(f"Validation result: {result}")
    assert result is True


def test_base_table_validation_no_table_name():
    """Test validation fails without table_name."""
    
    class NoNameTable(BaseTable):
        table_name = ""
        
        def define_columns(self):
            return [Column("id", "NUMBER", precision=38)]
    
    table = NoNameTable()
    with pytest.raises(ValueError, match="table_name is required"):
        table.validate()


def test_base_table_validation_no_columns():
    """Test validation fails without columns."""
    
    class NoColumnsTable(BaseTable):
        table_name = "empty_table"
        
        def define_columns(self):
            return []
    
    table = NoColumnsTable()
    with pytest.raises(ValueError, match="No columns defined"):
        table.validate()


def test_base_table_validation_invalid_pk():
    """Test validation fails with invalid primary key column."""
    
    class InvalidPKTable(BaseTable):
        table_name = "invalid_pk"
        primary_key = ["non_existent_col"]
        
        def define_columns(self):
            return [Column("id", "NUMBER", precision=38)]
    
    table = InvalidPKTable()
    with pytest.raises(ValueError, match="Primary key column.*not found"):
        table.validate()


def test_base_table_validation_invalid_fk():
    """Test validation fails with invalid foreign key column."""
    
    class InvalidFKTable(BaseTable):
        table_name = "invalid_fk"
        foreign_keys = [
            ForeignKey(
                column="non_existent_col",
                reference_table="other_table",
                reference_column="id"
            )
        ]
        
        def define_columns(self):
            return [Column("id", "NUMBER", precision=38)]
    
    table = InvalidFKTable()
    with pytest.raises(ValueError, match="Foreign key column.*not found"):
        table.validate()


def test_base_table_multiple_primary_keys():
    """Test table with composite primary key."""
    
    class CompositePKTable(BaseTable):
        table_name = "composite_pk"
        schema_name = "test_schema"
        primary_key = ["id1", "id2"]
        
        def define_columns(self):
            return [
                Column("id1", "NUMBER", precision=38, nullable=False),
                Column("id2", "NUMBER", precision=38, nullable=False),
                Column("data", "VARCHAR", length=100)
            ]
    
    table = CompositePKTable()
    sql = table.get_create_table_sql()
    
    assert "PRIMARY KEY (id1, id2)" in sql
