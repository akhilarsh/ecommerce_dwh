-- ============================================================================
-- Recalculate dim_customer_loyalty.lifetime_value from fact_sales
-- ============================================================================
-- Run after every data load (initial or incremental) to keep
-- lifetime_value in sync with actual sales totals.
--
-- Excludes Cancelled and Returned orders.
-- Updates only current SCD Type 2 rows (is_current = TRUE).
--
-- Uses the active schema from the connection (e.g. SNOWFLAKE_SCHEMA).
-- ============================================================================

UPDATE dim_customer_loyalty l
SET
    lifetime_value = COALESCE(agg.total_ltv, 0),
    updated_at = CURRENT_TIMESTAMP()
FROM (
    SELECT
        customer_key,
        SUM(total_amount) AS total_ltv
    FROM fact_sales
    WHERE order_status NOT IN ('Cancelled', 'Returned')
    GROUP BY customer_key
) agg
WHERE l.customer_key = agg.customer_key
  AND l.is_current = TRUE;
