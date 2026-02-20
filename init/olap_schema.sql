-- ============================================================
-- GROCERY STORE SIMULATION - OLAP SCHEMA (Star Schema)
-- Analytical database, accumulates data across simulated days
-- ============================================================

-- ----------------------
-- DIMENSION TABLES
-- ----------------------

-- Time dimension (one row per simulated hour)
CREATE TABLE IF NOT EXISTS dim_time (
    id                  SERIAL PRIMARY KEY,
    simulated_day       INT NOT NULL,        -- day 1, day 2, day 3...
    hour_of_day         INT NOT NULL,        -- 8 through 22
    time_label          VARCHAR(20),         -- e.g. '08:00', '14:00'
    part_of_day         VARCHAR(20),         -- Morning, Afternoon, Evening
    is_rush_hour        BOOLEAN DEFAULT FALSE -- 8-9am, 12-1pm, 5-6pm
);

-- Product dimension
CREATE TABLE IF NOT EXISTS dim_product (
    id              SERIAL PRIMARY KEY,
    source_id       INT NOT NULL,            -- original product id from OLTP
    name            VARCHAR(150) NOT NULL,
    category        VARCHAR(50)  NOT NULL,
    subcategory     VARCHAR(50),
    unit_cost       NUMERIC(8,2)
);

-- Customer dimension
CREATE TABLE IF NOT EXISTS dim_customer (
    id              SERIAL PRIMARY KEY,
    source_id       INT NOT NULL,
    name            VARCHAR(100),
    is_loyalty      BOOLEAN DEFAULT FALSE,   -- false = walk-in
    join_date       DATE
);

-- Employee dimension
CREATE TABLE IF NOT EXISTS dim_employee (
    id              SERIAL PRIMARY KEY,
    source_id       INT NOT NULL,
    name            VARCHAR(100),
    role            VARCHAR(50)
);

-- Payment method dimension
CREATE TABLE IF NOT EXISTS dim_payment_method (
    id              SERIAL PRIMARY KEY,
    method          VARCHAR(20) UNIQUE NOT NULL  -- cash, credit, debit, mobile
);

INSERT INTO dim_payment_method (method) VALUES
    ('cash'), ('credit'), ('debit'), ('mobile')
ON CONFLICT DO NOTHING;

-- ----------------------
-- FACT TABLE
-- ----------------------

-- One row per line item per transaction (most granular level)
CREATE TABLE IF NOT EXISTS fact_sales (
    id                      SERIAL PRIMARY KEY,
    dim_time_id             INT NOT NULL REFERENCES dim_time(id),
    dim_product_id          INT NOT NULL REFERENCES dim_product(id),
    dim_customer_id         INT NOT NULL REFERENCES dim_customer(id),
    dim_employee_id         INT REFERENCES dim_employee(id),
    dim_payment_method_id   INT NOT NULL REFERENCES dim_payment_method(id),

    -- Source reference
    source_transaction_id   INT NOT NULL,
    simulated_day           INT NOT NULL,

    -- Measures
    quantity_sold           INT NOT NULL,
    unit_price              NUMERIC(8,2) NOT NULL,
    unit_cost               NUMERIC(8,2) NOT NULL,
    revenue                 NUMERIC(10,2) NOT NULL,   -- quantity * unit_price
    cost                    NUMERIC(10,2) NOT NULL,   -- quantity * unit_cost
    profit                  NUMERIC(10,2) NOT NULL    -- revenue - cost
);

-- Indexes to speed up common analytical queries
CREATE INDEX IF NOT EXISTS idx_fact_sales_day      ON fact_sales(simulated_day);
CREATE INDEX IF NOT EXISTS idx_fact_sales_product  ON fact_sales(dim_product_id);
CREATE INDEX IF NOT EXISTS idx_fact_sales_time     ON fact_sales(dim_time_id);
