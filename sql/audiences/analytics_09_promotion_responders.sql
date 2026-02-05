-- ============================================================================
-- Promotion Responders Audience
-- Purpose: Identify customers who purchased during promotions
-- Output: Promotion-responsive customers for campaign targeting
-- ============================================================================

WITH promotion_purchases AS (
    SELECT 
        c.customer_key,
        c.customer_id,
        c.email,
        c.first_name,
        c.last_name,
        c.loyalty_tier,
        p.promotion_key,
        p.promotion_name,
        p.promotion_type,
        p.discount_percent,
        d.full_date AS purchase_date,
        fs.order_id,
        fs.net_amount,
        fs.gross_amount,
        (fs.gross_amount - fs.net_amount) AS discount_amount
    FROM fact_sales fs
    JOIN dim_customers c ON fs.customer_key = c.customer_key
    JOIN dim_promotions p ON fs.promotion_key = p.promotion_key
    JOIN dim_dates d ON fs.date_key = d.date_key
    WHERE c.is_current = TRUE
      AND fs.promotion_key IS NOT NULL
),

customer_promo_stats AS (
    SELECT 
        customer_key,
        customer_id,
        email,
        first_name,
        last_name,
        loyalty_tier,
        COUNT(DISTINCT order_id) AS promo_orders,
        COUNT(DISTINCT promotion_key) AS unique_promos_used,
        SUM(net_amount) AS promo_spend,
        SUM(discount_amount) AS total_discount_received,
        MIN(purchase_date) AS first_promo_purchase,
        MAX(purchase_date) AS last_promo_purchase
    FROM promotion_purchases
    GROUP BY customer_key, customer_id, email, first_name, last_name, loyalty_tier
),

-- Get total orders for comparison
total_orders AS (
    SELECT 
        customer_key,
        COUNT(DISTINCT order_id) AS all_orders,
        SUM(net_amount) AS all_spend
    FROM fact_sales
    GROUP BY customer_key
)

SELECT 
    cps.customer_key,
    cps.customer_id,
    cps.email,
    cps.first_name,
    cps.last_name,
    cps.loyalty_tier,
    cps.promo_orders,
    cps.unique_promos_used,
    ROUND(cps.promo_spend, 2) AS promo_spend,
    ROUND(cps.total_discount_received, 2) AS total_discount_received,
    tol.all_orders AS total_orders,
    ROUND(tol.all_spend, 2) AS total_spend,
    ROUND(cps.promo_orders * 100.0 / tol.all_orders, 1) AS promo_order_pct,
    cps.first_promo_purchase,
    cps.last_promo_purchase,
    'Promotion Responder' AS audience_name,
    CASE 
        WHEN cps.promo_orders * 100.0 / tol.all_orders >= 75 THEN 'Deal Seeker'
        WHEN cps.promo_orders * 100.0 / tol.all_orders >= 50 THEN 'Promo Sensitive'
        WHEN cps.promo_orders * 100.0 / tol.all_orders >= 25 THEN 'Occasional Promo User'
        ELSE 'Promo Opportunist'
    END AS promo_behavior,
    CASE 
        WHEN cps.total_discount_received >= 500 THEN 'High Discount Beneficiary'
        WHEN cps.total_discount_received >= 200 THEN 'Medium Discount Beneficiary'
        ELSE 'Low Discount Beneficiary'
    END AS discount_segment
FROM customer_promo_stats cps
JOIN total_orders tol ON cps.customer_key = tol.customer_key
ORDER BY cps.promo_orders DESC, cps.total_discount_received DESC;
