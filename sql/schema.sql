-- Customer Retention Intelligence Platform
-- Normalized MySQL schema for Olist ecommerce retention analytics.

DROP DATABASE IF EXISTS customer_retention_intelligence;
CREATE DATABASE customer_retention_intelligence;
USE customer_retention_intelligence;

DROP TABLE IF EXISTS order_items;
DROP TABLE IF EXISTS order_reviews;
DROP TABLE IF EXISTS orders;
DROP TABLE IF EXISTS products;
DROP TABLE IF EXISTS customers;

CREATE TABLE customers (
    customer_unique_id VARCHAR(50) PRIMARY KEY,
    customer_city VARCHAR(100),
    customer_state CHAR(2),
    first_seen_date DATE,
    last_seen_date DATE,
    total_orders INT DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE products (
    product_id VARCHAR(50) PRIMARY KEY,
    product_category_name VARCHAR(100),
    product_category_english VARCHAR(100),
    product_name_length INT,
    product_description_length INT,
    product_photos_qty INT,
    product_weight_g INT,
    product_length_cm INT,
    product_height_cm INT,
    product_width_cm INT
);

CREATE TABLE orders (
    order_id VARCHAR(50) PRIMARY KEY,
    customer_id VARCHAR(50) NOT NULL,
    customer_unique_id VARCHAR(50) NOT NULL,
    order_status VARCHAR(30),
    order_purchase_timestamp DATETIME,
    order_approved_at DATETIME,
    order_delivered_carrier_date DATETIME,
    order_delivered_customer_date DATETIME,
    order_estimated_delivery_date DATETIME,
    order_month DATE,
    order_revenue DECIMAL(12,2) DEFAULT 0,
    order_freight DECIMAL(12,2) DEFAULT 0,
    FOREIGN KEY (customer_unique_id) REFERENCES customers(customer_unique_id),
    INDEX idx_orders_customer_unique_id (customer_unique_id),
    INDEX idx_orders_purchase_ts (order_purchase_timestamp),
    INDEX idx_orders_month (order_month),
    INDEX idx_orders_status (order_status)
);

CREATE TABLE order_items (
    order_id VARCHAR(50) NOT NULL,
    order_item_id INT NOT NULL,
    product_id VARCHAR(50) NOT NULL,
    seller_id VARCHAR(50),
    shipping_limit_date DATETIME,
    price DECIMAL(12,2),
    freight_value DECIMAL(12,2),
    PRIMARY KEY (order_id, order_item_id),
    FOREIGN KEY (order_id) REFERENCES orders(order_id),
    FOREIGN KEY (product_id) REFERENCES products(product_id),
    INDEX idx_items_product_id (product_id),
    INDEX idx_items_seller_id (seller_id)
);

CREATE TABLE order_reviews (
    review_id VARCHAR(50) PRIMARY KEY,
    order_id VARCHAR(50) NOT NULL,
    review_score TINYINT,
    review_comment_message TEXT,
    FOREIGN KEY (order_id) REFERENCES orders(order_id),
    INDEX idx_reviews_order_id (order_id),
    INDEX idx_reviews_score (review_score)
);

CREATE OR REPLACE VIEW customer_order_summary AS
SELECT
    c.customer_unique_id,
    c.customer_city,
    c.customer_state,
    COUNT(DISTINCT o.order_id) AS total_orders,
    MIN(o.order_purchase_timestamp) AS first_purchase_date,
    MAX(o.order_purchase_timestamp) AS last_purchase_date,
    SUM(o.order_revenue) AS total_revenue,
    AVG(o.order_revenue) AS avg_order_value
FROM customers c
LEFT JOIN orders o
    ON c.customer_unique_id = o.customer_unique_id
GROUP BY
    c.customer_unique_id,
    c.customer_city,
    c.customer_state;
