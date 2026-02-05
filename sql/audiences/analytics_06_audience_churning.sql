-- ============================================================================
-- Churning Customer Audience
-- Purpose: Identify customers at risk of churning (no purchase in 90+ days)
-- Output: Churn risk segment for win-back campaigns
-- ============================================================================

WITH customer_activity AS (
    SELECT 
        c.customer_key,
        c.customer_id,
        c.email,
        c.first_name,
        c.last_name,
        c.loyalty_tier,
        MIN(d.full_date) AS first_purchase_date,
        MAX(d.full_date) AS last_purchase_date,
        COUNT(DISTINCT fs.order_id) AS total_orders,
        SUM(fs.net_amount) AS total_ltv,
        DATEDIFF(day, MAX(d.full_date), CURRENT_DATE()) AS days_since_last_purchase
    FROM fact_sales fs
    JOIN dim_customers c ON fs.customer_key = c.customer_key
    JOIN dim_dates d ON fs.date_key = d.date_key
    WHERE c.is_current = TRUE
    GROUP BY c.customer_key, c.customer_id, c.email, c.first_name, c.last_name, c.loyalty_tier
),

-- Calculate what was "normal" purchase frequency for each customer
purchase_frequency AS (
    SELECT 
        customer_key,
        DATEDIFF(day, first_purchase_date, last_purchase_date) AS active_period_days,
        CASE 
            WHEN total_orders > 1 
            THEN DATEDIFF(day, first_purchase_date, last_purchase_date) / (total_orders - 1)
            ELSE NULL 
        END AS avg_days_between_purchases
    FROM customer_activity
    WHERE total_orders > 1
)

SELECT 
    ca.customer_key,
    ca.customer_id,
    ca.email,
    ca.first_name,
    ca.last_name,
    ca.loyalty_tier,
    ca.first_purchase_date,
    ca.last_purchase_date,
    ca.days_since_last_purchase,
    ca.total_orders,
    ROUND(ca.total_ltv, 2) AS total_ltv,
    ROUND(pf.avg_days_between_purchases, 1) AS avg_days_between_purchases,
    'Churning Customer' AS audience_name,
    CASE 
        WHEN ca.days_since_last_purchase >= 180 THEN 'Critical - 180+ days'
        WHEN ca.days_since_last_purchase >= 120 THEN 'High Risk - 120+ days'
        WHEN ca.days_since_last_purchase >= 90 THEN 'At Risk - 90+ days'
        ELSE 'Monitor'
    END AS churn_risk_level,
    CASE 
        WHEN ca.total_ltv >= 1000 THEN 'High Value at Risk'
        WHEN ca.total_ltv >= 500 THEN 'Medium Value at Risk'
        ELSE 'Low Value at Risk'
    END AS value_at_risk
FROM customer_activity ca
LEFT JOIN purchase_frequency pf ON ca.customer_key = pf.customer_key
WHERE ca.days_since_last_purchase >= 90
  AND ca.total_orders >= 2  -- Had repeat behavior before
ORDER BY ca.total_ltv DESC, ca.days_since_last_purchase DESC;
