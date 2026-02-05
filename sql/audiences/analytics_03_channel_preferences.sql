-- ============================================================================
-- Channel Preferences Query
-- Purpose: Identify primary channel per customer and calculate channel affinity
-- Output: Customer channel preferences with affinity scores
-- ============================================================================

WITH customer_channel_stats AS (
    SELECT 
        c.customer_key,
        c.customer_id,
        c.email,
        c.first_name,
        c.last_name,
        ch.channel_key,
        ch.channel_name,
        ch.channel_type,
        COUNT(DISTINCT fs.order_id) AS orders_via_channel,
        SUM(fs.net_amount) AS revenue_via_channel
    FROM fact_sales fs
    JOIN dim_customers c ON fs.customer_key = c.customer_key
    JOIN dim_channels ch ON fs.channel_key = ch.channel_key
    WHERE c.is_current = TRUE
    GROUP BY c.customer_key, c.customer_id, c.email, c.first_name, c.last_name,
             ch.channel_key, ch.channel_name, ch.channel_type
),

customer_totals AS (
    SELECT 
        customer_key,
        SUM(orders_via_channel) AS total_orders,
        SUM(revenue_via_channel) AS total_revenue
    FROM customer_channel_stats
    GROUP BY customer_key
),

channel_affinity AS (
    SELECT 
        ccs.customer_key,
        ccs.customer_id,
        ccs.email,
        ccs.first_name,
        ccs.last_name,
        ccs.channel_name,
        ccs.channel_type,
        ccs.orders_via_channel,
        ROUND(ccs.revenue_via_channel, 2) AS revenue_via_channel,
        ct.total_orders,
        ROUND(ct.total_revenue, 2) AS total_revenue,
        ROUND(ccs.orders_via_channel * 100.0 / ct.total_orders, 2) AS order_share_pct,
        ROUND(ccs.revenue_via_channel * 100.0 / ct.total_revenue, 2) AS revenue_share_pct,
        ROW_NUMBER() OVER (PARTITION BY ccs.customer_key ORDER BY ccs.orders_via_channel DESC) AS channel_rank
    FROM customer_channel_stats ccs
    JOIN customer_totals ct ON ccs.customer_key = ct.customer_key
)

SELECT 
    customer_key,
    customer_id,
    email,
    first_name,
    last_name,
    channel_name AS primary_channel,
    channel_type AS primary_channel_type,
    orders_via_channel AS primary_channel_orders,
    revenue_via_channel AS primary_channel_revenue,
    total_orders,
    total_revenue,
    order_share_pct AS channel_affinity_pct,
    CASE 
        WHEN order_share_pct >= 80 THEN 'Single Channel Loyalist'
        WHEN order_share_pct >= 50 THEN 'Channel Preferred'
        ELSE 'Multi-Channel Shopper'
    END AS channel_behavior
FROM channel_affinity
WHERE channel_rank = 1
ORDER BY total_revenue DESC;
