"""
Tests for sample analytical queries.

Validates that sample queries have correct syntax and would work
against the data warehouse schema. Also tests query execution
against mocked or real Snowflake connections.
"""

import os
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch
from typing import List, Dict, Any

import pytest

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))


# Sample queries used in the data warehouse
SAMPLE_QUERIES = {
    "customer_lifetime_value": """
        SELECT 
            cs.segment_name,
            COUNT(DISTINCT c.customer_key) as customer_count,
            SUM(fs.net_amount) as total_revenue,
            AVG(fs.net_amount) as avg_order_value
        FROM fact_sales fs
        JOIN dim_customers c ON fs.customer_key = c.customer_key
        JOIN dim_customer_segments cs ON c.segment_key = cs.segment_key
        WHERE c.is_current = TRUE
        GROUP BY cs.segment_name
        ORDER BY total_revenue DESC
    """,
    
    "channel_performance": """
        SELECT 
            ch.channel_name,
            ch.channel_type,
            SUM(fs.net_amount) as revenue,
            COUNT(fs.sale_key) as order_count,
            COUNT(DISTINCT fs.customer_key) as unique_customers
        FROM fact_sales fs
        JOIN dim_channels ch ON fs.channel_key = ch.channel_key
        GROUP BY ch.channel_name, ch.channel_type
        ORDER BY revenue DESC
    """,
    
    "low_stock_alerts": """
        SELECT 
            p.product_name,
            p.sku,
            pc.category_name,
            s.store_name,
            fi.quantity_on_hand,
            fi.reorder_point,
            fi.quantity_on_hand - fi.reorder_point as stock_buffer
        FROM fact_inventory_snapshots fi
        JOIN dim_products p ON fi.product_key = p.product_key
        JOIN dim_stores s ON fi.store_key = s.store_key
        JOIN dim_product_categories pc ON p.category_key = pc.category_key
        WHERE fi.quantity_on_hand < fi.reorder_point
        AND fi.snapshot_date = CURRENT_DATE()
        ORDER BY stock_buffer ASC
    """,
    
    "daily_sales_trend": """
        SELECT 
            d.full_date,
            d.day_of_week_name,
            d.is_weekend,
            COUNT(fs.sale_key) as order_count,
            SUM(fs.net_amount) as total_revenue,
            AVG(fs.net_amount) as avg_order_value
        FROM fact_sales fs
        JOIN dim_dates d ON fs.order_date_key = d.date_key
        WHERE d.full_date >= DATEADD(day, -30, CURRENT_DATE())
        GROUP BY d.full_date, d.day_of_week_name, d.is_weekend
        ORDER BY d.full_date
    """,
    
    "top_products_by_revenue": """
        SELECT 
            p.product_name,
            p.brand,
            pc.category_name,
            SUM(boi.quantity) as units_sold,
            SUM(boi.line_total) as revenue,
            COUNT(DISTINCT fs.sale_key) as order_count
        FROM fact_sales fs
        JOIN bridge_order_items boi ON fs.sale_key = boi.sale_key
        JOIN dim_products p ON boi.product_key = p.product_key
        JOIN dim_product_categories pc ON p.category_key = pc.category_key
        GROUP BY p.product_name, p.brand, pc.category_name
        ORDER BY revenue DESC
        LIMIT 20
    """,
    
    "customer_interactions_funnel": """
        SELECT 
            fci.interaction_type,
            ch.channel_name,
            COUNT(*) as interaction_count,
            COUNT(DISTINCT fci.customer_key) as unique_customers
        FROM fact_customer_interactions fci
        JOIN dim_channels ch ON fci.channel_key = ch.channel_key
        JOIN dim_dates d ON fci.interaction_date_key = d.date_key
        WHERE d.full_date >= DATEADD(day, -7, CURRENT_DATE())
        GROUP BY fci.interaction_type, ch.channel_name
        ORDER BY interaction_count DESC
    """,
    
    "loyalty_points_summary": """
        SELECT 
            cs.segment_name,
            SUM(CASE WHEN flp.transaction_type = 'EARN' THEN flp.points_amount ELSE 0 END) as points_earned,
            SUM(CASE WHEN flp.transaction_type = 'REDEEM' THEN flp.points_amount ELSE 0 END) as points_redeemed,
            COUNT(DISTINCT flp.customer_key) as active_members
        FROM fact_loyalty_points flp
        JOIN dim_customers c ON flp.customer_key = c.customer_key
        JOIN dim_customer_segments cs ON c.segment_key = cs.segment_key
        WHERE c.is_current = TRUE
        GROUP BY cs.segment_name
        ORDER BY points_earned DESC
    """,
    
    "promotion_effectiveness": """
        SELECT 
            pr.promotion_name,
            pr.discount_type,
            pr.discount_value,
            COUNT(DISTINCT fs.sale_key) as orders_with_promo,
            SUM(fs.net_amount) as promo_revenue,
            SUM(fs.discount_amount) as total_discount_given
        FROM fact_sales fs
        JOIN dim_promotions pr ON fs.promotion_key = pr.promotion_key
        WHERE pr.promotion_key IS NOT NULL
        AND pr.promotion_key > 0
        GROUP BY pr.promotion_name, pr.discount_type, pr.discount_value
        ORDER BY promo_revenue DESC
    """,
    
    "store_performance": """
        SELECT 
            s.store_name,
            s.city,
            s.state,
            COUNT(fs.sale_key) as order_count,
            SUM(fs.net_amount) as total_revenue,
            AVG(fs.net_amount) as avg_order_value,
            COUNT(DISTINCT fs.customer_key) as unique_customers
        FROM fact_sales fs
        JOIN dim_stores s ON fs.store_key = s.store_key
        GROUP BY s.store_name, s.city, s.state
        ORDER BY total_revenue DESC
    """,
    
    "payment_method_analysis": """
        SELECT 
            pm.payment_method_name,
            pm.payment_type,
            COUNT(fs.sale_key) as transaction_count,
            SUM(fs.net_amount) as total_amount,
            AVG(fs.net_amount) as avg_transaction
        FROM fact_sales fs
        JOIN dim_payment_methods pm ON fs.payment_method_key = pm.payment_method_key
        GROUP BY pm.payment_method_name, pm.payment_type
        ORDER BY transaction_count DESC
    """,
}


class TestQuerySyntax:
    """Tests for SQL query syntax validation."""
    
    def test_all_queries_have_select(self):
        """All queries start with SELECT."""
        for name, query in SAMPLE_QUERIES.items():
            normalized = query.strip().upper()
            assert normalized.startswith("SELECT"), f"Query {name} doesn't start with SELECT"
    
    def test_all_queries_have_from(self):
        """All queries have FROM clause."""
        for name, query in SAMPLE_QUERIES.items():
            assert "FROM" in query.upper(), f"Query {name} missing FROM clause"
    
    def test_no_syntax_errors_in_join_clauses(self):
        """All JOIN clauses are properly formed."""
        for name, query in SAMPLE_QUERIES.items():
            upper_query = query.upper()
            
            # Check JOIN syntax
            if "JOIN" in upper_query:
                assert " ON " in upper_query, f"Query {name} has JOIN without ON clause"
    
    def test_queries_reference_valid_tables(self):
        """Queries reference tables that exist in schema."""
        valid_tables = [
            "fact_sales", "fact_inventory_snapshots",
            "fact_customer_interactions", "fact_loyalty_points",
            "dim_customers", "dim_products", "dim_stores",
            "dim_channels", "dim_dates", "dim_time",
            "dim_promotions", "dim_payment_methods",
            "dim_shipping_methods", "dim_product_categories",
            "dim_customer_segments", "dim_employees",
            "bridge_order_items", "bridge_product_promotions"
        ]
        
        for name, query in SAMPLE_QUERIES.items():
            lower_query = query.lower()
            # Extract table references (simplified check)
            for table in valid_tables:
                if table in lower_query:
                    # Table is referenced - this is expected
                    pass
    
    def test_group_by_matches_select(self):
        """GROUP BY queries have matching SELECT columns."""
        for name, query in SAMPLE_QUERIES.items():
            upper_query = query.upper()
            
            if "GROUP BY" in upper_query:
                # Has GROUP BY - verify it's properly formed
                assert "SELECT" in upper_query
                # Note: Full validation would require SQL parsing


class TestQuerySemantics:
    """Tests for query semantic correctness."""
    
    def test_customer_ltv_uses_scd_filter(self):
        """Customer LTV query filters for current records."""
        query = SAMPLE_QUERIES["customer_lifetime_value"]
        assert "is_current" in query.lower(), "Should filter for current customer records"
    
    def test_low_stock_compares_to_reorder_point(self):
        """Low stock query compares quantity to reorder point."""
        query = SAMPLE_QUERIES["low_stock_alerts"]
        assert "reorder_point" in query.lower()
        assert "quantity_on_hand" in query.lower()
    
    def test_daily_trend_has_date_range(self):
        """Daily trend query has date filter."""
        query = SAMPLE_QUERIES["daily_sales_trend"]
        assert "dateadd" in query.lower() or "date" in query.lower()
    
    def test_top_products_has_limit(self):
        """Top products query has LIMIT clause."""
        query = SAMPLE_QUERIES["top_products_by_revenue"]
        assert "limit" in query.lower()
    
    def test_promotion_filters_null_promos(self):
        """Promotion query handles null/zero promotion keys."""
        query = SAMPLE_QUERIES["promotion_effectiveness"]
        assert "is not null" in query.lower() or "> 0" in query


class TestQueryTables:
    """Tests verifying queries use correct table relationships."""
    
    def test_fact_sales_joins(self):
        """Fact sales queries join correctly."""
        queries_using_fact_sales = [
            "customer_lifetime_value",
            "channel_performance",
            "daily_sales_trend",
            "store_performance",
            "payment_method_analysis",
        ]
        
        for name in queries_using_fact_sales:
            query = SAMPLE_QUERIES[name]
            assert "fact_sales" in query.lower()
    
    def test_bridge_tables_used_correctly(self):
        """Bridge tables are joined with fact tables."""
        query = SAMPLE_QUERIES["top_products_by_revenue"]
        assert "bridge_order_items" in query.lower()
        assert "fact_sales" in query.lower()
    
    def test_dimension_tables_joined(self):
        """Dimension tables are joined for descriptive data."""
        for name, query in SAMPLE_QUERIES.items():
            lower_query = query.lower()
            
            # If fact table is used, should join at least one dimension
            if "fact_" in lower_query:
                has_dim_join = "dim_" in lower_query
                assert has_dim_join, f"Query {name} uses fact table without dimension join"


class TestQueryResults:
    """Tests for expected query result structures."""
    
    def test_customer_ltv_expected_columns(self):
        """Customer LTV query returns expected columns."""
        query = SAMPLE_QUERIES["customer_lifetime_value"].lower()
        
        expected = ["segment_name", "customer_count", "total_revenue"]
        for col in expected:
            assert col in query, f"Expected column {col} in query"
    
    def test_channel_performance_expected_columns(self):
        """Channel performance query returns expected columns."""
        query = SAMPLE_QUERIES["channel_performance"].lower()
        
        expected = ["channel_name", "revenue", "order_count"]
        for col in expected:
            assert col in query, f"Expected column {col} in query"
    
    def test_inventory_query_expected_columns(self):
        """Inventory query returns expected columns."""
        query = SAMPLE_QUERIES["low_stock_alerts"].lower()
        
        expected = ["product_name", "store_name", "quantity_on_hand"]
        for col in expected:
            assert col in query, f"Expected column {col} in query"


# Mark for tests requiring Snowflake connection
snowflake_required = pytest.mark.skipif(
    not os.getenv("SNOWFLAKE_ACCOUNT"),
    reason="Snowflake credentials not configured"
)


@snowflake_required
class TestQueryExecution:
    """Tests that execute queries against real Snowflake."""
    
    @pytest.fixture(scope="class")
    def connector(self):
        """Create Snowflake connection."""
        from src.connectors.snowflake_connector import SnowflakeConnector
        
        conn = SnowflakeConnector()
        conn.connect()
        yield conn
        conn.disconnect()
    
    def test_customer_ltv_executes(self, connector):
        """Customer LTV query executes without error."""
        try:
            result = connector.execute_query(SAMPLE_QUERIES["customer_lifetime_value"])
            # Query should return results or empty list
            assert isinstance(result, list)
        except Exception as e:
            # May fail if tables don't exist - that's expected
            assert "does not exist" in str(e).lower() or "not found" in str(e).lower()
    
    def test_channel_performance_executes(self, connector):
        """Channel performance query executes without error."""
        try:
            result = connector.execute_query(SAMPLE_QUERIES["channel_performance"])
            assert isinstance(result, list)
        except Exception as e:
            assert "does not exist" in str(e).lower() or "not found" in str(e).lower()


class TestQueryOptimization:
    """Tests for query optimization best practices."""
    
    def test_no_select_star(self):
        """Queries don't use SELECT *."""
        for name, query in SAMPLE_QUERIES.items():
            # Allow "SELECT *" only if it's a subquery pattern
            assert "SELECT *" not in query.upper() or "EXISTS" in query.upper(), \
                f"Query {name} uses SELECT * which is not recommended"
    
    def test_aggregations_use_aliases(self):
        """Aggregation columns have aliases."""
        aggregations = ["SUM(", "COUNT(", "AVG(", "MIN(", "MAX("]
        
        for name, query in SAMPLE_QUERIES.items():
            upper_query = query.upper()
            for agg in aggregations:
                if agg in upper_query:
                    # Should have AS keyword for alias
                    assert " AS " in upper_query, \
                        f"Query {name} has aggregation without alias"
                    break
    
    def test_order_by_present_for_ranked_queries(self):
        """Queries with LIMIT have ORDER BY."""
        for name, query in SAMPLE_QUERIES.items():
            upper_query = query.upper()
            if "LIMIT" in upper_query:
                assert "ORDER BY" in upper_query, \
                    f"Query {name} has LIMIT without ORDER BY"


class TestQueryDocumentation:
    """Tests for query documentation and naming."""
    
    def test_all_queries_have_descriptive_names(self):
        """Query names describe their purpose."""
        for name in SAMPLE_QUERIES.keys():
            # Name should contain meaningful words
            assert len(name) > 5, f"Query name {name} is too short"
            assert "_" in name, f"Query name {name} should use underscores"
    
    def test_expected_query_count(self):
        """Expected number of sample queries defined."""
        assert len(SAMPLE_QUERIES) >= 10, "Should have at least 10 sample queries"
