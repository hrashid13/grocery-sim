import psycopg2
from psycopg2.extras import execute_values

# ------------------------------------------------------------------
# Database connection
# ------------------------------------------------------------------

DB_CONFIG = {
    "host":     "localhost",
    "port":     5434,
    "dbname":   "grocery_oltp",
    "user":     "grocery_user",
    "password": "grocery_pass"
}

def get_connection():
    return psycopg2.connect(**DB_CONFIG)


# ------------------------------------------------------------------
# Seed data
# ------------------------------------------------------------------

SUPPLIERS = [
    ("Fresh Farms Produce",     "freshfarms@supplier.com",   1),
    ("Dairy Direct Co.",        "dairydirect@supplier.com",  2),
    ("Sunrise Bakery Supply",   "sunrise@supplier.com",      1),
    ("Frozen Foods Inc.",       "frozenfoods@supplier.com",  3),
    ("Pantry Wholesale",        "pantry@supplier.com",       2),
    ("Butcher Block Meats",     "butcherblock@supplier.com", 1),
    ("Beverage World",          "beverageworld@supplier.com",2),
]

# (name, category, subcategory, unit_price, unit_cost, supplier_index)
# supplier_index is 0-based index into SUPPLIERS list above
PRODUCTS = [
    # Produce
    ("Bananas (bunch)",         "Produce", "Fruit",         0.69,  0.30, 0),
    ("Gala Apples (lb)",        "Produce", "Fruit",         1.29,  0.55, 0),
    ("Strawberries (pint)",     "Produce", "Fruit",         3.49,  1.80, 0),
    ("Broccoli (head)",         "Produce", "Vegetable",     1.79,  0.80, 0),
    ("Baby Spinach (5oz)",      "Produce", "Leafy Greens",  3.29,  1.50, 0),
    ("Roma Tomatoes (lb)",      "Produce", "Vegetable",     1.49,  0.65, 0),
    ("Yellow Onions (3lb bag)", "Produce", "Vegetable",     2.49,  1.00, 0),
    ("Russet Potatoes (5lb)",   "Produce", "Vegetable",     3.99,  1.75, 0),

    # Dairy
    ("Whole Milk (gallon)",     "Dairy",   "Milk",          3.79,  2.20, 1),
    ("2% Milk (gallon)",        "Dairy",   "Milk",          3.59,  2.10, 1),
    ("Large Eggs (dozen)",      "Dairy",   "Eggs",          3.29,  1.90, 1),
    ("Cheddar Cheese (8oz)",    "Dairy",   "Cheese",        4.49,  2.50, 1),
    ("Butter (1lb)",            "Dairy",   "Butter",        5.29,  3.10, 1),
    ("Greek Yogurt (32oz)",     "Dairy",   "Yogurt",        5.99,  3.20, 1),
    ("Sour Cream (16oz)",       "Dairy",   "Cream",         2.49,  1.20, 1),

    # Bakery
    ("White Sandwich Bread",    "Bakery",  "Bread",         2.99,  1.20, 2),
    ("Whole Wheat Bread",       "Bakery",  "Bread",         3.49,  1.50, 2),
    ("Bagels (6 pack)",         "Bakery",  "Bagels",        3.99,  1.80, 2),
    ("Blueberry Muffins (4pk)", "Bakery",  "Muffins",       4.49,  2.00, 2),
    ("Flour Tortillas (10ct)",  "Bakery",  "Tortillas",     2.99,  1.30, 2),

    # Frozen
    ("Frozen Pizza (pepperoni)","Frozen",  "Pizza",         6.99,  3.50, 3),
    ("Ice Cream (1.5qt)",       "Frozen",  "Dessert",       4.99,  2.40, 3),
    ("Frozen Broccoli (12oz)",  "Frozen",  "Vegetables",    1.99,  0.90, 3),
    ("Chicken Nuggets (24oz)",  "Frozen",  "Poultry",       7.49,  3.80, 3),
    ("Frozen Waffles (8ct)",    "Frozen",  "Breakfast",     3.49,  1.60, 3),

    # Pantry
    ("Pasta (spaghetti 16oz)",  "Pantry",  "Pasta",         1.49,  0.60, 4),
    ("Marinara Sauce (24oz)",   "Pantry",  "Sauces",        2.99,  1.30, 4),
    ("Chicken Broth (32oz)",    "Pantry",  "Soups",         2.49,  1.10, 4),
    ("Canned Diced Tomatoes",   "Pantry",  "Canned Goods",  1.29,  0.55, 4),
    ("Peanut Butter (16oz)",    "Pantry",  "Spreads",       3.49,  1.70, 4),
    ("Strawberry Jam (18oz)",   "Pantry",  "Spreads",       3.29,  1.50, 4),
    ("White Rice (2lb)",        "Pantry",  "Grains",        2.49,  1.00, 4),
    ("Olive Oil (16oz)",        "Pantry",  "Oils",          7.99,  4.20, 4),
    ("Saltine Crackers (16oz)", "Pantry",  "Snacks",        2.79,  1.20, 4),
    ("Corn Flakes (18oz)",      "Pantry",  "Cereal",        3.99,  1.80, 4),

    # Meat
    ("Chicken Breast (lb)",     "Meat",    "Poultry",       5.99,  3.20, 5),
    ("Ground Beef 80/20 (lb)",  "Meat",    "Beef",          5.49,  3.00, 5),
    ("Bacon (12oz)",            "Meat",    "Pork",          6.99,  3.80, 5),
    ("Pork Chops (lb)",         "Meat",    "Pork",          4.99,  2.70, 5),

    # Beverages
    ("Orange Juice (52oz)",     "Beverages","Juice",        4.49,  2.20, 6),
    ("Apple Juice (64oz)",      "Beverages","Juice",        3.99,  1.90, 6),
    ("Coca-Cola (12pk cans)",   "Beverages","Soda",         7.99,  4.50, 6),
    ("Spring Water (24pk)",     "Beverages","Water",        4.99,  2.30, 6),
    ("Coffee (12oz ground)",    "Beverages","Coffee",       8.99,  4.80, 6),
]

EMPLOYEES = [
    ("Maria Santos",   "Cashier",   "08:00", "16:00"),
    ("James Okafor",   "Cashier",   "08:00", "16:00"),
    ("Linda Park",     "Cashier",   "12:00", "20:00"),
    ("Derek Williams", "Cashier",   "12:00", "20:00"),
    ("Sara Ahmed",     "Cashier",   "14:00", "22:00"),
    ("Tom Nguyen",     "Cashier",   "14:00", "22:00"),
    ("Rachel Green",   "Supervisor","08:00", "16:00"),
    ("Mike Torres",    "Supervisor","14:00", "22:00"),
]

CUSTOMERS = [
    ("Alice Johnson",   "alice.johnson@email.com"),
    ("Bob Smith",       "bob.smith@email.com"),
    ("Carol Davis",     "carol.davis@email.com"),
    ("David Lee",       "david.lee@email.com"),
    ("Emma Wilson",     "emma.wilson@email.com"),
    ("Frank Martinez",  "frank.martinez@email.com"),
    ("Grace Kim",       "grace.kim@email.com"),
    ("Henry Brown",     "henry.brown@email.com"),
    ("Irene Clark",     "irene.clark@email.com"),
    ("Jason White",     "jason.white@email.com"),
    ("Karen Hall",      "karen.hall@email.com"),
    ("Leo Robinson",    "leo.robinson@email.com"),
    ("Mia Walker",      "mia.walker@email.com"),
    ("Nathan Young",    "nathan.young@email.com"),
    ("Olivia Adams",    "olivia.adams@email.com"),
    ("Paul Scott",      "paul.scott@email.com"),
    ("Quinn Thomas",    "quinn.thomas@email.com"),
    ("Rachel Harris",   "rachel.harris@email.com"),
    ("Sam Nelson",      "sam.nelson@email.com"),
    ("Tina Carter",     "tina.carter@email.com"),
]


# ------------------------------------------------------------------
# Seeding functions
# ------------------------------------------------------------------

def seed_suppliers(cur):
    print("Seeding suppliers...")
    execute_values(cur,
        "INSERT INTO suppliers (name, contact_info, lead_time_days) VALUES %s RETURNING id",
        SUPPLIERS
    )
    ids = [row[0] for row in cur.fetchall()]
    print(f"  Inserted {len(ids)} suppliers.")
    return ids


def seed_products(cur, supplier_ids):
    print("Seeding products...")
    rows = [
        (name, category, subcategory, unit_price, unit_cost, supplier_ids[sup_idx])
        for name, category, subcategory, unit_price, unit_cost, sup_idx in PRODUCTS
    ]
    execute_values(cur,
        """INSERT INTO products (name, category, subcategory, unit_price, unit_cost, supplier_id)
           VALUES %s RETURNING id""",
        rows
    )
    ids = [row[0] for row in cur.fetchall()]
    print(f"  Inserted {len(ids)} products.")
    return ids


def seed_inventory(cur, product_ids):
    print("Seeding inventory...")
    rows = [(pid, 150, 20) for pid in product_ids]
    execute_values(cur,
        "INSERT INTO inventory (product_id, quantity_on_hand, reorder_threshold) VALUES %s",
        rows
    )
    print(f"  Inserted inventory for {len(rows)} products.")


def seed_employees(cur):
    print("Seeding employees...")
    execute_values(cur,
        "INSERT INTO employees (name, role, shift_start, shift_end) VALUES %s",
        EMPLOYEES
    )
    print(f"  Inserted {len(EMPLOYEES)} employees.")


def seed_customers(cur):
    print("Seeding loyalty customers...")
    execute_values(cur,
        "INSERT INTO customers (name, email) VALUES %s ON CONFLICT DO NOTHING",
        CUSTOMERS
    )
    print(f"  Inserted {len(CUSTOMERS)} loyalty customers (plus existing walk-in).")


# ------------------------------------------------------------------
# Main
# ------------------------------------------------------------------

def main():
    print("Connecting to OLTP database...")
    conn = get_connection()
    cur  = conn.cursor()

    try:
        supplier_ids = seed_suppliers(cur)
        product_ids  = seed_products(cur, supplier_ids)
        seed_inventory(cur, product_ids)
        seed_employees(cur)
        seed_customers(cur)

        conn.commit()
        print("\nDatabase seeded successfully.")

    except Exception as e:
        conn.rollback()
        print(f"\nError during seeding: {e}")
        raise

    finally:
        cur.close()
        conn.close()


if __name__ == "__main__":
    main()
