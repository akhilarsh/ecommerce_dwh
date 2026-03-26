-- ============================================================================
-- Fetch purchase data from v_purchase (slim view)
-- Purpose: Query v_purchase and join dim_products for product details.
--          Demonstrates customer -> v_purchase -> dim_products pattern.
-- Usage: dwh run-sql sql/07_select_v_purchase.sql
-- ============================================================================

USE DATABASE ecommerce_db;
USE SCHEMA e_mart;

SELECT
    vp.sale_key,
    vp.order_id,
    vp.order_item_key,
    vp.line_number,
    vp.customer_key,
    vp.customer_id,
    vp.first_name,
    vp.last_name,
    vp.email,
    vp.loyalty_tier,
    vp.order_date,
    vp.calendar_year,
    vp.quarter_number,
    vp.month_name,
    vp.product_key,
    p.product_id,
    p.sku,
    p.product_name,
    p.brand,
    pc.category_name,
    vp.line_quantity,
    vp.unit_price,
    vp.line_discount_amount,
    vp.line_total,
    vp.order_total_items,
    vp.gross_amount,
    vp.net_amount,
    vp.total_amount,
    vp.order_status,
    vp.is_online,
    vp.channel_name,
    vp.store_name,
    vp.promotion_name,
    vp.payment_method_name,
    vp.shipping_method_name,
    vp.points_earned,
    vp.order_created_at
FROM ecommerce_db.e_mart.v_purchase vp
JOIN ecommerce_db.e_mart.dim_products p ON vp.product_key = p.product_key AND p.is_current = TRUE
LEFT JOIN ecommerce_db.e_mart.dim_product_categories pc ON p.category_key = pc.category_key
ORDER BY vp.order_date DESC, vp.sale_key, vp.line_number
LIMIT 1000;
