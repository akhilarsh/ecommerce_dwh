-- ============================================================================
-- Customer Lifetime Value Tiers Query
-- Purpose: Calculate total spend per customer and assign LTV tiers
-- Output: Customers with LTV amount and tier (Bronze, Silver, Gold, Platinum)
-- ============================================================================

WITH customer_ltv AS (
    SELECT 
        c.customer_key,
        c.customer_id,
        c.email,
        c.first_name,
        c.last_name,
        c.loyalty_tier AS current_loyalty_tier,
        MIN(d.full_date) AS first_purchase_date,
        MAX(d.full_date) AS last_purchase_date,
        COUNT(DISTINCT fs.order_id) AS total_orders,
        SUM(fs.net_amount) AS total_ltv,
        AVG(fs.net_amount) AS avg_order_value,
        DATEDIFF(month, MIN(d.full_date), CURRENT_DATE()) AS customer_tenure_months
    FROM fact_sales fs
    JOIN dim_customers c ON fs.customer_key = c.customer_key
    JOIN dim_dates d ON fs.date_key = d.date_key
    WHERE c.is_current = TRUE
    GROUP BY c.customer_key, c.customer_id, c.email, c.first_name, c.last_name, c.loyalty_tier
),

ltv_percentiles AS (
    SELECT 
        PERCENTILE_CONT(0.25) WITHIN GROUP (ORDER BY total_ltv) AS p25,
        PERCENTILE_CONT(0.50) WITHIN GROUP (ORDER BY total_ltv) AS p50,
        PERCENTILE_CONT(0.75) WITHIN GROUP (ORDER BY total_ltv) AS p75,
        PERCENTILE_CONT(0.90) WITHIN GROUP (ORDER BY total_ltv) AS p90
    FROM customer_ltv
)

SELECT 
    cl.customer_key,
    cl.customer_id,
    cl.email,
    cl.first_name,
    cl.last_name,
    cl.current_loyalty_tier,
    cl.first_purchase_date,
    cl.last_purchase_date,
    cl.total_orders,
    ROUND(cl.total_ltv, 2) AS total_ltv,
    ROUND(cl.avg_order_value, 2) AS avg_order_value,
    cl.customer_tenure_months,
    CASE 
        WHEN cl.total_ltv >= lp.p90 THEN 'Platinum'
        WHEN cl.total_ltv >= lp.p75 THEN 'Gold'
        WHEN cl.total_ltv >= lp.p50 THEN 'Silver'
        ELSE 'Bronze'
    END AS ltv_tier,
    CASE 
        WHEN cl.total_ltv >= lp.p90 THEN 4
        WHEN cl.total_ltv >= lp.p75 THEN 3
        WHEN cl.total_ltv >= lp.p50 THEN 2
        ELSE 1
    END AS ltv_tier_rank
FROM customer_ltv cl
CROSS JOIN ltv_percentiles lp
ORDER BY cl.total_ltv DESC;
