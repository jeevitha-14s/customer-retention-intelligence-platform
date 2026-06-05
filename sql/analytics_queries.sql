-- Customer Retention Intelligence Platform
-- Advanced SQL analysis for retention, churn, CLV, segmentation, cohorts, and revenue impact.

USE customer_retention_intelligence;

-- 1. Which customers generate the most revenue? Uses INNER JOIN, RANK(), and DENSE_RANK().
WITH customer_revenue AS (
    SELECT
        c.customer_unique_id,
        c.customer_state,
        c.customer_city,
        COUNT(DISTINCT o.order_id) AS orders_count,
        SUM(o.order_revenue) AS total_revenue,
        AVG(o.order_revenue) AS avg_order_value
    FROM customers c
    INNER JOIN orders o
        ON c.customer_unique_id = o.customer_unique_id
    WHERE o.order_status = 'delivered'
    GROUP BY c.customer_unique_id, c.customer_state, c.customer_city
)
SELECT
    customer_unique_id,
    customer_state,
    customer_city,
    orders_count,
    total_revenue,
    avg_order_value,
    RANK() OVER (ORDER BY total_revenue DESC) AS revenue_rank,
    DENSE_RANK() OVER (PARTITION BY customer_state ORDER BY total_revenue DESC) AS state_revenue_rank
FROM customer_revenue
ORDER BY revenue_rank
LIMIT 100;

-- 2. RFM segmentation with value tiers.
WITH customer_metrics AS (
    SELECT
        c.customer_unique_id,
        c.customer_state,
        MAX(DATE(o.order_purchase_timestamp)) AS last_purchase_date,
        COUNT(DISTINCT o.order_id) AS frequency,
        SUM(o.order_revenue) AS monetary,
        DATEDIFF((SELECT MAX(DATE(order_purchase_timestamp)) FROM orders), MAX(DATE(o.order_purchase_timestamp))) AS recency_days
    FROM customers c
    LEFT JOIN orders o
        ON c.customer_unique_id = o.customer_unique_id
    WHERE o.order_status = 'delivered'
    GROUP BY c.customer_unique_id, c.customer_state
),
rfm_scores AS (
    SELECT
        *,
        NTILE(5) OVER (ORDER BY recency_days DESC) AS recency_score,
        NTILE(5) OVER (ORDER BY frequency ASC) AS frequency_score,
        NTILE(5) OVER (ORDER BY monetary ASC) AS monetary_score
    FROM customer_metrics
)
SELECT
    customer_unique_id,
    customer_state,
    recency_days,
    frequency,
    monetary,
    recency_score,
    frequency_score,
    monetary_score,
    (recency_score + frequency_score + monetary_score) AS rfm_score,
    CASE
        WHEN recency_score >= 4 AND frequency_score >= 4 AND monetary_score >= 4 THEN 'VIP'
        WHEN recency_score >= 3 AND frequency_score >= 3 THEN 'Loyal'
        WHEN recency_score <= 2 AND monetary_score >= 3 THEN 'At Risk'
        WHEN recency_score <= 2 THEN 'Lost'
        ELSE 'Developing'
    END AS value_tier
FROM rfm_scores;

-- 3. Which customer segments have the highest churn?
WITH rfm AS (
    SELECT
        c.customer_unique_id,
        c.customer_state,
        MAX(DATE(o.order_purchase_timestamp)) AS last_purchase_date,
        COUNT(DISTINCT o.order_id) AS frequency,
        SUM(o.order_revenue) AS monetary,
        DATEDIFF((SELECT MAX(DATE(order_purchase_timestamp)) FROM orders), MAX(DATE(o.order_purchase_timestamp))) AS recency_days
    FROM customers c
    INNER JOIN orders o
        ON c.customer_unique_id = o.customer_unique_id
    WHERE o.order_status = 'delivered'
    GROUP BY c.customer_unique_id, c.customer_state
),
segments AS (
    SELECT
        *,
        CASE
            WHEN recency_days <= 90 AND frequency >= 2 AND monetary >= 500 THEN 'VIP'
            WHEN recency_days <= 180 AND frequency >= 2 THEN 'Loyal'
            WHEN recency_days BETWEEN 181 AND 365 THEN 'At Risk'
            ELSE 'Lost'
        END AS customer_segment,
        CASE WHEN recency_days > 180 THEN 1 ELSE 0 END AS churned_flag
    FROM rfm
)
SELECT
    customer_segment,
    COUNT(*) AS customers,
    SUM(churned_flag) AS churned_customers,
    ROUND(SUM(churned_flag) / COUNT(*) * 100, 2) AS churn_rate_pct,
    SUM(CASE WHEN churned_flag = 1 THEN monetary ELSE 0 END) AS historical_revenue_from_churned
FROM segments
GROUP BY customer_segment
ORDER BY churn_rate_pct DESC;

-- 4. What percentage of customers return after 30, 60, and 90 days? Uses LAG().
WITH customer_orders AS (
    SELECT
        customer_unique_id,
        order_id,
        order_purchase_timestamp,
        LAG(order_purchase_timestamp) OVER (
            PARTITION BY customer_unique_id
            ORDER BY order_purchase_timestamp
        ) AS previous_order_ts
    FROM orders
    WHERE order_status = 'delivered'
),
return_windows AS (
    SELECT
        customer_unique_id,
        order_id,
        DATEDIFF(order_purchase_timestamp, previous_order_ts) AS days_since_previous_order
    FROM customer_orders
    WHERE previous_order_ts IS NOT NULL
)
SELECT
    COUNT(DISTINCT customer_unique_id) AS returning_customers,
    ROUND(COUNT(DISTINCT CASE WHEN days_since_previous_order <= 30 THEN customer_unique_id END)
        / COUNT(DISTINCT customer_unique_id) * 100, 2) AS returned_within_30_days_pct,
    ROUND(COUNT(DISTINCT CASE WHEN days_since_previous_order <= 60 THEN customer_unique_id END)
        / COUNT(DISTINCT customer_unique_id) * 100, 2) AS returned_within_60_days_pct,
    ROUND(COUNT(DISTINCT CASE WHEN days_since_previous_order <= 90 THEN customer_unique_id END)
        / COUNT(DISTINCT customer_unique_id) * 100, 2) AS returned_within_90_days_pct
FROM return_windows;

-- 5. Which regions have the best retention?
WITH customer_activity AS (
    SELECT
        c.customer_state,
        c.customer_unique_id,
        COUNT(DISTINCT o.order_id) AS order_count
    FROM customers c
    LEFT JOIN orders o
        ON c.customer_unique_id = o.customer_unique_id
       AND o.order_status = 'delivered'
    GROUP BY c.customer_state, c.customer_unique_id
)
SELECT
    customer_state,
    COUNT(*) AS customers,
    SUM(CASE WHEN order_count >= 2 THEN 1 ELSE 0 END) AS repeat_customers,
    ROUND(SUM(CASE WHEN order_count >= 2 THEN 1 ELSE 0 END) / COUNT(*) * 100, 2) AS repeat_customer_rate_pct
FROM customer_activity
GROUP BY customer_state
HAVING customers >= 100
ORDER BY repeat_customer_rate_pct DESC;

-- 6. Revenue impact of churn.
WITH customer_value AS (
    SELECT
        customer_unique_id,
        MAX(DATE(order_purchase_timestamp)) AS last_purchase_date,
        COUNT(DISTINCT order_id) AS order_count,
        SUM(order_revenue) AS historical_clv,
        AVG(order_revenue) AS avg_order_value
    FROM orders
    WHERE order_status = 'delivered'
    GROUP BY customer_unique_id
)
SELECT
    CASE
        WHEN DATEDIFF((SELECT MAX(DATE(order_purchase_timestamp)) FROM orders), last_purchase_date) > 180 THEN 'Churned'
        ELSE 'Active'
    END AS lifecycle_status,
    COUNT(*) AS customers,
    SUM(historical_clv) AS historical_revenue,
    SUM(avg_order_value) AS estimated_revenue_at_risk,
    AVG(historical_clv) AS avg_historical_clv
FROM customer_value
GROUP BY lifecycle_status;

-- 7. Monthly cohorts and retention percentage.
WITH orders_clean AS (
    SELECT
        customer_unique_id,
        order_id,
        DATE_FORMAT(order_purchase_timestamp, '%Y-%m-01') AS order_month
    FROM orders
    WHERE order_status = 'delivered'
),
cohorts AS (
    SELECT
        customer_unique_id,
        MIN(order_month) AS cohort_month
    FROM orders_clean
    GROUP BY customer_unique_id
),
cohort_activity AS (
    SELECT
        c.cohort_month,
        o.order_month,
        TIMESTAMPDIFF(MONTH, c.cohort_month, o.order_month) AS months_since_first_purchase,
        COUNT(DISTINCT o.customer_unique_id) AS active_customers
    FROM orders_clean o
    INNER JOIN cohorts c
        ON o.customer_unique_id = c.customer_unique_id
    GROUP BY c.cohort_month, o.order_month, months_since_first_purchase
),
cohort_sizes AS (
    SELECT
        cohort_month,
        active_customers AS cohort_size
    FROM cohort_activity
    WHERE months_since_first_purchase = 0
)
SELECT
    ca.cohort_month,
    ca.months_since_first_purchase,
    cs.cohort_size,
    ca.active_customers,
    ROUND(ca.active_customers / cs.cohort_size * 100, 2) AS retention_pct
FROM cohort_activity ca
INNER JOIN cohort_sizes cs
    ON ca.cohort_month = cs.cohort_month
ORDER BY ca.cohort_month, ca.months_since_first_purchase;

-- 8. Revenue retention by cohort.
WITH orders_clean AS (
    SELECT
        customer_unique_id,
        order_id,
        DATE_FORMAT(order_purchase_timestamp, '%Y-%m-01') AS order_month,
        order_revenue
    FROM orders
    WHERE order_status = 'delivered'
),
cohorts AS (
    SELECT
        customer_unique_id,
        MIN(order_month) AS cohort_month
    FROM orders_clean
    GROUP BY customer_unique_id
),
cohort_revenue AS (
    SELECT
        c.cohort_month,
        o.order_month,
        TIMESTAMPDIFF(MONTH, c.cohort_month, o.order_month) AS months_since_first_purchase,
        SUM(o.order_revenue) AS revenue
    FROM orders_clean o
    INNER JOIN cohorts c
        ON o.customer_unique_id = c.customer_unique_id
    GROUP BY c.cohort_month, o.order_month, months_since_first_purchase
),
base_revenue AS (
    SELECT cohort_month, revenue AS month_0_revenue
    FROM cohort_revenue
    WHERE months_since_first_purchase = 0
)
SELECT
    cr.cohort_month,
    cr.months_since_first_purchase,
    cr.revenue,
    br.month_0_revenue,
    ROUND(cr.revenue / br.month_0_revenue * 100, 2) AS revenue_retention_pct
FROM cohort_revenue cr
INNER JOIN base_revenue br
    ON cr.cohort_month = br.cohort_month
ORDER BY cr.cohort_month, cr.months_since_first_purchase;

-- 9. Monthly revenue with running totals and month-over-month change.
WITH monthly_revenue AS (
    SELECT
        DATE_FORMAT(order_purchase_timestamp, '%Y-%m-01') AS revenue_month,
        COUNT(DISTINCT order_id) AS orders_count,
        COUNT(DISTINCT customer_unique_id) AS active_customers,
        SUM(order_revenue) AS revenue
    FROM orders
    WHERE order_status = 'delivered'
    GROUP BY DATE_FORMAT(order_purchase_timestamp, '%Y-%m-01')
)
SELECT
    revenue_month,
    orders_count,
    active_customers,
    revenue,
    SUM(revenue) OVER (ORDER BY revenue_month) AS running_revenue,
    LAG(revenue) OVER (ORDER BY revenue_month) AS prior_month_revenue,
    ROUND((revenue - LAG(revenue) OVER (ORDER BY revenue_month))
        / NULLIF(LAG(revenue) OVER (ORDER BY revenue_month), 0) * 100, 2) AS mom_revenue_growth_pct
FROM monthly_revenue
ORDER BY revenue_month;

-- 10. Churn trend over time using a 180-day inactivity rule.
WITH customer_months AS (
    SELECT
        customer_unique_id,
        DATE_FORMAT(order_purchase_timestamp, '%Y-%m-01') AS order_month,
        MAX(DATE(order_purchase_timestamp)) AS last_purchase_in_month
    FROM orders
    WHERE order_status = 'delivered'
    GROUP BY customer_unique_id, DATE_FORMAT(order_purchase_timestamp, '%Y-%m-01')
),
month_spine AS (
    SELECT DISTINCT DATE_FORMAT(order_purchase_timestamp, '%Y-%m-01') AS month_start
    FROM orders
    WHERE order_status = 'delivered'
),
customer_month_status AS (
    SELECT
        m.month_start,
        c.customer_unique_id,
        MAX(cm.last_purchase_in_month) AS last_purchase_before_or_in_month
FROM month_spine m
    CROSS JOIN customers c
    LEFT JOIN customer_months cm
        ON c.customer_unique_id = cm.customer_unique_id
       AND cm.order_month <= m.month_start
    GROUP BY m.month_start, c.customer_unique_id
)
SELECT
    month_start,
    COUNT(*) AS known_customers,
    SUM(CASE WHEN DATEDIFF(LAST_DAY(month_start), last_purchase_before_or_in_month) > 180 THEN 1 ELSE 0 END) AS churned_customers,
    ROUND(SUM(CASE WHEN DATEDIFF(LAST_DAY(month_start), last_purchase_before_or_in_month) > 180 THEN 1 ELSE 0 END) / COUNT(*) * 100, 2) AS churn_rate_pct
FROM customer_month_status
WHERE last_purchase_before_or_in_month IS NOT NULL
GROUP BY month_start
ORDER BY month_start;
