-- ============================================================================
-- Store Visit Converters Audience
-- Purpose: Identify customers whose store interactions led to purchases
-- Output: High-converting customers for in-store experience optimization
-- ============================================================================

WITH interaction_stats AS (
    SELECT 
        c.customer_key,
        c.customer_id,
        c.email,
        c.first_name,
        c.last_name,
        c.loyalty_tier,
        COUNT(*) AS total_interactions,
        SUM(CASE WHEN fci.led_to_purchase THEN 1 ELSE 0 END) AS converted_interactions,
        COUNT(DISTINCT CASE WHEN fci.led_to_purchase THEN fci.sale_key END) AS purchases_from_interactions,
        COUNT(DISTINCT fci.store_key) AS stores_visited,
        COUNT(DISTINCT fci.channel_key) AS channels_used
    FROM fact_customer_interactions fci
    JOIN dim_customers c ON fci.customer_key = c.customer_key
    WHERE c.is_current = TRUE
    GROUP BY c.customer_key, c.customer_id, c.email, c.first_name, c.last_name, c.loyalty_tier
),

-- Get revenue from converted interactions
conversion_revenue AS (
    SELECT 
        fci.customer_key,
        SUM(fs.net_amount) AS revenue_from_conversions
    FROM fact_customer_interactions fci
    JOIN fact_sales fs ON fci.sale_key = fs.sale_key
    WHERE fci.led_to_purchase = TRUE
    GROUP BY fci.customer_key
),

-- Get interaction types breakdown
interaction_types AS (
    SELECT 
        customer_key,
        interaction_type,
        COUNT(*) AS type_count,
        SUM(CASE WHEN led_to_purchase THEN 1 ELSE 0 END) AS type_conversions
    FROM fact_customer_interactions
    GROUP BY customer_key, interaction_type
),

-- Get most common interaction type per customer
top_interaction_type AS (
    SELECT 
        customer_key,
        interaction_type AS primary_interaction_type,
        type_count,
        type_conversions,
        ROW_NUMBER() OVER (PARTITION BY customer_key ORDER BY type_count DESC) AS rn
    FROM interaction_types
)

SELECT 
    ist.customer_key,
    ist.customer_id,
    ist.email,
    ist.first_name,
    ist.last_name,
    ist.loyalty_tier,
    ist.total_interactions,
    ist.converted_interactions,
    ist.purchases_from_interactions,
    ROUND(ist.converted_interactions * 100.0 / NULLIF(ist.total_interactions, 0), 1) AS conversion_rate_pct,
    ist.stores_visited,
    ist.channels_used,
    ROUND(cr.revenue_from_conversions, 2) AS revenue_from_conversions,
    tit.primary_interaction_type,
    'Store Visit Converter' AS audience_name,
    CASE 
        WHEN ist.converted_interactions * 100.0 / NULLIF(ist.total_interactions, 0) >= 75 THEN 'High Converter'
        WHEN ist.converted_interactions * 100.0 / NULLIF(ist.total_interactions, 0) >= 50 THEN 'Good Converter'
        WHEN ist.converted_interactions * 100.0 / NULLIF(ist.total_interactions, 0) >= 25 THEN 'Moderate Converter'
        ELSE 'Low Converter'
    END AS conversion_segment,
    CASE 
        WHEN ist.stores_visited >= 3 THEN 'Multi-Store Visitor'
        WHEN ist.stores_visited = 2 THEN 'Dual-Store Visitor'
        ELSE 'Single-Store Visitor'
    END AS store_visit_behavior,
    CASE 
        WHEN ist.total_interactions >= 10 THEN 'Highly Engaged'
        WHEN ist.total_interactions >= 5 THEN 'Moderately Engaged'
        ELSE 'Lightly Engaged'
    END AS engagement_level
FROM interaction_stats ist
LEFT JOIN conversion_revenue cr ON ist.customer_key = cr.customer_key
LEFT JOIN top_interaction_type tit ON ist.customer_key = tit.customer_key AND tit.rn = 1
WHERE ist.converted_interactions >= 1
ORDER BY ist.conversion_rate_pct DESC, cr.revenue_from_conversions DESC;
