-- ============================================================================
-- High-Value Customer Audience
-- Purpose: Identify top customers by LTV and RFM score for VIP campaigns
-- Output: High-value customer segment for marketing
-- ============================================================================

WITH customer_metrics AS (
    SELECT 
        c.customer_key,
        c.customer_id,
        c.email,
        c.first_name,
        c.last_name,
        c.loyalty_tier,
        DATEDIFF(day, MAX(d.full_date), CURRENT_DATE()) AS recency_days,
        COUNT(DISTINCT fs.order_id) AS frequency,
        SUM(fs.net_amount) AS monetary
    FROM fact_sales fs
    JOIN dim_customers c ON fs.customer_key = c.customer_key
    JOIN dim_dates d ON fs.date_key = d.date_key
    WHERE c.is_current = TRUE
    GROUP BY c.customer_key, c.customer_id, c.email, c.first_name, c.last_name, c.loyalty_tier
),

rfm_scores AS (
    SELECT 
        *,
        NTILE(5) OVER (ORDER BY recency_days DESC) AS r_score,
        NTILE(5) OVER (ORDER BY frequency ASC) AS f_score,
        NTILE(5) OVER (ORDER BY monetary ASC) AS m_score
    FROM customer_metrics
),

scored_customers AS (
    SELECT 
        *,
        (r_score + f_score + m_score) / 3.0 AS rfm_score,
        PERCENT_RANK() OVER (ORDER BY monetary) AS ltv_percentile
    FROM rfm_scores
)

SELECT 
    customer_key,
    customer_id,
    email,
    first_name,
    last_name,
    loyalty_tier,
    recency_days,
    frequency AS total_orders,
    ROUND(monetary, 2) AS total_ltv,
    r_score,
    f_score,
    m_score,
    ROUND(rfm_score, 2) AS rfm_score,
    ROUND(ltv_percentile * 100, 1) AS ltv_percentile,
    'High-Value Customer' AS audience_name,
    CASE 
        WHEN rfm_score >= 4.5 AND ltv_percentile >= 0.9 THEN 'Tier 1 - VIP'
        WHEN rfm_score >= 4.0 AND ltv_percentile >= 0.8 THEN 'Tier 2 - Premium'
        ELSE 'Tier 3 - High Value'
    END AS audience_tier
FROM scored_customers
WHERE rfm_score >= 3.5 
  AND ltv_percentile >= 0.75
ORDER BY monetary DESC;
