-- ============================================================================
-- Purchase Views
-- v_purchase_full: Denormalized - all customer, product, order attributes.
-- v_purchase: Slim - purchase relationship + product_key only. Join dim_products
--             for product details (customer -> view -> product pattern).
-- ============================================================================

-- Full denormalized view (one row per line item with all attributes)
CREATE OR REPLACE VIEW ecommerce_db.e_mart.v_purchase_full AS
SELECT
    fs.sale_key,
    fs.order_id,
    boi.order_item_key,
    boi.line_number,
    c.customer_key,
    c.customer_id,
    c.first_name,
    c.last_name,
    c.email,
    c.loyalty_tier,
    c.loyalty_program_member,
    dd.full_date AS order_date,
    dd.calendar_year,
    dd.quarter_number,
    dd.month_name,
    dd.week_of_year,
    dd.is_weekend,
    dd.is_holiday,
    t.time_value AS order_time,
    t.day_part AS order_day_part,
    p.product_key,
    p.product_id,
    p.sku,
    p.product_name,
    p.brand,
    pc.category_key,
    pc.category_name,
    pc.category_path,
    boi.quantity AS line_quantity,
    boi.unit_price,
    boi.discount_amount AS line_discount_amount,
    boi.line_total,
    boi.is_gift,
    boi.gift_message,
    fs.quantity AS order_total_items,
    fs.gross_amount,
    fs.discount_amount AS order_discount_amount,
    fs.net_amount,
    fs.tax_amount,
    fs.shipping_amount,
    fs.total_amount,
    fs.order_status,
    fs.is_online,
    ch.channel_name,
    ch.channel_type,
    st.store_name,
    st.city AS store_city,
    st.region AS store_region,
    prom.promotion_name,
    prom.promotion_type,
    prom.promotion_code,
    pm.payment_method_name,
    pm.payment_type,
    sm.shipping_method_name,
    sm.carrier AS shipping_carrier,
    emp.full_name AS sales_employee_name,
    lp.points_earned,
    fs.created_at AS order_created_at
FROM ecommerce_db.e_mart.fact_sales fs
JOIN ecommerce_db.e_mart.bridge_order_items boi ON fs.sale_key = boi.sale_key
JOIN ecommerce_db.e_mart.dim_customers c ON fs.customer_key = c.customer_key AND c.is_current = TRUE
JOIN ecommerce_db.e_mart.dim_products p ON boi.product_key = p.product_key AND p.is_current = TRUE
JOIN ecommerce_db.e_mart.dim_dates dd ON fs.date_key = dd.date_key
LEFT JOIN ecommerce_db.e_mart.dim_time t ON fs.time_key = t.time_key
LEFT JOIN ecommerce_db.e_mart.dim_channels ch ON fs.channel_key = ch.channel_key
LEFT JOIN ecommerce_db.e_mart.dim_stores st ON fs.store_key = st.store_key
LEFT JOIN ecommerce_db.e_mart.dim_promotions prom ON fs.promotion_key = prom.promotion_key
LEFT JOIN ecommerce_db.e_mart.dim_payment_methods pm ON fs.payment_method_key = pm.payment_method_key
LEFT JOIN ecommerce_db.e_mart.dim_shipping_methods sm ON fs.shipping_method_key = sm.shipping_method_key
LEFT JOIN ecommerce_db.e_mart.dim_employees emp ON fs.employee_key = emp.employee_key
LEFT JOIN ecommerce_db.e_mart.dim_product_categories pc ON p.category_key = pc.category_key
LEFT JOIN (
    SELECT sale_key, SUM(points) AS points_earned
    FROM ecommerce_db.e_mart.fact_loyalty_points
    WHERE transaction_type = 'Earned' AND sale_key IS NOT NULL
    GROUP BY sale_key
) lp ON fs.sale_key = lp.sale_key;;

-- Slim view: purchase relationship + product_key, join dim_products for attributes.
CREATE OR REPLACE VIEW ecommerce_db.e_mart.v_purchase AS
SELECT
    fs.sale_key,
    fs.order_id,
    boi.order_item_key,
    boi.line_number,
    boi.product_key,
    c.customer_key,
    c.customer_id,
    c.first_name,
    c.last_name,
    c.email,
    c.loyalty_tier,
    c.loyalty_program_member,
    dd.full_date AS order_date,
    dd.calendar_year,
    dd.quarter_number,
    dd.month_name,
    dd.week_of_year,
    dd.is_weekend,
    dd.is_holiday,
    t.time_value AS order_time,
    t.day_part AS order_day_part,
    boi.quantity AS line_quantity,
    boi.unit_price,
    boi.discount_amount AS line_discount_amount,
    boi.line_total,
    boi.is_gift,
    boi.gift_message,
    fs.quantity AS order_total_items,
    fs.gross_amount,
    fs.discount_amount AS order_discount_amount,
    fs.net_amount,
    fs.tax_amount,
    fs.shipping_amount,
    fs.total_amount,
    fs.order_status,
    fs.is_online,
    ch.channel_name,
    ch.channel_type,
    st.store_name,
    st.city AS store_city,
    st.region AS store_region,
    prom.promotion_name,
    prom.promotion_type,
    prom.promotion_code,
    pm.payment_method_name,
    pm.payment_type,
    sm.shipping_method_name,
    sm.carrier AS shipping_carrier,
    emp.full_name AS sales_employee_name,
    lp.points_earned,
    fs.created_at AS order_created_at
FROM ecommerce_db.e_mart.fact_sales fs
JOIN ecommerce_db.e_mart.bridge_order_items boi ON fs.sale_key = boi.sale_key
JOIN ecommerce_db.e_mart.dim_customers c ON fs.customer_key = c.customer_key AND c.is_current = TRUE
JOIN ecommerce_db.e_mart.dim_dates dd ON fs.date_key = dd.date_key
LEFT JOIN ecommerce_db.e_mart.dim_time t ON fs.time_key = t.time_key
LEFT JOIN ecommerce_db.e_mart.dim_channels ch ON fs.channel_key = ch.channel_key
LEFT JOIN ecommerce_db.e_mart.dim_stores st ON fs.store_key = st.store_key
LEFT JOIN ecommerce_db.e_mart.dim_promotions prom ON fs.promotion_key = prom.promotion_key
LEFT JOIN ecommerce_db.e_mart.dim_payment_methods pm ON fs.payment_method_key = pm.payment_method_key
LEFT JOIN ecommerce_db.e_mart.dim_shipping_methods sm ON fs.shipping_method_key = sm.shipping_method_key
LEFT JOIN ecommerce_db.e_mart.dim_employees emp ON fs.employee_key = emp.employee_key
LEFT JOIN (
    SELECT sale_key, SUM(points) AS points_earned
    FROM ecommerce_db.e_mart.fact_loyalty_points
    WHERE transaction_type = 'Earned' AND sale_key IS NOT NULL
    GROUP BY sale_key
) lp ON fs.sale_key = lp.sale_key;;
