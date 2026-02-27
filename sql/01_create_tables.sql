CREATE TABLE IF NOT EXISTS ecommerce_db.e_mart.dim_dates (
  date_key NUMBER(38) NOT NULL COMMENT 'Surrogate key (YYYYMMDD format)',
  full_date DATE NOT NULL COMMENT 'Actual date',
  day_of_week NUMBER(1) NOT NULL COMMENT '1=Monday to 7=Sunday',
  day_name VARCHAR(10) NOT NULL COMMENT 'Monday, Tuesday, etc.',
  day_of_month NUMBER(2) NOT NULL COMMENT '1-31',
  day_of_year NUMBER(3) NOT NULL COMMENT '1-366',
  week_of_year NUMBER(2) NOT NULL COMMENT '1-53',
  month_number NUMBER(2) NOT NULL COMMENT '1-12',
  month_name VARCHAR(10) NOT NULL COMMENT 'January, February, etc.',
  month_abbr VARCHAR(3) NOT NULL COMMENT 'Jan, Feb, etc.',
  quarter_number NUMBER(1) NOT NULL COMMENT '1-4',
  calendar_year NUMBER(4) NOT NULL COMMENT 'Calendar year',
  is_weekend BOOLEAN NOT NULL DEFAULT FALSE COMMENT 'True if Saturday/Sunday',
  is_holiday BOOLEAN NOT NULL DEFAULT FALSE COMMENT 'True if public holiday',
  fiscal_year NUMBER(4) COMMENT 'Fiscal year (can differ from calendar)',
  fiscal_quarter NUMBER(1) COMMENT 'Fiscal quarter 1-4',
  PRIMARY KEY (date_key)
)
COMMENT = 'Date dimension with calendar attributes';;

CREATE TABLE IF NOT EXISTS ecommerce_db.e_mart.dim_time (
  time_key NUMBER(38) NOT NULL COMMENT 'Surrogate key (HHMM format)',
  time_value TIME NOT NULL COMMENT 'Actual time value',
  hour_24 NUMBER(2) NOT NULL COMMENT '0-23',
  minute_of_hour NUMBER(2) NOT NULL COMMENT '0-59',
  second_of_minute NUMBER(2) NOT NULL DEFAULT 0 COMMENT '0-59',
  am_pm VARCHAR(2) NOT NULL COMMENT 'AM or PM',
  hour_12 NUMBER(2) NOT NULL COMMENT '1-12 (12-hour format)',
  day_part VARCHAR(20) COMMENT 'Morning, Afternoon, Evening, Night',
  is_business_hours BOOLEAN NOT NULL DEFAULT FALSE COMMENT 'True if 9AM-5PM',
  is_peak_shopping BOOLEAN NOT NULL DEFAULT FALSE COMMENT 'True if peak shopping hours',
  PRIMARY KEY (time_key)
)
COMMENT = 'Time of day dimension with hourly/minute breakdown';;

CREATE TABLE IF NOT EXISTS ecommerce_db.e_mart.dim_channels (
  channel_key NUMBER(38) NOT NULL COMMENT 'Surrogate key',
  channel_id VARCHAR(50) NOT NULL COMMENT 'Business channel identifier',
  channel_name VARCHAR(100) NOT NULL COMMENT 'Web, In-Store, Mobile App, Call Center',
  channel_code VARCHAR(20) NOT NULL COMMENT 'Short code for channel',
  channel_type VARCHAR(50) COMMENT 'Digital, Physical, Hybrid',
  description VARCHAR(500) COMMENT 'Detailed description',
  is_active BOOLEAN NOT NULL DEFAULT TRUE COMMENT 'Channel currently active',
  created_at TIMESTAMP_NTZ NOT NULL COMMENT 'Record creation timestamp',
  updated_at TIMESTAMP_NTZ COMMENT 'Last update timestamp',
  PRIMARY KEY (channel_key)
)
COMMENT = 'Sales channels (online, in-store, mobile, etc.)';;

CREATE TABLE IF NOT EXISTS ecommerce_db.e_mart.dim_payment_methods (
  payment_method_key NUMBER(38) NOT NULL COMMENT 'Surrogate key',
  payment_method_id VARCHAR(50) NOT NULL COMMENT 'Business payment method identifier',
  payment_method_name VARCHAR(100) NOT NULL COMMENT 'Credit Card, Debit Card, Cash, PayPal, etc.',
  payment_method_code VARCHAR(20) NOT NULL COMMENT 'Short code for payment method',
  payment_type VARCHAR(50) COMMENT 'Card, Cash, Digital Wallet, Bank Transfer',
  is_active BOOLEAN NOT NULL DEFAULT TRUE COMMENT 'Payment method currently active',
  created_at TIMESTAMP_NTZ NOT NULL COMMENT 'Record creation timestamp',
  updated_at TIMESTAMP_NTZ COMMENT 'Last update timestamp',
  PRIMARY KEY (payment_method_key)
)
COMMENT = 'Payment methods (credit, debit, cash, digital wallet, etc.)';;

CREATE TABLE IF NOT EXISTS ecommerce_db.e_mart.dim_shipping_methods (
  shipping_method_key NUMBER(38) NOT NULL COMMENT 'Surrogate key',
  shipping_method_id VARCHAR(50) NOT NULL COMMENT 'Business shipping method identifier',
  shipping_method_name VARCHAR(100) NOT NULL COMMENT 'Standard, Express, Same Day, In-Store Pickup',
  shipping_method_code VARCHAR(20) NOT NULL COMMENT 'Short code for shipping method',
  carrier VARCHAR(100) COMMENT 'Shipping carrier (FedEx, UPS, USPS, etc.)',
  estimated_days_min NUMBER(3) COMMENT 'Minimum delivery days',
  estimated_days_max NUMBER(3) COMMENT 'Maximum delivery days',
  base_cost NUMBER(10,2) COMMENT 'Base shipping cost',
  is_active BOOLEAN NOT NULL DEFAULT TRUE COMMENT 'Shipping method currently active',
  created_at TIMESTAMP_NTZ NOT NULL COMMENT 'Record creation timestamp',
  updated_at TIMESTAMP_NTZ COMMENT 'Last update timestamp',
  PRIMARY KEY (shipping_method_key)
)
COMMENT = 'Shipping and fulfillment methods';;

CREATE TABLE IF NOT EXISTS ecommerce_db.e_mart.dim_customer_segments (
  segment_key NUMBER(38) NOT NULL COMMENT 'Surrogate key',
  segment_id VARCHAR(50) NOT NULL COMMENT 'Business segment identifier',
  segment_name VARCHAR(100) NOT NULL COMMENT 'VIP, High Value, Regular, New Customer, At Risk',
  segment_code VARCHAR(20) NOT NULL COMMENT 'Short code for segment',
  description VARCHAR(500) COMMENT 'Detailed segment description',
  min_lifetime_value NUMBER(12,2) COMMENT 'Minimum LTV for this segment',
  max_lifetime_value NUMBER(12,2) COMMENT 'Maximum LTV for this segment',
  is_active BOOLEAN NOT NULL DEFAULT TRUE COMMENT 'Segment currently active',
  created_at TIMESTAMP_NTZ NOT NULL COMMENT 'Record creation timestamp',
  updated_at TIMESTAMP_NTZ COMMENT 'Last update timestamp',
  PRIMARY KEY (segment_key)
)
COMMENT = 'Customer segmentation groups (VIP, Regular, New, etc.)';;

CREATE TABLE IF NOT EXISTS ecommerce_db.e_mart.dim_product_categories (
  category_key NUMBER(38) NOT NULL COMMENT 'Surrogate key',
  category_id VARCHAR(50) NOT NULL COMMENT 'Business category identifier',
  category_name VARCHAR(100) NOT NULL COMMENT 'Category name',
  category_level NUMBER(1) COMMENT 'Hierarchy level (1=Category, 2=Subcategory, 3=Brand)',
  parent_category_key NUMBER(38) COMMENT 'Parent category for hierarchy navigation',
  category_path VARCHAR(500) COMMENT 'Full hierarchy path (e.g., Electronics > Phones > Apple)',
  is_active BOOLEAN NOT NULL DEFAULT TRUE COMMENT 'Category currently active',
  created_at TIMESTAMP_NTZ NOT NULL COMMENT 'Record creation timestamp',
  updated_at TIMESTAMP_NTZ COMMENT 'Last update timestamp',
  PRIMARY KEY (category_key)
)
COMMENT = 'Product category hierarchy';;

CREATE TABLE IF NOT EXISTS ecommerce_db.e_mart.dim_promotions (
  promotion_key NUMBER(38) NOT NULL COMMENT 'Surrogate key',
  promotion_id VARCHAR(50) NOT NULL COMMENT 'Business promotion identifier',
  promotion_name VARCHAR(200) NOT NULL COMMENT 'Promotion campaign name',
  promotion_type VARCHAR(50) COMMENT 'Percentage, Fixed Amount, BOGO, Free Shipping',
  promotion_code VARCHAR(50) COMMENT 'Promo code for redemption',
  start_date DATE NOT NULL COMMENT 'Promotion start date',
  end_date DATE NOT NULL COMMENT 'Promotion end date',
  discount_percentage NUMBER(5,2) COMMENT 'Discount percentage (0-100)',
  discount_amount NUMBER(10,2) COMMENT 'Fixed discount amount',
  min_purchase_amount NUMBER(10,2) COMMENT 'Minimum purchase required',
  max_discount_amount NUMBER(10,2) COMMENT 'Maximum discount cap',
  is_stackable BOOLEAN NOT NULL DEFAULT FALSE COMMENT 'Can combine with other promotions',
  is_active BOOLEAN NOT NULL DEFAULT TRUE COMMENT 'Promotion currently active',
  created_at TIMESTAMP_NTZ NOT NULL COMMENT 'Record creation timestamp',
  updated_at TIMESTAMP_NTZ COMMENT 'Last update timestamp',
  PRIMARY KEY (promotion_key)
)
COMMENT = 'Marketing promotions and campaigns';;

CREATE TABLE IF NOT EXISTS ecommerce_db.e_mart.dim_stores (
  store_key NUMBER(38) NOT NULL COMMENT 'Surrogate key',
  store_id VARCHAR(50) NOT NULL COMMENT 'Business store identifier',
  store_name VARCHAR(200) NOT NULL COMMENT 'Store name',
  store_type VARCHAR(50) COMMENT 'Flagship, Mall, Outlet, Warehouse',
  address_line1 VARCHAR(500) COMMENT 'Street address line 1',
  address_line2 VARCHAR(500) COMMENT 'Street address line 2',
  city VARCHAR(100) COMMENT 'City',
  state VARCHAR(50) COMMENT 'State/Province',
  postal_code VARCHAR(20) COMMENT 'ZIP/Postal code',
  country VARCHAR(100) NOT NULL COMMENT 'Country',
  region VARCHAR(100) COMMENT 'Geographic region',
  phone_number VARCHAR(20) COMMENT 'Store phone number',
  email VARCHAR(200) COMMENT 'Store email address',
  opening_date DATE COMMENT 'Store opening date',
  closing_date DATE COMMENT 'Store closing date (if closed)',
  square_footage NUMBER(10) COMMENT 'Store size in square feet',
  is_active BOOLEAN NOT NULL DEFAULT TRUE COMMENT 'Store currently active',
  latitude NUMBER(10,6) COMMENT 'Geographic latitude',
  longitude NUMBER(10,6) COMMENT 'Geographic longitude',
  created_at TIMESTAMP_NTZ NOT NULL COMMENT 'Record creation timestamp',
  updated_at TIMESTAMP_NTZ COMMENT 'Last update timestamp',
  PRIMARY KEY (store_key)
)
COMMENT = 'Physical store locations';;

CREATE TABLE IF NOT EXISTS ecommerce_db.e_mart.dim_products (
  product_key NUMBER(38) NOT NULL COMMENT 'Surrogate key',
  product_id VARCHAR(50) NOT NULL COMMENT 'Business product identifier (natural key)',
  sku VARCHAR(100) NOT NULL COMMENT 'Stock Keeping Unit',
  product_name VARCHAR(500) NOT NULL COMMENT 'Product name',
  brand VARCHAR(100) COMMENT 'Product brand',
  category_key NUMBER(38) COMMENT 'FK to dim_product_categories',
  description VARCHAR(2000) COMMENT 'Detailed product description',
  unit_price NUMBER(10,2) NOT NULL COMMENT 'Retail price',
  unit_cost NUMBER(10,2) COMMENT 'Product cost',
  weight_kg NUMBER(10,2) COMMENT 'Product weight in kg',
  is_active BOOLEAN NOT NULL DEFAULT TRUE COMMENT 'Product currently active',
  is_discontinued BOOLEAN NOT NULL DEFAULT FALSE COMMENT 'Product discontinued',
  effective_date DATE NOT NULL COMMENT 'SCD effective start date',
  end_date DATE COMMENT 'SCD effective end date (NULL = current)',
  is_current BOOLEAN NOT NULL DEFAULT TRUE COMMENT 'Current version flag',
  created_at TIMESTAMP_NTZ NOT NULL COMMENT 'Record creation timestamp',
  updated_at TIMESTAMP_NTZ COMMENT 'Last update timestamp',
  PRIMARY KEY (product_key)
)
COMMENT = 'Product catalog with historical tracking (SCD Type 2)';;

CREATE TABLE IF NOT EXISTS ecommerce_db.e_mart.dim_customers (
  customer_key NUMBER(38) NOT NULL COMMENT 'Surrogate key',
  customer_id VARCHAR(50) NOT NULL COMMENT 'Business customer identifier (natural key)',
  first_name VARCHAR(100) NOT NULL COMMENT 'Customer first name',
  last_name VARCHAR(100) NOT NULL COMMENT 'Customer last name',
  full_name VARCHAR(200) COMMENT 'Full name (first + last)',
  email VARCHAR(200) COMMENT 'Customer email address',
  phone_number VARCHAR(20) COMMENT 'Customer phone number',
  birth_date DATE COMMENT 'Customer date of birth',
  gender VARCHAR(20) COMMENT 'M, F, Other, Prefer not to say',
  address_line1 VARCHAR(500) COMMENT 'Street address line 1',
  address_line2 VARCHAR(500) COMMENT 'Street address line 2',
  city VARCHAR(100) COMMENT 'City',
  state VARCHAR(50) COMMENT 'State/Province',
  postal_code VARCHAR(20) COMMENT 'ZIP/Postal code',
  country VARCHAR(100) COMMENT 'Country',
  registration_date DATE NOT NULL COMMENT 'Customer registration date',
  segment_key NUMBER(38) COMMENT 'FK to dim_customer_segments',
  preferred_channel VARCHAR(50) COMMENT 'Preferred shopping channel',
  loyalty_program_member BOOLEAN NOT NULL DEFAULT FALSE COMMENT 'Member of loyalty program',
  loyalty_tier VARCHAR(50) COMMENT 'Bronze, Silver, Gold, Platinum',
  loyalty_points_balance NUMBER(10) COMMENT 'Current loyalty points balance',
  lifetime_value NUMBER(12,2) COMMENT 'Total lifetime purchase value',
  is_active BOOLEAN NOT NULL DEFAULT TRUE COMMENT 'Customer account active',
  effective_date DATE NOT NULL COMMENT 'SCD effective start date',
  end_date DATE COMMENT 'SCD effective end date (NULL = current)',
  is_current BOOLEAN NOT NULL DEFAULT TRUE COMMENT 'Current version flag',
  created_at TIMESTAMP_NTZ NOT NULL COMMENT 'Record creation timestamp',
  updated_at TIMESTAMP_NTZ COMMENT 'Last update timestamp',
  PRIMARY KEY (customer_key)
)
COMMENT = 'Customer master data with historical tracking (SCD Type 2)';;

CREATE TABLE IF NOT EXISTS ecommerce_db.e_mart.dim_employees (
  employee_key NUMBER(38) NOT NULL COMMENT 'Surrogate key',
  employee_id VARCHAR(50) NOT NULL COMMENT 'Business employee identifier',
  first_name VARCHAR(100) NOT NULL COMMENT 'Employee first name',
  last_name VARCHAR(100) NOT NULL COMMENT 'Employee last name',
  full_name VARCHAR(200) COMMENT 'Full name (first + last)',
  email VARCHAR(200) COMMENT 'Employee email address',
  phone_number VARCHAR(20) COMMENT 'Employee phone number',
  position VARCHAR(100) COMMENT 'Sales Associate, Store Manager, etc.',
  department VARCHAR(100) COMMENT 'Department name',
  store_key NUMBER(38) COMMENT 'Associated store (FK to dim_stores)',
  hire_date DATE COMMENT 'Employee hire date',
  termination_date DATE COMMENT 'Employee termination date (if terminated)',
  salary NUMBER(12,2) COMMENT 'Annual salary',
  is_active BOOLEAN NOT NULL DEFAULT TRUE COMMENT 'Employee currently active',
  created_at TIMESTAMP_NTZ NOT NULL COMMENT 'Record creation timestamp',
  updated_at TIMESTAMP_NTZ COMMENT 'Last update timestamp',
  PRIMARY KEY (employee_key)
)
COMMENT = 'Store employees and sales associates';;

CREATE TABLE IF NOT EXISTS ecommerce_db.e_mart.fact_sales (
  sale_key NUMBER(38) NOT NULL COMMENT 'Surrogate key for each sale transaction',
  order_id VARCHAR(50) NOT NULL COMMENT 'Business order identifier',
  date_key NUMBER(38) NOT NULL COMMENT 'FK to dim_dates',
  time_key NUMBER(38) COMMENT 'FK to dim_time',
  customer_key NUMBER(38) NOT NULL COMMENT 'FK to dim_customers',
  store_key NUMBER(38) COMMENT 'FK to dim_stores (NULL for online orders)',
  channel_key NUMBER(38) NOT NULL COMMENT 'FK to dim_channels',
  promotion_key NUMBER(38) COMMENT 'FK to dim_promotions (NULL if no promotion)',
  payment_method_key NUMBER(38) NOT NULL COMMENT 'FK to dim_payment_methods',
  shipping_method_key NUMBER(38) COMMENT 'FK to dim_shipping_methods',
  employee_key NUMBER(38) COMMENT 'FK to dim_employees (NULL for online orders)',
  quantity NUMBER(10) NOT NULL COMMENT 'Total items in order',
  gross_amount NUMBER(15,2) NOT NULL COMMENT 'Order total before discounts',
  discount_amount NUMBER(15,2) DEFAULT 0 COMMENT 'Total discount applied',
  net_amount NUMBER(15,2) NOT NULL COMMENT 'Amount after discount (gross - discount)',
  tax_amount NUMBER(15,2) DEFAULT 0 COMMENT 'Sales tax',
  shipping_amount NUMBER(15,2) DEFAULT 0 COMMENT 'Shipping charges',
  total_amount NUMBER(15,2) NOT NULL COMMENT 'Final order total (net + tax + shipping)',
  order_status VARCHAR(50) COMMENT 'Completed, Cancelled, Returned, Pending',
  is_online BOOLEAN NOT NULL DEFAULT FALSE COMMENT 'Online order flag',
  created_at TIMESTAMP_NTZ NOT NULL COMMENT 'Record creation timestamp',
  PRIMARY KEY (sale_key)
)
COMMENT = 'Core sales transactions fact table'
CLUSTER BY (date_key, customer_key);;

CREATE TABLE IF NOT EXISTS ecommerce_db.e_mart.fact_inventory_snapshots (
  inventory_snapshot_key NUMBER(38) NOT NULL COMMENT 'Surrogate key',
  date_key NUMBER(38) NOT NULL COMMENT 'FK to dim_dates',
  product_key NUMBER(38) NOT NULL COMMENT 'FK to dim_products',
  store_key NUMBER(38) COMMENT 'FK to dim_stores (NULL for warehouse/online inventory)',
  quantity_on_hand NUMBER(10) NOT NULL COMMENT 'Current inventory quantity',
  quantity_reserved NUMBER(10) DEFAULT 0 COMMENT 'Quantity reserved for pending orders',
  quantity_available NUMBER(10) NOT NULL COMMENT 'Available for sale (on_hand - reserved)',
  reorder_point NUMBER(10) COMMENT 'Minimum quantity before reorder',
  is_below_reorder_point BOOLEAN NOT NULL DEFAULT FALSE COMMENT 'True if below reorder point',
  days_of_supply NUMBER(5,1) COMMENT 'Estimated days until stockout',
  created_at TIMESTAMP_NTZ NOT NULL COMMENT 'Record creation timestamp',
  PRIMARY KEY (inventory_snapshot_key)
)
COMMENT = 'Daily inventory levels by product and location'
CLUSTER BY (date_key, product_key);;

CREATE TABLE IF NOT EXISTS ecommerce_db.e_mart.fact_customer_interactions (
  interaction_key NUMBER(38) NOT NULL COMMENT 'Surrogate key',
  interaction_id VARCHAR(50) NOT NULL COMMENT 'Business interaction identifier',
  date_key NUMBER(38) NOT NULL COMMENT 'FK to dim_dates',
  time_key NUMBER(38) COMMENT 'FK to dim_time',
  customer_key NUMBER(38) NOT NULL COMMENT 'FK to dim_customers',
  channel_key NUMBER(38) NOT NULL COMMENT 'FK to dim_channels',
  store_key NUMBER(38) COMMENT 'FK to dim_stores (for in-store interactions)',
  employee_key NUMBER(38) COMMENT 'FK to dim_employees (if assisted)',
  product_key NUMBER(38) COMMENT 'FK to dim_products (if product-related)',
  sale_key NUMBER(38) COMMENT 'FK to fact_sales if purchase made',
  interaction_type VARCHAR(100) NOT NULL COMMENT 'Website Visit, Store Visit, Support Call, Email, Chat',
  device_type VARCHAR(50) COMMENT 'Desktop, Mobile, Tablet, In-Store',
  session_id VARCHAR(100) COMMENT 'Session identifier for web visits',
  page_url VARCHAR(1000) COMMENT 'Page URL for web visits',
  duration_seconds NUMBER(10) COMMENT 'Duration of interaction in seconds',
  is_converted BOOLEAN NOT NULL DEFAULT FALSE COMMENT 'Did interaction result in purchase',
  created_at TIMESTAMP_NTZ NOT NULL COMMENT 'Record creation timestamp',
  PRIMARY KEY (interaction_key)
)
COMMENT = 'Customer touchpoints and interactions'
CLUSTER BY (date_key, customer_key);;

CREATE TABLE IF NOT EXISTS ecommerce_db.e_mart.fact_loyalty_points (
  loyalty_transaction_key NUMBER(38) NOT NULL COMMENT 'Surrogate key',
  transaction_id VARCHAR(50) NOT NULL COMMENT 'Business transaction identifier',
  date_key NUMBER(38) NOT NULL COMMENT 'FK to dim_dates',
  time_key NUMBER(38) COMMENT 'FK to dim_time',
  customer_key NUMBER(38) NOT NULL COMMENT 'FK to dim_customers',
  sale_key NUMBER(38) COMMENT 'FK to fact_sales (if points from purchase)',
  channel_key NUMBER(38) COMMENT 'FK to dim_channels',
  transaction_type VARCHAR(50) NOT NULL COMMENT 'Earned, Redeemed, Expired, Adjusted, Bonus',
  points NUMBER(10) NOT NULL COMMENT 'Point amount (positive for earned, negative for redeemed)',
  points_balance_after NUMBER(10) COMMENT 'Customer point balance after transaction',
  description VARCHAR(500) COMMENT 'Description of transaction',
  expiration_date DATE COMMENT 'When these points will expire',
  created_at TIMESTAMP_NTZ NOT NULL COMMENT 'Record creation timestamp',
  PRIMARY KEY (loyalty_transaction_key)
)
COMMENT = 'Loyalty program point transactions'
CLUSTER BY (date_key, customer_key);;

CREATE TABLE IF NOT EXISTS ecommerce_db.e_mart.bridge_order_items (
  order_item_key NUMBER(38) NOT NULL COMMENT 'Surrogate key for each line item',
  sale_key NUMBER(38) NOT NULL COMMENT 'FK to fact_sales',
  product_key NUMBER(38) NOT NULL COMMENT 'FK to dim_products',
  line_number NUMBER(5) NOT NULL COMMENT 'Line number within order',
  quantity NUMBER(10) NOT NULL COMMENT 'Quantity of this product in order',
  unit_price NUMBER(10,2) NOT NULL COMMENT 'Unit price at time of sale',
  discount_amount NUMBER(10,2) DEFAULT 0 COMMENT 'Discount applied to this line item',
  line_total NUMBER(15,2) NOT NULL COMMENT 'Line total (quantity * unit_price - discount)',
  is_gift BOOLEAN NOT NULL DEFAULT FALSE COMMENT 'Item is a gift',
  gift_message VARCHAR(500) COMMENT 'Gift message',
  created_at TIMESTAMP_NTZ NOT NULL COMMENT 'Record creation timestamp',
  PRIMARY KEY (order_item_key)
)
COMMENT = 'Order line items - links orders to products'
CLUSTER BY (sale_key, product_key);;

CREATE TABLE IF NOT EXISTS ecommerce_db.e_mart.bridge_product_promotions (
  product_promotion_key NUMBER(38) NOT NULL COMMENT 'Surrogate key',
  product_key NUMBER(38) NOT NULL COMMENT 'FK to dim_products',
  promotion_key NUMBER(38) NOT NULL COMMENT 'FK to dim_promotions',
  is_featured BOOLEAN NOT NULL DEFAULT FALSE COMMENT 'Product is featured in promotion',
  priority NUMBER(3) COMMENT 'Promotion priority if multiple apply',
  created_at TIMESTAMP_NTZ NOT NULL COMMENT 'Record creation timestamp',
  PRIMARY KEY (product_promotion_key)
)
COMMENT = 'Links products to applicable promotions'
CLUSTER BY (product_key, promotion_key);