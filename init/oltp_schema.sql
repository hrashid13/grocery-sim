-- ============================================================
-- GROCERY STORE SIMULATION - OLTP SCHEMA
-- Transactional database, resets each simulated day
-- ============================================================

-- Customers (loyalty card members; walk-ins use id = 1)
CREATE TABLE IF NOT EXISTS customers (
    id              SERIAL PRIMARY KEY,
    name            VARCHAR(100),
    email           VARCHAR(150) UNIQUE,
    join_date       DATE NOT NULL DEFAULT CURRENT_DATE
);

-- Insert anonymous walk-in customer as the default
INSERT INTO customers (id, name, email, join_date)
VALUES (1, 'Walk-In Customer', NULL, CURRENT_DATE)
ON CONFLICT DO NOTHING;

-- Suppliers
CREATE TABLE IF NOT EXISTS suppliers (
    id              SERIAL PRIMARY KEY,
    name            VARCHAR(100) NOT NULL,
    contact_info    VARCHAR(200),
    lead_time_days  INT NOT NULL DEFAULT 1
);

-- Product catalog
CREATE TABLE IF NOT EXISTS products (
    id              SERIAL PRIMARY KEY,
    name            VARCHAR(150) NOT NULL,
    category        VARCHAR(50)  NOT NULL,  -- e.g. Produce, Dairy, Frozen
    subcategory     VARCHAR(50),             -- e.g. Fruit, Leafy Greens
    unit_price      NUMERIC(8,2) NOT NULL,
    unit_cost       NUMERIC(8,2) NOT NULL,
    supplier_id     INT REFERENCES suppliers(id)
);

-- Inventory (one row per product, updated in real time)
CREATE TABLE IF NOT EXISTS inventory (
    product_id          INT PRIMARY KEY REFERENCES products(id),
    quantity_on_hand    INT NOT NULL DEFAULT 0,
    reorder_threshold   INT NOT NULL DEFAULT 20,
    last_restocked      TIMESTAMP
);

-- Employees / cashiers
CREATE TABLE IF NOT EXISTS employees (
    id              SERIAL PRIMARY KEY,
    name            VARCHAR(100) NOT NULL,
    role            VARCHAR(50)  NOT NULL DEFAULT 'Cashier',
    shift_start     TIME,
    shift_end       TIME
);

-- Transaction header (one row per checkout)
CREATE TABLE IF NOT EXISTS transactions (
    id              SERIAL PRIMARY KEY,
    customer_id     INT NOT NULL REFERENCES customers(id) DEFAULT 1,
    employee_id     INT REFERENCES employees(id),
    transaction_time TIMESTAMP NOT NULL DEFAULT NOW(),
    payment_method  VARCHAR(20) NOT NULL CHECK (payment_method IN ('cash', 'credit', 'debit', 'mobile')),
    total_amount    NUMERIC(10,2) NOT NULL
);

-- Transaction line items (one row per product per transaction)
CREATE TABLE IF NOT EXISTS transaction_items (
    id                  SERIAL PRIMARY KEY,
    transaction_id      INT NOT NULL REFERENCES transactions(id),
    product_id          INT NOT NULL REFERENCES products(id),
    quantity            INT NOT NULL,
    unit_price_at_sale  NUMERIC(8,2) NOT NULL,
    subtotal            NUMERIC(10,2) NOT NULL
);

-- Purchase orders (restocking events)
CREATE TABLE IF NOT EXISTS purchase_orders (
    id                  SERIAL PRIMARY KEY,
    supplier_id         INT NOT NULL REFERENCES suppliers(id),
    product_id          INT NOT NULL REFERENCES products(id),
    quantity_ordered    INT NOT NULL,
    cost_per_unit       NUMERIC(8,2) NOT NULL,
    order_date          TIMESTAMP NOT NULL DEFAULT NOW(),
    received_date       TIMESTAMP
);
