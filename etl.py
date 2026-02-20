import psycopg2
import psycopg2.extras
from datetime import datetime

# ------------------------------------------------------------------
# Configuration
# ------------------------------------------------------------------

OLTP_CONFIG = {
    "host":     "localhost",
    "port":     5434,
    "dbname":   "grocery_oltp",
    "user":     "grocery_user",
    "password": "grocery_pass"
}

OLAP_CONFIG = {
    "host":     "localhost",
    "port":     5435,
    "dbname":   "grocery_olap",
    "user":     "grocery_user",
    "password": "grocery_pass"
}

STORE_OPEN_HOUR  = 8
STORE_CLOSE_HOUR = 22


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------

def get_part_of_day(hour):
    if hour < 12:
        return "Morning"
    elif hour < 17:
        return "Afternoon"
    else:
        return "Evening"


def is_rush_hour(hour):
    return hour in (8, 9, 12, 17, 18)


# ------------------------------------------------------------------
# Step 1: Load OLTP data
# ------------------------------------------------------------------

def load_oltp_data(oltp_cur):
    print("  Loading transactions from OLTP...")

    oltp_cur.execute("""
        SELECT
            t.id               AS transaction_id,
            t.customer_id,
            t.employee_id,
            t.transaction_time,
            t.payment_method,
            ti.product_id,
            ti.quantity,
            ti.unit_price_at_sale,
            ti.subtotal,
            p.unit_cost,
            p.name             AS product_name,
            p.category,
            p.subcategory,
            p.supplier_id,
            c.name             AS customer_name,
            c.email,
            e.name             AS employee_name,
            e.role
        FROM transaction_items ti
        JOIN transactions  t  ON ti.transaction_id = t.id
        JOIN products      p  ON ti.product_id     = p.id
        JOIN customers     c  ON t.customer_id     = c.id
        LEFT JOIN employees e ON t.employee_id     = e.id
        ORDER BY t.transaction_time
    """)

    rows = oltp_cur.fetchall()
    cols = [desc[0] for desc in oltp_cur.description]
    data = [dict(zip(cols, row)) for row in rows]
    print(f"    Loaded {len(data)} line items from {len(set(r['transaction_id'] for r in data))} transactions.")
    return data


# ------------------------------------------------------------------
# Step 2: Populate dimension tables
# ------------------------------------------------------------------

def upsert_dim_time(olap_cur, sim_day):
    print("  Populating dim_time...")
    rows = []
    for hour in range(STORE_OPEN_HOUR, STORE_CLOSE_HOUR):
        rows.append((
            sim_day,
            hour,
            f"{hour:02d}:00",
            get_part_of_day(hour),
            is_rush_hour(hour)
        ))
    psycopg2.extras.execute_values(olap_cur, """
        INSERT INTO dim_time (simulated_day, hour_of_day, time_label, part_of_day, is_rush_hour)
        VALUES %s
        ON CONFLICT DO NOTHING
        RETURNING id, hour_of_day
    """, rows)

    # Build a lookup: hour -> dim_time id for this sim_day
    olap_cur.execute(
        "SELECT id, hour_of_day FROM dim_time WHERE simulated_day = %s", (sim_day,)
    )
    return {hour: tid for tid, hour in olap_cur.fetchall()}


def upsert_dim_products(olap_cur, data):
    print("  Populating dim_product...")
    seen = {}
    for row in data:
        pid = row["product_id"]
        if pid not in seen:
            seen[pid] = (pid, row["product_name"], row["category"],
                         row["subcategory"], float(row["unit_cost"]))

    psycopg2.extras.execute_values(olap_cur, """
        INSERT INTO dim_product (source_id, name, category, subcategory, unit_cost)
        VALUES %s
        ON CONFLICT DO NOTHING
    """, list(seen.values()))

    olap_cur.execute("SELECT id, source_id FROM dim_product")
    return {source_id: dim_id for dim_id, source_id in olap_cur.fetchall()}


def upsert_dim_customers(olap_cur, data):
    print("  Populating dim_customer...")
    seen = {}
    for row in data:
        cid = row["customer_id"]
        if cid not in seen:
            seen[cid] = (
                cid,
                row["customer_name"],
                row["email"] is not None,  # is_loyalty
                None                        # join_date not critical for OLAP
            )

    psycopg2.extras.execute_values(olap_cur, """
        INSERT INTO dim_customer (source_id, name, is_loyalty, join_date)
        VALUES %s
        ON CONFLICT DO NOTHING
    """, list(seen.values()))

    olap_cur.execute("SELECT id, source_id FROM dim_customer")
    return {source_id: dim_id for dim_id, source_id in olap_cur.fetchall()}


def upsert_dim_employees(olap_cur, data):
    print("  Populating dim_employee...")
    seen = {}
    for row in data:
        eid = row["employee_id"]
        if eid and eid not in seen:
            seen[eid] = (eid, row["employee_name"], row["role"])

    if seen:
        psycopg2.extras.execute_values(olap_cur, """
            INSERT INTO dim_employee (source_id, name, role)
            VALUES %s
            ON CONFLICT DO NOTHING
        """, list(seen.values()))

    olap_cur.execute("SELECT id, source_id FROM dim_employee")
    return {source_id: dim_id for dim_id, source_id in olap_cur.fetchall()}


def get_payment_method_map(olap_cur):
    olap_cur.execute("SELECT id, method FROM dim_payment_method")
    return {method: pid for pid, method in olap_cur.fetchall()}


# ------------------------------------------------------------------
# Step 3: Insert into fact_sales
# ------------------------------------------------------------------

def insert_fact_sales(olap_cur, data, sim_day,
                      time_map, product_map, customer_map,
                      employee_map, payment_map):
    print("  Inserting into fact_sales...")
    rows = []
    for row in data:
        hour          = row["transaction_time"].hour
        dim_time_id   = time_map.get(hour)
        dim_prod_id   = product_map.get(row["product_id"])
        dim_cust_id   = customer_map.get(row["customer_id"])
        dim_emp_id    = employee_map.get(row["employee_id"])
        dim_pay_id    = payment_map.get(row["payment_method"])

        if not all([dim_time_id, dim_prod_id, dim_cust_id, dim_pay_id]):
            print(f"    Warning: skipping line item, missing dimension key.")
            continue

        quantity   = row["quantity"]
        unit_price = float(row["unit_price_at_sale"])
        unit_cost  = float(row["unit_cost"])
        revenue    = round(unit_price * quantity, 2)
        cost       = round(unit_cost  * quantity, 2)
        profit     = round(revenue - cost, 2)

        rows.append((
            dim_time_id, dim_prod_id, dim_cust_id, dim_emp_id, dim_pay_id,
            row["transaction_id"], sim_day,
            quantity, unit_price, unit_cost, revenue, cost, profit
        ))

    psycopg2.extras.execute_values(olap_cur, """
        INSERT INTO fact_sales (
            dim_time_id, dim_product_id, dim_customer_id,
            dim_employee_id, dim_payment_method_id,
            source_transaction_id, simulated_day,
            quantity_sold, unit_price, unit_cost,
            revenue, cost, profit
        ) VALUES %s
    """, rows)

    print(f"    Inserted {len(rows)} rows into fact_sales.")


# ------------------------------------------------------------------
# Step 4: Reset OLTP for next day
# ------------------------------------------------------------------

def reset_oltp(oltp_cur):
    print("  Resetting OLTP for next day...")
    oltp_cur.execute("DELETE FROM transaction_items")
    oltp_cur.execute("DELETE FROM transactions")
    oltp_cur.execute("DELETE FROM purchase_orders")
    oltp_cur.execute("UPDATE inventory SET quantity_on_hand = 150, last_restocked = NULL")
    print("    Transactions cleared, inventory restocked to 150 units.")


# ------------------------------------------------------------------
# Main ETL
# ------------------------------------------------------------------

def run_etl(sim_day):
    print("=" * 50)
    print(f"ETL - END OF DAY {sim_day}")
    print("=" * 50)
    started = datetime.now()

    oltp_conn = psycopg2.connect(**OLTP_CONFIG)
    olap_conn = psycopg2.connect(**OLAP_CONFIG)
    oltp_cur  = oltp_conn.cursor()
    olap_cur  = olap_conn.cursor()

    try:
        # Extract
        data = load_oltp_data(oltp_cur)

        if not data:
            print("No transactions found. Did the simulation run today?")
            return

        # Transform + Load dimensions
        time_map     = upsert_dim_time(olap_cur, sim_day)
        product_map  = upsert_dim_products(olap_cur, data)
        customer_map = upsert_dim_customers(olap_cur, data)
        employee_map = upsert_dim_employees(olap_cur, data)
        payment_map  = get_payment_method_map(olap_cur)

        # Load fact table
        insert_fact_sales(
            olap_cur, data, sim_day,
            time_map, product_map, customer_map,
            employee_map, payment_map
        )

        olap_conn.commit()
        print("\n  OLAP load complete.")

        # Reset OLTP
        reset_oltp(oltp_cur)
        oltp_conn.commit()

        elapsed = (datetime.now() - started).total_seconds()
        print(f"\nETL finished in {elapsed:.1f} seconds.")
        print(f"Day {sim_day} data is now in the OLAP database.")
        print("=" * 50)

    except Exception as e:
        olap_conn.rollback()
        oltp_conn.rollback()
        print(f"\nETL error: {e}")
        raise

    finally:
        oltp_cur.close()
        olap_cur.close()
        oltp_conn.close()
        olap_conn.close()


# ------------------------------------------------------------------
# Entry point
# ------------------------------------------------------------------

if __name__ == "__main__":
    import sys
    day_number = int(sys.argv[1]) if len(sys.argv) > 1 else 1
    run_etl(sim_day=day_number)
