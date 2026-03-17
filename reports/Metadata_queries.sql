SELECT 
    'fact_sales' as table_name, COUNT(*) as row_count FROM fact_sales
UNION ALL
SELECT 'dim_time', COUNT(*) FROM dim_time
UNION ALL
SELECT 'dim_product', COUNT(*) FROM dim_product
UNION ALL
SELECT 'dim_customer', COUNT(*) FROM dim_customer
UNION ALL
SELECT 'dim_employee', COUNT(*) FROM dim_employee
UNION ALL
SELECT 'dim_payment_method', COUNT(*) FROM dim_payment_method;