ALTER TABLE ecommerce_db.e_mart.dim_products ADD CONSTRAINT fk_dim_products_category_key FOREIGN KEY (category_key) REFERENCES ecommerce_db.e_mart.dim_product_categories(category_key);;

ALTER TABLE ecommerce_db.e_mart.dim_customers ADD CONSTRAINT fk_dim_customers_segment_key FOREIGN KEY (segment_key) REFERENCES ecommerce_db.e_mart.dim_customer_segments(segment_key);;

ALTER TABLE ecommerce_db.e_mart.dim_employees ADD CONSTRAINT fk_dim_employees_store_key FOREIGN KEY (store_key) REFERENCES ecommerce_db.e_mart.dim_stores(store_key);;

ALTER TABLE ecommerce_db.e_mart.fact_sales ADD CONSTRAINT fk_fact_sales_date_key FOREIGN KEY (date_key) REFERENCES ecommerce_db.e_mart.dim_dates(date_key);;

ALTER TABLE ecommerce_db.e_mart.fact_sales ADD CONSTRAINT fk_fact_sales_time_key FOREIGN KEY (time_key) REFERENCES ecommerce_db.e_mart.dim_time(time_key);;

ALTER TABLE ecommerce_db.e_mart.fact_sales ADD CONSTRAINT fk_fact_sales_customer_key FOREIGN KEY (customer_key) REFERENCES ecommerce_db.e_mart.dim_customers(customer_key);;

ALTER TABLE ecommerce_db.e_mart.fact_sales ADD CONSTRAINT fk_fact_sales_store_key FOREIGN KEY (store_key) REFERENCES ecommerce_db.e_mart.dim_stores(store_key);;

ALTER TABLE ecommerce_db.e_mart.fact_sales ADD CONSTRAINT fk_fact_sales_channel_key FOREIGN KEY (channel_key) REFERENCES ecommerce_db.e_mart.dim_channels(channel_key);;

ALTER TABLE ecommerce_db.e_mart.fact_sales ADD CONSTRAINT fk_fact_sales_promotion_key FOREIGN KEY (promotion_key) REFERENCES ecommerce_db.e_mart.dim_promotions(promotion_key);;

ALTER TABLE ecommerce_db.e_mart.fact_sales ADD CONSTRAINT fk_fact_sales_payment_method_key FOREIGN KEY (payment_method_key) REFERENCES ecommerce_db.e_mart.dim_payment_methods(payment_method_key);;

ALTER TABLE ecommerce_db.e_mart.fact_sales ADD CONSTRAINT fk_fact_sales_shipping_method_key FOREIGN KEY (shipping_method_key) REFERENCES ecommerce_db.e_mart.dim_shipping_methods(shipping_method_key);;

ALTER TABLE ecommerce_db.e_mart.fact_sales ADD CONSTRAINT fk_fact_sales_employee_key FOREIGN KEY (employee_key) REFERENCES ecommerce_db.e_mart.dim_employees(employee_key);;

ALTER TABLE ecommerce_db.e_mart.fact_inventory_snapshots ADD CONSTRAINT fk_fact_inventory_snapshots_date_key FOREIGN KEY (date_key) REFERENCES ecommerce_db.e_mart.dim_dates(date_key);;

ALTER TABLE ecommerce_db.e_mart.fact_inventory_snapshots ADD CONSTRAINT fk_fact_inventory_snapshots_product_key FOREIGN KEY (product_key) REFERENCES ecommerce_db.e_mart.dim_products(product_key);;

ALTER TABLE ecommerce_db.e_mart.fact_inventory_snapshots ADD CONSTRAINT fk_fact_inventory_snapshots_store_key FOREIGN KEY (store_key) REFERENCES ecommerce_db.e_mart.dim_stores(store_key);;

ALTER TABLE ecommerce_db.e_mart.fact_customer_interactions ADD CONSTRAINT fk_fact_customer_interactions_date_key FOREIGN KEY (date_key) REFERENCES ecommerce_db.e_mart.dim_dates(date_key);;

ALTER TABLE ecommerce_db.e_mart.fact_customer_interactions ADD CONSTRAINT fk_fact_customer_interactions_time_key FOREIGN KEY (time_key) REFERENCES ecommerce_db.e_mart.dim_time(time_key);;

ALTER TABLE ecommerce_db.e_mart.fact_customer_interactions ADD CONSTRAINT fk_fact_customer_interactions_customer_key FOREIGN KEY (customer_key) REFERENCES ecommerce_db.e_mart.dim_customers(customer_key);;

ALTER TABLE ecommerce_db.e_mart.fact_customer_interactions ADD CONSTRAINT fk_fact_customer_interactions_channel_key FOREIGN KEY (channel_key) REFERENCES ecommerce_db.e_mart.dim_channels(channel_key);;

ALTER TABLE ecommerce_db.e_mart.fact_customer_interactions ADD CONSTRAINT fk_fact_customer_interactions_store_key FOREIGN KEY (store_key) REFERENCES ecommerce_db.e_mart.dim_stores(store_key);;

ALTER TABLE ecommerce_db.e_mart.fact_customer_interactions ADD CONSTRAINT fk_fact_customer_interactions_employee_key FOREIGN KEY (employee_key) REFERENCES ecommerce_db.e_mart.dim_employees(employee_key);;

ALTER TABLE ecommerce_db.e_mart.fact_customer_interactions ADD CONSTRAINT fk_fact_customer_interactions_product_key FOREIGN KEY (product_key) REFERENCES ecommerce_db.e_mart.dim_products(product_key);;

ALTER TABLE ecommerce_db.e_mart.fact_customer_interactions ADD CONSTRAINT fk_fact_customer_interactions_sale_key FOREIGN KEY (sale_key) REFERENCES ecommerce_db.e_mart.fact_sales(sale_key);;

ALTER TABLE ecommerce_db.e_mart.fact_loyalty_points ADD CONSTRAINT fk_fact_loyalty_points_date_key FOREIGN KEY (date_key) REFERENCES ecommerce_db.e_mart.dim_dates(date_key);;

ALTER TABLE ecommerce_db.e_mart.fact_loyalty_points ADD CONSTRAINT fk_fact_loyalty_points_time_key FOREIGN KEY (time_key) REFERENCES ecommerce_db.e_mart.dim_time(time_key);;

ALTER TABLE ecommerce_db.e_mart.fact_loyalty_points ADD CONSTRAINT fk_fact_loyalty_points_customer_key FOREIGN KEY (customer_key) REFERENCES ecommerce_db.e_mart.dim_customers(customer_key);;

ALTER TABLE ecommerce_db.e_mart.fact_loyalty_points ADD CONSTRAINT fk_fact_loyalty_points_sale_key FOREIGN KEY (sale_key) REFERENCES ecommerce_db.e_mart.fact_sales(sale_key);;

ALTER TABLE ecommerce_db.e_mart.fact_loyalty_points ADD CONSTRAINT fk_fact_loyalty_points_channel_key FOREIGN KEY (channel_key) REFERENCES ecommerce_db.e_mart.dim_channels(channel_key);;

ALTER TABLE ecommerce_db.e_mart.bridge_order_items ADD CONSTRAINT fk_bridge_order_items_sale_key FOREIGN KEY (sale_key) REFERENCES ecommerce_db.e_mart.fact_sales(sale_key);;

ALTER TABLE ecommerce_db.e_mart.bridge_order_items ADD CONSTRAINT fk_bridge_order_items_product_key FOREIGN KEY (product_key) REFERENCES ecommerce_db.e_mart.dim_products(product_key);;

ALTER TABLE ecommerce_db.e_mart.bridge_product_promotions ADD CONSTRAINT fk_bridge_product_promotions_product_key FOREIGN KEY (product_key) REFERENCES ecommerce_db.e_mart.dim_products(product_key);;

ALTER TABLE ecommerce_db.e_mart.bridge_product_promotions ADD CONSTRAINT fk_bridge_product_promotions_promotion_key FOREIGN KEY (promotion_key) REFERENCES ecommerce_db.e_mart.dim_promotions(promotion_key);