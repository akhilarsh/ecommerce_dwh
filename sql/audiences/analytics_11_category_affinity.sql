-- ============================================================================
-- Category Affinity Audience
-- Purpose: Identify customer preferences by product category
-- Output: Category-based segments for targeted product recommendations
-- ============================================================================

WITH customer_category_purchases AS (
    SELECT 
        c.customer_key,
        c.customer_id,
        c.email,
        c.first_name,
        c.last_name,
        c.loyalty_tier,
        pc.category_key,
        pc.category_name,
        pc.subcategory_name,
        pc.category_path,
        COUNT(DISTINCT fs.order_id) AS orders_in_category,
        SUM(boi.quantity) AS items_in_category,
        SUM(boi.line_total) AS spend_in_category
    FROM fact_sales fs
    JOIN dim_customers c ON fs.customer_key = c.customer_key
    JOIN bridge_order_items boi ON fs.sale_key = boi.sale_key
    JOIN dim_products p ON boi.product_key = p.product_key
    JOIN dim_product_categories pc ON p.category_key = pc.category_key
    WHERE c.is_current = TRUE
    GROUP BY c.customer_key, c.customer_id, c.email, c.first_name, c.last_name,
             c.loyalty_tier, pc.category_key, pc.category_name, pc.subcategory_name, pc.category_path
),

customer_totals AS (
    SELECT 
        customer_key,
        SUM(orders_in_category) AS total_category_orders,
        SUM(spend_in_category) AS total_spend
    FROM customer_category_purchases
    GROUP BY customer_key
),

category_affinity AS (
    SELECT 
        ccp.customer_key,
        ccp.customer_id,
        ccp.email,
        ccp.first_name,
        ccp.last_name,
        ccp.loyalty_tier,
        ccp.category_name,
        ccp.subcategory_name,
        ccp.category_path,
        ccp.orders_in_category,
        ccp.items_in_category,
        ROUND(ccp.spend_in_category, 2) AS spend_in_category,
        ct.total_category_orders,
        ROUND(ct.total_spend, 2) AS total_spend,
        ROUND(ccp.spend_in_category * 100.0 / ct.total_spend, 1) AS category_spend_pct,
        ROW_NUMBER() OVER (PARTITION BY ccp.customer_key ORDER BY ccp.spend_in_category DESC) AS category_rank
    FROM customer_category_purchases ccp
    JOIN customer_totals ct ON ccp.customer_key = ct.customer_key
)

SELECT 
    customer_key,
    customer_id,
    email,
    first_name,
    last_name,
    loyalty_tier,
    category_name AS primary_category,
    subcategory_name AS primary_subcategory,
    category_path AS primary_category_path,
    orders_in_category AS primary_category_orders,
    items_in_category AS primary_category_items,
    spend_in_category AS primary_category_spend,
    total_spend,
    category_spend_pct AS primary_category_affinity_pct,
    'Category Affinity' AS audience_name,
    CASE 
        WHEN category_spend_pct >= 70 THEN 'Category Specialist'
        WHEN category_spend_pct >= 50 THEN 'Category Preferred'
        WHEN category_spend_pct >= 30 THEN 'Category Leaning'
        ELSE 'Category Diverse'
    END AS category_loyalty_type,
    -- Dynamic audience name based on top category
    category_name || ' Enthusiast' AS category_audience_name
FROM category_affinity
WHERE category_rank = 1
ORDER BY spend_in_category DESC;
