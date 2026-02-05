-- ============================================================================
-- Loyalty Tier Members Audience
-- Purpose: Segment customers by loyalty tier (Bronze, Silver, Gold, Platinum)
-- Output: Loyalty tier breakdown for tier-specific campaigns
-- ============================================================================

WITH loyalty_member_stats AS (
    SELECT 
        c.customer_key,
        c.customer_id,
        c.email,
        c.first_name,
        c.last_name,
        c.loyalty_tier,
        cs.segment_name AS customer_segment,
        MIN(d.full_date) AS first_purchase_date,
        MAX(d.full_date) AS last_purchase_date,
        COUNT(DISTINCT fs.order_id) AS total_orders,
        SUM(fs.net_amount) AS total_spend,
        DATEDIFF(day, MAX(d.full_date), CURRENT_DATE()) AS days_since_last_purchase
    FROM dim_customers c
    LEFT JOIN dim_customer_segments cs ON c.segment_key = cs.segment_key
    LEFT JOIN fact_sales fs ON c.customer_key = fs.customer_key
    LEFT JOIN dim_dates d ON fs.date_key = d.date_key
    WHERE c.is_current = TRUE
    GROUP BY c.customer_key, c.customer_id, c.email, c.first_name, c.last_name, 
             c.loyalty_tier, cs.segment_name
),

-- Get loyalty points balance
loyalty_points AS (
    SELECT 
        customer_key,
        SUM(CASE WHEN transaction_type = 'Earned' THEN points_amount ELSE 0 END) AS total_earned,
        SUM(CASE WHEN transaction_type = 'Redeemed' THEN points_amount ELSE 0 END) AS total_redeemed,
        SUM(CASE 
            WHEN transaction_type = 'Earned' THEN points_amount 
            WHEN transaction_type = 'Redeemed' THEN -points_amount 
            ELSE 0 
        END) AS current_balance
    FROM fact_loyalty_points
    GROUP BY customer_key
)

SELECT 
    lms.customer_key,
    lms.customer_id,
    lms.email,
    lms.first_name,
    lms.last_name,
    lms.loyalty_tier,
    lms.customer_segment,
    lms.first_purchase_date,
    lms.last_purchase_date,
    lms.days_since_last_purchase,
    lms.total_orders,
    ROUND(lms.total_spend, 2) AS total_spend,
    COALESCE(lp.total_earned, 0) AS total_points_earned,
    COALESCE(lp.total_redeemed, 0) AS total_points_redeemed,
    COALESCE(lp.current_balance, 0) AS current_points_balance,
    'Loyalty Tier Member' AS audience_name,
    CASE lms.loyalty_tier
        WHEN 'Platinum' THEN 1
        WHEN 'Gold' THEN 2
        WHEN 'Silver' THEN 3
        WHEN 'Bronze' THEN 4
        ELSE 5
    END AS tier_rank,
    CASE 
        WHEN lms.days_since_last_purchase <= 30 THEN 'Active'
        WHEN lms.days_since_last_purchase <= 90 THEN 'Engaged'
        ELSE 'Dormant'
    END AS engagement_status,
    CASE 
        WHEN COALESCE(lp.current_balance, 0) >= 10000 THEN 'High Points Balance'
        WHEN COALESCE(lp.current_balance, 0) >= 5000 THEN 'Medium Points Balance'
        ELSE 'Low Points Balance'
    END AS points_segment
FROM loyalty_member_stats lms
LEFT JOIN loyalty_points lp ON lms.customer_key = lp.customer_key
WHERE lms.loyalty_tier IS NOT NULL
ORDER BY tier_rank, lms.total_spend DESC;
