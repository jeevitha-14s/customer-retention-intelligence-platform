-- Load Olist CSVs into the normalized MySQL schema.
-- Run after schema.sql from the repository root with LOCAL INFILE enabled:
-- mysql --local-infile=1 -u root -p < sql/schema.sql
-- mysql --local-infile=1 -u root -p customer_retention_intelligence < sql/load_data.sql

USE customer_retention_intelligence;
SET SESSION sql_mode = '';
SET FOREIGN_KEY_CHECKS = 0;

DROP TABLE IF EXISTS stg_customers;
DROP TABLE IF EXISTS stg_orders;
DROP TABLE IF EXISTS stg_order_items;
DROP TABLE IF EXISTS stg_products;
DROP TABLE IF EXISTS stg_category_translation;

CREATE TABLE stg_customers (
    customer_id VARCHAR(50),
    customer_unique_id VARCHAR(50),
    customer_zip_code_prefix INT,
    customer_city VARCHAR(100),
    customer_state CHAR(2)
);

CREATE TABLE stg_orders (
    order_id VARCHAR(50),
    customer_id VARCHAR(50),
    order_status VARCHAR(30),
    order_purchase_timestamp DATETIME NULL,
    order_approved_at DATETIME NULL,
    order_delivered_carrier_date DATETIME NULL,
    order_delivered_customer_date DATETIME NULL,
    order_estimated_delivery_date DATETIME NULL
);

CREATE TABLE stg_order_items (
    order_id VARCHAR(50),
    order_item_id INT,
    product_id VARCHAR(50),
    seller_id VARCHAR(50),
    shipping_limit_date DATETIME NULL,
    price DECIMAL(12,2),
    freight_value DECIMAL(12,2)
);

CREATE TABLE stg_products (
    product_id VARCHAR(50),
    product_category_name VARCHAR(100),
    product_name_lenght INT,
    product_description_lenght INT,
    product_photos_qty INT,
    product_weight_g INT,
    product_length_cm INT,
    product_height_cm INT,
    product_width_cm INT
);

CREATE TABLE stg_category_translation (
    product_category_name VARCHAR(100),
    product_category_name_english VARCHAR(100)
);

LOAD DATA LOCAL INFILE 'data/raw/olist_customers_dataset.csv'
INTO TABLE stg_customers
FIELDS TERMINATED BY ',' OPTIONALLY ENCLOSED BY '"'
LINES TERMINATED BY '\n'
IGNORE 1 ROWS;

LOAD DATA LOCAL INFILE 'data/raw/olist_orders_dataset.csv'
INTO TABLE stg_orders
FIELDS TERMINATED BY ',' OPTIONALLY ENCLOSED BY '"'
LINES TERMINATED BY '\n'
IGNORE 1 ROWS
(order_id, customer_id, order_status, @purchase_ts, @approved_at, @carrier_date, @delivered_date, @estimated_date)
SET
    order_purchase_timestamp = NULLIF(@purchase_ts, ''),
    order_approved_at = NULLIF(@approved_at, ''),
    order_delivered_carrier_date = NULLIF(@carrier_date, ''),
    order_delivered_customer_date = NULLIF(@delivered_date, ''),
    order_estimated_delivery_date = NULLIF(@estimated_date, '');

LOAD DATA LOCAL INFILE 'data/raw/olist_order_items_dataset.csv'
INTO TABLE stg_order_items
FIELDS TERMINATED BY ',' OPTIONALLY ENCLOSED BY '"'
LINES TERMINATED BY '\n'
IGNORE 1 ROWS
(order_id, order_item_id, product_id, seller_id, @shipping_limit_date, price, freight_value)
SET shipping_limit_date = NULLIF(@shipping_limit_date, '');

LOAD DATA LOCAL INFILE 'data/raw/olist_products_dataset.csv'
INTO TABLE stg_products
FIELDS TERMINATED BY ',' OPTIONALLY ENCLOSED BY '"'
LINES TERMINATED BY '\n'
IGNORE 1 ROWS;

LOAD DATA LOCAL INFILE 'data/raw/product_category_name_translation.csv'
INTO TABLE stg_category_translation
CHARACTER SET utf8mb4
FIELDS TERMINATED BY ',' OPTIONALLY ENCLOSED BY '"'
LINES TERMINATED BY '\n'
IGNORE 1 ROWS;

INSERT INTO customers (
    customer_unique_id,
    customer_city,
    customer_state,
    first_seen_date,
    last_seen_date,
    total_orders
)
SELECT
    c.customer_unique_id,
    MIN(c.customer_city) AS customer_city,
    MIN(c.customer_state) AS customer_state,
    DATE(MIN(o.order_purchase_timestamp)) AS first_seen_date,
    DATE(MAX(o.order_purchase_timestamp)) AS last_seen_date,
    COUNT(DISTINCT o.order_id) AS total_orders
FROM stg_customers c
LEFT JOIN stg_orders o
    ON c.customer_id = o.customer_id
GROUP BY c.customer_unique_id;

INSERT INTO products (
    product_id,
    product_category_name,
    product_category_english,
    product_name_length,
    product_description_length,
    product_photos_qty,
    product_weight_g,
    product_length_cm,
    product_height_cm,
    product_width_cm
)
SELECT
    p.product_id,
    p.product_category_name,
    COALESCE(t.product_category_name_english, p.product_category_name, 'unknown') AS product_category_english,
    p.product_name_lenght,
    p.product_description_lenght,
    p.product_photos_qty,
    p.product_weight_g,
    p.product_length_cm,
    p.product_height_cm,
    p.product_width_cm
FROM stg_products p
LEFT JOIN stg_category_translation t
    ON p.product_category_name = REPLACE(t.product_category_name, '\ufeff', '');

INSERT INTO orders (
    order_id,
    customer_id,
    customer_unique_id,
    order_status,
    order_purchase_timestamp,
    order_approved_at,
    order_delivered_carrier_date,
    order_delivered_customer_date,
    order_estimated_delivery_date,
    order_month,
    order_revenue,
    order_freight
)
SELECT
    o.order_id,
    o.customer_id,
    c.customer_unique_id,
    o.order_status,
    o.order_purchase_timestamp,
    o.order_approved_at,
    o.order_delivered_carrier_date,
    o.order_delivered_customer_date,
    o.order_estimated_delivery_date,
    DATE_FORMAT(o.order_purchase_timestamp, '%Y-%m-01') AS order_month,
    COALESCE(SUM(i.price), 0) AS order_revenue,
    COALESCE(SUM(i.freight_value), 0) AS order_freight
FROM stg_orders o
INNER JOIN stg_customers c
    ON o.customer_id = c.customer_id
LEFT JOIN stg_order_items i
    ON o.order_id = i.order_id
GROUP BY
    o.order_id,
    o.customer_id,
    c.customer_unique_id,
    o.order_status,
    o.order_purchase_timestamp,
    o.order_approved_at,
    o.order_delivered_carrier_date,
    o.order_delivered_customer_date,
    o.order_estimated_delivery_date;

INSERT INTO order_items (
    order_id,
    order_item_id,
    product_id,
    seller_id,
    shipping_limit_date,
    price,
    freight_value
)
SELECT
    i.order_id,
    i.order_item_id,
    i.product_id,
    i.seller_id,
    i.shipping_limit_date,
    i.price,
    i.freight_value
FROM stg_order_items i
INNER JOIN orders o
    ON i.order_id = o.order_id
INNER JOIN products p
    ON i.product_id = p.product_id;

SET FOREIGN_KEY_CHECKS = 1;

SELECT 'customers' AS table_name, COUNT(*) AS row_count FROM customers
UNION ALL
SELECT 'products', COUNT(*) FROM products
UNION ALL
SELECT 'orders', COUNT(*) FROM orders
UNION ALL
SELECT 'order_items', COUNT(*) FROM order_items;
