-- ============================================================================
-- Holiday Shoppers Audience
-- Purpose: Identify customers who purchase on holidays
-- Output: Holiday shoppers for seasonal campaign targeting
-- ============================================================================

WITH holiday_purchases AS (
    SELECT 
        c.customer_key,
        c.customer_id,
        c.email,
        c.first_name,
        c.last_name,
        c.loyalty_tier,
        d.full_date,
        d.day_name,
        d.quarter,
        d.year,
        d.is_holiday,
        d.is_weekend,
        fs.order_id,
        fs.net_amount
    FROM fact_sales fs
    JOIN dim_customers c ON fs.customer_key = c.customer_key
    JOIN dim_dates d ON fs.date_key = d.date_key
    WHERE c.is_current = TRUE
),

customer_holiday_stats AS (
    SELECT 
        customer_key,
        customer_id,
        email,
        first_name,
        last_name,
        loyalty_tier,
        -- Holiday purchases
        COUNT(DISTINCT CASE WHEN is_holiday THEN order_id END) AS holiday_orders,
        SUM(CASE WHEN is_holiday THEN net_amount ELSE 0 END) AS holiday_spend,
        -- Non-holiday purchases
        COUNT(DISTINCT CASE WHEN NOT is_holiday THEN order_id END) AS regular_orders,
        SUM(CASE WHEN NOT is_holiday THEN net_amount ELSE 0 END) AS regular_spend,
        -- Q4 (holiday season) purchases
        COUNT(DISTINCT CASE WHEN quarter = 4 THEN order_id END) AS q4_orders,
        SUM(CASE WHEN quarter = 4 THEN net_amount ELSE 0 END) AS q4_spend,
        -- Totals
        COUNT(DISTINCT order_id) AS total_orders,
        SUM(net_amount) AS total_spend
    FROM holiday_purchases
    GROUP BY customer_key, customer_id, email, first_name, last_name, loyalty_tier
)

SELECT 
    customer_key,
    customer_id,
    email,
    first_name,
    last_name,
    loyalty_tier,
    holiday_orders,
    ROUND(holiday_spend, 2) AS holiday_spend,
    regular_orders,
    ROUND(regular_spend, 2) AS regular_spend,
    q4_orders,
    ROUND(q4_spend, 2) AS q4_spend,
    total_orders,
    ROUND(total_spend, 2) AS total_spend,
    ROUND(holiday_orders * 100.0 / NULLIF(total_orders, 0), 1) AS holiday_order_pct,
    ROUND(q4_orders * 100.0 / NULLIF(total_orders, 0), 1) AS q4_order_pct,
    ROUND(holiday_spend / NULLIF(holiday_orders, 0), 2) AS avg_holiday_basket,
    ROUND(regular_spend / NULLIF(regular_orders, 0), 2) AS avg_regular_basket,
    'Holiday Shopper' AS audience_name,
    CASE 
        WHEN holiday_orders >= 5 THEN 'Frequent Holiday Shopper'
        WHEN holiday_orders >= 2 THEN 'Regular Holiday Shopper'
        WHEN holiday_orders >= 1 THEN 'Occasional Holiday Shopper'
        ELSE 'Non-Holiday Shopper'
    END AS holiday_shopper_type,
    CASE 
        WHEN q4_orders * 100.0 / NULLIF(total_orders, 0) >= 50 THEN 'Q4 Heavy'
        WHEN q4_orders * 100.0 / NULLIF(total_orders, 0) >= 25 THEN 'Q4 Active'
        ELSE 'Year-Round'
    END AS seasonality_profile
FROM customer_holiday_stats
WHERE holiday_orders >= 1 OR q4_orders >= 1
ORDER BY holiday_spend DESC, q4_spend DESC;
