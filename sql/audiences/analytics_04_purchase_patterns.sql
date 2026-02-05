-- ============================================================================
-- Purchase Patterns Query
-- Purpose: Analyze buying behavior - basket size, frequency, time preferences
-- Output: Customer purchase behavior metrics
-- ============================================================================

WITH order_details AS (
    SELECT 
        fs.customer_key,
        fs.order_id,
        fs.date_key,
        fs.time_key,
        d.full_date,
        d.day_name,
        d.day_of_week,
        d.is_weekend,
        t.hour,
        t.day_period,
        fs.net_amount,
        fs.quantity
    FROM fact_sales fs
    JOIN dim_dates d ON fs.date_key = d.date_key
    LEFT JOIN dim_time t ON fs.time_key = t.time_key
),

customer_patterns AS (
    SELECT 
        c.customer_key,
        c.customer_id,
        c.email,
        c.first_name,
        c.last_name,
        COUNT(DISTINCT od.order_id) AS total_orders,
        ROUND(AVG(od.net_amount), 2) AS avg_basket_size,
        ROUND(MIN(od.net_amount), 2) AS min_basket_size,
        ROUND(MAX(od.net_amount), 2) AS max_basket_size,
        SUM(od.quantity) AS total_items_purchased,
        ROUND(AVG(od.quantity), 2) AS avg_items_per_order,
        -- Time preferences
        MODE(od.day_name) AS preferred_day,
        MODE(od.day_period) AS preferred_time_of_day,
        -- Weekend vs weekday
        SUM(CASE WHEN od.is_weekend THEN 1 ELSE 0 END) AS weekend_orders,
        SUM(CASE WHEN NOT od.is_weekend THEN 1 ELSE 0 END) AS weekday_orders,
        -- Purchase frequency
        MIN(od.full_date) AS first_purchase,
        MAX(od.full_date) AS last_purchase,
        DATEDIFF(day, MIN(od.full_date), MAX(od.full_date)) AS customer_lifespan_days
    FROM dim_customers c
    JOIN order_details od ON c.customer_key = od.customer_key
    WHERE c.is_current = TRUE
    GROUP BY c.customer_key, c.customer_id, c.email, c.first_name, c.last_name
)

SELECT 
    customer_key,
    customer_id,
    email,
    first_name,
    last_name,
    total_orders,
    avg_basket_size,
    min_basket_size,
    max_basket_size,
    total_items_purchased,
    avg_items_per_order,
    preferred_day,
    preferred_time_of_day,
    weekend_orders,
    weekday_orders,
    CASE 
        WHEN weekend_orders > weekday_orders THEN 'Weekend Shopper'
        WHEN weekday_orders > weekend_orders THEN 'Weekday Shopper'
        ELSE 'Balanced'
    END AS shopping_time_preference,
    first_purchase,
    last_purchase,
    customer_lifespan_days,
    CASE 
        WHEN customer_lifespan_days = 0 THEN NULL
        ELSE ROUND(customer_lifespan_days * 1.0 / NULLIF(total_orders - 1, 0), 1)
    END AS avg_days_between_orders,
    CASE 
        WHEN avg_basket_size >= 200 THEN 'High Basket'
        WHEN avg_basket_size >= 100 THEN 'Medium Basket'
        ELSE 'Low Basket'
    END AS basket_size_segment,
    CASE 
        WHEN total_orders >= 10 THEN 'Frequent Buyer'
        WHEN total_orders >= 5 THEN 'Regular Buyer'
        WHEN total_orders >= 2 THEN 'Occasional Buyer'
        ELSE 'One-Time Buyer'
    END AS frequency_segment
FROM customer_patterns
ORDER BY total_orders DESC, avg_basket_size DESC;
