-- ============================================================================
-- RFM Analysis Query
-- Purpose: Score customers on Recency, Frequency, Monetary value
-- Output: Customer RFM scores with behavioral segment labels
-- ============================================================================

WITH customer_metrics AS (
    SELECT 
        c.customer_key,
        c.customer_id,
        c.email,
        c.first_name,
        c.last_name,
        DATEDIFF(day, MAX(d.full_date), CURRENT_DATE()) AS recency_days,
        COUNT(DISTINCT fs.order_id) AS frequency,
        SUM(fs.net_amount) AS monetary
    FROM fact_sales fs
    JOIN dim_customers c ON fs.customer_key = c.customer_key
    JOIN dim_dates d ON fs.date_key = d.date_key
    WHERE c.is_current = TRUE
    GROUP BY c.customer_key, c.customer_id, c.email, c.first_name, c.last_name
),

rfm_scores AS (
    SELECT 
        customer_key,
        customer_id,
        email,
        first_name,
        last_name,
        recency_days,
        frequency,
        monetary,
        -- R score: 5 = most recent, 1 = least recent
        NTILE(5) OVER (ORDER BY recency_days DESC) AS r_score,
        -- F score: 5 = most frequent, 1 = least frequent
        NTILE(5) OVER (ORDER BY frequency ASC) AS f_score,
        -- M score: 5 = highest spend, 1 = lowest spend
        NTILE(5) OVER (ORDER BY monetary ASC) AS m_score
    FROM customer_metrics
)

SELECT 
    customer_key,
    customer_id,
    email,
    first_name,
    last_name,
    recency_days,
    frequency,
    ROUND(monetary, 2) AS monetary,
    r_score,
    f_score,
    m_score,
    ROUND((r_score + f_score + m_score) / 3.0, 2) AS rfm_score,
    -- Segment labels based on RFM combination
    CASE 
        WHEN r_score >= 4 AND f_score >= 4 AND m_score >= 4 THEN 'Champions'
        WHEN r_score >= 4 AND f_score >= 3 AND m_score >= 3 THEN 'Loyal Customers'
        WHEN r_score >= 4 AND f_score <= 2 THEN 'New Customers'
        WHEN r_score >= 3 AND f_score >= 3 AND m_score >= 3 THEN 'Potential Loyalists'
        WHEN r_score >= 3 AND f_score >= 1 AND m_score >= 2 THEN 'Promising'
        WHEN r_score <= 2 AND f_score >= 4 AND m_score >= 4 THEN 'At Risk'
        WHEN r_score <= 2 AND f_score >= 3 AND m_score >= 3 THEN 'Need Attention'
        WHEN r_score <= 2 AND f_score <= 2 AND m_score <= 2 THEN 'Hibernating'
        WHEN r_score <= 1 AND f_score >= 3 THEN 'Cannot Lose Them'
        WHEN r_score <= 1 AND f_score <= 2 THEN 'Lost'
        ELSE 'Others'
    END AS rfm_segment
FROM rfm_scores
ORDER BY rfm_score DESC;
