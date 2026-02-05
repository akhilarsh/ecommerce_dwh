-- ============================================================================
-- New Customer Audience
-- Purpose: Identify customers with first purchase within 30 days
-- Output: New customer segment for onboarding campaigns
-- ============================================================================

WITH customer_first_purchase AS (
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
        SUM(fs.net_amount) AS total_spend,
        DATEDIFF(day, MIN(d.full_date), CURRENT_DATE()) AS days_since_first_purchase
    FROM fact_sales fs
    JOIN dim_customers c ON fs.customer_key = c.customer_key
    JOIN dim_dates d ON fs.date_key = d.date_key
    WHERE c.is_current = TRUE
    GROUP BY c.customer_key, c.customer_id, c.email, c.first_name, c.last_name, c.loyalty_tier
),

-- Get first order details
first_order_details AS (
    SELECT 
        fs.customer_key,
        ch.channel_name AS first_order_channel,
        fs.net_amount AS first_order_value
    FROM fact_sales fs
    JOIN dim_channels ch ON fs.channel_key = ch.channel_key
    JOIN dim_dates d ON fs.date_key = d.date_key
    WHERE (fs.customer_key, d.full_date) IN (
        SELECT customer_key, first_purchase_date
        FROM customer_first_purchase
        WHERE days_since_first_purchase <= 30
    )
    QUALIFY ROW_NUMBER() OVER (PARTITION BY fs.customer_key ORDER BY d.full_date, fs.sale_key) = 1
)

SELECT 
    cfp.customer_key,
    cfp.customer_id,
    cfp.email,
    cfp.first_name,
    cfp.last_name,
    cfp.loyalty_tier,
    cfp.first_purchase_date,
    cfp.days_since_first_purchase,
    cfp.total_orders,
    ROUND(cfp.total_spend, 2) AS total_spend,
    ROUND(fod.first_order_value, 2) AS first_order_value,
    fod.first_order_channel,
    'New Customer' AS audience_name,
    CASE 
        WHEN cfp.days_since_first_purchase <= 7 THEN 'This Week'
        WHEN cfp.days_since_first_purchase <= 14 THEN 'Last 2 Weeks'
        ELSE 'Last 30 Days'
    END AS acquisition_recency,
    CASE 
        WHEN cfp.total_orders > 1 THEN 'Already Repeat'
        ELSE 'First Purchase Only'
    END AS engagement_status,
    CASE 
        WHEN fod.first_order_value >= 200 THEN 'High First Order'
        WHEN fod.first_order_value >= 100 THEN 'Medium First Order'
        ELSE 'Low First Order'
    END AS first_order_segment
FROM customer_first_purchase cfp
LEFT JOIN first_order_details fod ON cfp.customer_key = fod.customer_key
WHERE cfp.days_since_first_purchase <= 30
ORDER BY cfp.first_purchase_date DESC;
