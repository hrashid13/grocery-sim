import psycopg2
import psycopg2.extras
import random
import time
import json
from datetime import datetime, date

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

STORE_OPEN_HOUR  = 8
STORE_CLOSE_HOUR = 22
SECONDS_PER_SIMULATED_HOUR = 60

PAYMENT_METHODS = ["cash", "credit", "debit", "mobile"]
PAYMENT_WEIGHTS = [0.15, 0.45, 0.30, 0.10]

CUSTOMER_ARRIVAL_RATES = {
    8:  12,
    9:  18,
    10: 15,
    11: 20,
    12: 30,
    13: 28,
    14: 22,
    15: 20,
    16: 25,
    17: 38,
    18: 42,
    19: 35,
    20: 25,
    21: 15,
}

LOYALTY_CUSTOMER_CHANCE = 0.35

# Will be set to server.push_event if UI is running, otherwise no-op
_push_event = None

def set_push_event(fn):
    global _push_event
    _push_event = fn

def push(data):
    if _push_event:
        _push_event(json.dumps(data))


# ------------------------------------------------------------------
# Database helpers
# ------------------------------------------------------------------

def get_connection():
    return psycopg2.connect(**OLTP_CONFIG)


def load_products(cur):
    cur.execute("SELECT id, name, unit_price, unit_cost, category FROM products")
    return cur.fetchall()  # (id, name, unit_price, unit_cost, category)


def load_employees(cur):
    cur.execute("SELECT id, shift_start, shift_end FROM employees WHERE role = 'Cashier'")
    return cur.fetchall()


def load_loyalty_customers(cur):
    cur.execute("SELECT id, name FROM customers WHERE id != 1")
    return cur.fetchall()  # (id, name)


def get_on_shift_employees(employees, hour):
    on_shift = []
    for emp_id, shift_start, shift_end in employees:
        if shift_start.hour <= hour < shift_end.hour:
            on_shift.append(emp_id)
    return on_shift or [employees[0][0]]


# ------------------------------------------------------------------
# Transaction generation
# ------------------------------------------------------------------

def pick_customer(loyalty_customers):
    if loyalty_customers and random.random() < LOYALTY_CUSTOMER_CHANCE:
        return random.choice(loyalty_customers)
    return (1, "Walk-In Customer")


def pick_products(products):
    num_items = random.randint(1, 8)
    selected  = random.sample(products, min(num_items, len(products)))
    cart = []
    for prod_id, name, unit_price, unit_cost, category in selected:
        quantity = random.randint(1, 4)
        cart.append({
            "product_id": prod_id,
            "product":    name,
            "unit_price": float(unit_price),
            "unit_cost":  float(unit_cost),
            "quantity":   quantity,
            "subtotal":   round(float(unit_price) * quantity, 2)
        })
    return cart


def insert_transaction(cur, customer_id, employee_id, sim_time, cart):
    total   = round(sum(item["subtotal"] for item in cart), 2)
    payment = random.choices(PAYMENT_METHODS, weights=PAYMENT_WEIGHTS, k=1)[0]

    cur.execute(
        """INSERT INTO transactions
               (customer_id, employee_id, transaction_time, payment_method, total_amount)
           VALUES (%s, %s, %s, %s, %s) RETURNING id""",
        (customer_id, employee_id, sim_time, payment, total)
    )
    transaction_id = cur.fetchone()[0]

    for item in cart:
        cur.execute(
            """INSERT INTO transaction_items
                   (transaction_id, product_id, quantity, unit_price_at_sale, subtotal)
               VALUES (%s, %s, %s, %s, %s)""",
            (transaction_id, item["product_id"], item["quantity"],
             item["unit_price"], item["subtotal"])
        )

    return transaction_id, total, payment


def update_inventory(cur, cart):
    low_stock = []
    for item in cart:
        cur.execute(
            """UPDATE inventory
               SET quantity_on_hand = quantity_on_hand - %s
               WHERE product_id = %s
               RETURNING quantity_on_hand, reorder_threshold""",
            (item["quantity"], item["product_id"])
        )
        result = cur.fetchone()
        if result and result[0] <= result[1]:
            low_stock.append((item["product_id"], item["product"]))
    return low_stock


def create_purchase_order(cur, product_id, sim_time):
    cur.execute("SELECT supplier_id, unit_cost FROM products WHERE id = %s", (product_id,))
    row = cur.fetchone()
    if not row:
        return
    supplier_id, unit_cost = row
    cur.execute(
        """INSERT INTO purchase_orders
               (supplier_id, product_id, quantity_ordered, cost_per_unit, order_date)
           VALUES (%s, %s, %s, %s, %s)""",
        (supplier_id, product_id, 100, float(unit_cost), sim_time)
    )
    cur.execute(
        """UPDATE inventory
           SET quantity_on_hand = quantity_on_hand + 100, last_restocked = %s
           WHERE product_id = %s""",
        (sim_time, product_id)
    )


# ------------------------------------------------------------------
# Simulation loop
# ------------------------------------------------------------------

def simulate_hour(cur, hour, sim_date, products, employees, loyalty_customers, stats, sim_day):
    arrival_rate  = CUSTOMER_ARRIVAL_RATES.get(hour, 10)
    num_customers = max(1, int(random.gauss(arrival_rate, arrival_rate * 0.2)))
    on_shift      = get_on_shift_employees(employees, hour)
    reorders_this_hour = 0

    for _ in range(num_customers):
        minute   = random.randint(0, 59)
        second   = random.randint(0, 59)
        sim_time = datetime(sim_date.year, sim_date.month, sim_date.day, hour, minute, second)

        customer_id, customer_name = pick_customer(loyalty_customers)
        employee_id = random.choice(on_shift)
        cart        = pick_products(products)

        transaction_id, total, payment = insert_transaction(
            cur, customer_id, employee_id, sim_time, cart
        )

        # Push transaction event to UI
        push({
            "type":     "transaction",
            "day":      sim_day,
            "hour":     hour,
            "sim_time": sim_time.strftime("%H:%M"),
            "customer": customer_name,
            "items":    [{"quantity": i["quantity"], "product": i["product"]} for i in cart],
            "total":    total,
            "payment":  payment
        })

        low_stock = update_inventory(cur, cart)
        for product_id, product_name in low_stock:
            create_purchase_order(cur, product_id, sim_time)
            reorders_this_hour += 1
            push({
                "type":     "reorder",
                "sim_time": sim_time.strftime("%H:%M"),
                "product":  product_name
            })

        stats["transactions"] += 1
        stats["items_sold"]   += sum(i["quantity"] for i in cart)
        stats["revenue"]      += sum(i["subtotal"] for i in cart)
        stats["cost"]         += sum(i["unit_cost"] * i["quantity"] for i in cart)

    return num_customers, reorders_this_hour


def run_simulation(sim_day_number=1):
    print("-" * 50)
    print(f"GROCERY STORE SIMULATION - DAY {sim_day_number}")
    print("-" * 50)

    conn = get_connection()
    cur  = conn.cursor()

    products          = load_products(cur)
    employees         = load_employees(cur)
    loyalty_customers = load_loyalty_customers(cur)
    sim_date          = date.today()

    print(f"Loaded {len(products)} products, {len(employees)} cashiers, "
          f"{len(loyalty_customers)} loyalty customers.")

    push({
        "type": "day_start",
        "day":  sim_day_number
    })

    stats = {"transactions": 0, "items_sold": 0, "revenue": 0.0, "cost": 0.0}

    try:
        for hour in range(STORE_OPEN_HOUR, STORE_CLOSE_HOUR):
            hour_label = f"{hour:02d}:00 - {hour+1:02d}:00"
            print(f"  Simulating hour {hour_label}...", end=" ", flush=True)

            customers, reorders = simulate_hour(
                cur, hour, sim_date, products, employees,
                loyalty_customers, stats, sim_day_number
            )
            conn.commit()

            print(f"{customers} customers | {reorders} reorders triggered")

            push({
                "type":      "hour",
                "hour":      hour,
                "label":     hour_label,
                "customers": customers,
                "reorders":  reorders
            })

            time.sleep(SECONDS_PER_SIMULATED_HOUR)

        profit = stats["revenue"] - stats["cost"]
        push({
            "type":         "day_end",
            "day":          sim_day_number,
            "transactions": stats["transactions"],
            "revenue":      round(stats["revenue"], 2),
            "profit":       round(profit, 2)
        })

        print("\n" + "-" * 50)
        print("DAY COMPLETE - SUMMARY")
        print("-" * 50)
        print(f"  Total transactions : {stats['transactions']}")
        print(f"  Total items sold   : {stats['items_sold']}")
        print(f"  Total revenue      : ${stats['revenue']:,.2f}")
        print("-" * 50)

    except Exception as e:
        conn.rollback()
        print(f"\nSimulation error: {e}")
        raise

    finally:
        cur.close()
        conn.close()


if __name__ == "__main__":
    import sys
    day_number = int(sys.argv[1]) if len(sys.argv) > 1 else 1
    run_simulation(sim_day_number=day_number)
