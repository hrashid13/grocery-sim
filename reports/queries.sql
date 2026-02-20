
-- 1. Daily Revenue Summary

SELECT
    fs.simulated_day,
    COUNT(DISTINCT fs.source_transaction_id)  AS total_transactions,
    SUM(fs.quantity_sold)                     AS total_items_sold,
    ROUND(SUM(fs.revenue)::numeric, 2)        AS total_revenue,
    ROUND(SUM(fs.cost)::numeric, 2)           AS total_cost,
    ROUND(SUM(fs.profit)::numeric, 2)         AS total_profit,
    ROUND(AVG(fs.revenue)::numeric, 2)        AS avg_revenue_per_item
FROM fact_sales fs
GROUP BY fs.simulated_day
ORDER BY fs.simulated_day;

-- 2. Revenue by Hour of Day

SELECT
    dt.hour_of_day,
    dt.time_label,
    dt.part_of_day,
    dt.is_rush_hour,
    COUNT(DISTINCT fs.source_transaction_id)  AS total_transactions,
    ROUND(SUM(fs.revenue)::numeric, 2)        AS total_revenue,
    ROUND(AVG(fs.revenue)::numeric, 2)        AS avg_revenue_per_item
FROM fact_sales fs
JOIN dim_time dt ON fs.dim_time_id = dt.id
GROUP BY dt.hour_of_day, dt.time_label, dt.part_of_day, dt.is_rush_hour
ORDER BY dt.hour_of_day;


-- 3. Top 10 Best Selling Products

SELECT
    dp.name                                   AS product,
    dp.category,
    SUM(fs.quantity_sold)                     AS total_units_sold,
    ROUND(SUM(fs.revenue)::numeric, 2)        AS total_revenue,
    ROUND(SUM(fs.profit)::numeric, 2)         AS total_profit,
    ROUND((SUM(fs.profit) / NULLIF(SUM(fs.revenue), 0) * 100)::numeric, 1) AS profit_margin_pct
FROM fact_sales fs
JOIN dim_product dp ON fs.dim_product_id = dp.id
GROUP BY dp.name, dp.category
ORDER BY total_revenue DESC
LIMIT 10;


-- 4. Revenue by Product Category

SELECT
    dp.category,
    SUM(fs.quantity_sold)                     AS total_units_sold,
    ROUND(SUM(fs.revenue)::numeric, 2)        AS total_revenue,
    ROUND(SUM(fs.profit)::numeric, 2)         AS total_profit,
    ROUND((SUM(fs.profit) / NULLIF(SUM(fs.revenue), 0) * 100)::numeric, 1) AS profit_margin_pct
FROM fact_sales fs
JOIN dim_product dp ON fs.dim_product_id = dp.id
GROUP BY dp.category
ORDER BY total_revenue DESC;


-- 5. Loyalty vs Walk-in

SELECT
    CASE WHEN dc.is_loyalty THEN 'Loyalty Member' ELSE 'Walk-In' END AS customer_type,
    COUNT(DISTINCT fs.source_transaction_id)  AS total_transactions,
    ROUND(SUM(fs.revenue)::numeric, 2)        AS total_revenue,
    ROUND(
        SUM(fs.revenue) / NULLIF(COUNT(DISTINCT fs.source_transaction_id), 0)
    ::numeric, 2)                             AS avg_spend_per_transaction
FROM fact_sales fs
JOIN dim_customer dc ON fs.dim_customer_id = dc.id
GROUP BY dc.is_loyalty
ORDER BY dc.is_loyalty DESC;


-- 6. Payment Method Breakdown

SELECT
    dpm.method                                AS payment_method,
    COUNT(DISTINCT fs.source_transaction_id)  AS total_transactions,
    ROUND(SUM(fs.revenue)::numeric, 2)        AS total_revenue,
    ROUND(
        COUNT(DISTINCT fs.source_transaction_id) * 100.0 /
        SUM(COUNT(DISTINCT fs.source_transaction_id)) OVER ()
    ::numeric, 1)                             AS pct_of_transactions
FROM fact_sales fs
JOIN dim_payment_method dpm ON fs.dim_payment_method_id = dpm.id
GROUP BY dpm.method
ORDER BY total_transactions DESC;


-- 7. Top Cashier Performances

SELECT
    de.name                                   AS employee,
    de.role,
    COUNT(DISTINCT fs.source_transaction_id)  AS total_transactions,
    ROUND(SUM(fs.revenue)::numeric, 2)        AS total_revenue_processed,
    ROUND(
        SUM(fs.revenue) / NULLIF(COUNT(DISTINCT fs.source_transaction_id), 0)
    ::numeric, 2)                             AS avg_transaction_value
FROM fact_sales fs
JOIN dim_employee de ON fs.dim_employee_id = de.id
GROUP BY de.name, de.role
ORDER BY total_revenue_processed DESC;


-- 8. Rush hour vs non peak time

SELECT
    CASE WHEN dt.is_rush_hour THEN 'Rush Hour' ELSE 'Off-Peak' END AS period,
    COUNT(DISTINCT fs.source_transaction_id)  AS total_transactions,
    ROUND(SUM(fs.revenue)::numeric, 2)        AS total_revenue,
    ROUND(AVG(fs.revenue)::numeric, 2)        AS avg_revenue_per_item,
    ROUND(
        COUNT(DISTINCT fs.source_transaction_id) * 100.0 /
        SUM(COUNT(DISTINCT fs.source_transaction_id)) OVER ()
    ::numeric, 1)                             AS pct_of_transactions
FROM fact_sales fs
JOIN dim_time dt ON fs.dim_time_id = dt.id
GROUP BY dt.is_rush_hour
ORDER BY dt.is_rush_hour DESC;


-- 9. Revenue by Category by Day

SELECT
    fs.simulated_day,
    dp.category,
    ROUND(SUM(fs.revenue)::numeric, 2)        AS revenue
FROM fact_sales fs
JOIN dim_product dp ON fs.dim_product_id = dp.id
GROUP BY fs.simulated_day, dp.category
ORDER BY fs.simulated_day, revenue DESC;


-- 10. Bottom 10 Products

SELECT
    dp.name                                   AS product,
    dp.category,
    SUM(fs.quantity_sold)                     AS total_units_sold,
    ROUND(SUM(fs.revenue)::numeric, 2)        AS total_revenue
FROM fact_sales fs
JOIN dim_product dp ON fs.dim_product_id = dp.id
GROUP BY dp.name, dp.category
ORDER BY total_units_sold ASC
LIMIT 10;
