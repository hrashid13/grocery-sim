import time
import os
import json
import psycopg2
from datetime import datetime

import server
import simulator
from etl import run_etl

# ------------------------------------------------------------------
# Configuration
# ------------------------------------------------------------------

PAUSE_BETWEEN_DAYS = 5
DAY_COUNTER_FILE   = "current_day.txt"
STATE_FILE         = "sim_state.json"

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


# ------------------------------------------------------------------
# Day counter
# ------------------------------------------------------------------

def load_current_day():
    if os.path.exists(DAY_COUNTER_FILE):
        with open(DAY_COUNTER_FILE, "r") as f:
            try:
                return int(f.read().strip())
            except ValueError:
                return 1
    return 1


def save_current_day(day):
    with open(DAY_COUNTER_FILE, "w") as f:
        f.write(str(day))


# ------------------------------------------------------------------
# State tracking
# Tracks whether the last day completed fully so we can recover
# from Ctrl+C interruptions cleanly
# ------------------------------------------------------------------

def load_state():
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE, "r") as f:
            try:
                return json.load(f)
            except (ValueError, KeyError):
                return {}
    return {}


def save_state(data):
    with open(STATE_FILE, "w") as f:
        json.dump(data, f)


def mark_day_started(day):
    save_state({"day": day, "stage": "simulation", "complete": False})


def mark_etl_started(day):
    save_state({"day": day, "stage": "etl", "complete": False})


def mark_day_complete(day):
    save_state({"day": day, "stage": "complete", "complete": True})


# ------------------------------------------------------------------
# Recovery
# If we find an incomplete day on startup, clean it up before
# resuming so we don't get duplicate or partial data
# ------------------------------------------------------------------

def recover_if_needed(day):
    state = load_state()

    if not state or state.get("complete", True):
        return day  # last run finished cleanly

    incomplete_day = state.get("day")
    stage          = state.get("stage")

    if incomplete_day != day:
        return day  # mismatch, just proceed

    print(f"\nDetected incomplete day {incomplete_day} (interrupted during {stage}).")
    print("Cleaning up before restarting that day...")

    try:
        # Clear any partial OLTP transactions from the interrupted day
        oltp_conn = psycopg2.connect(**OLTP_CONFIG)
        oltp_cur  = oltp_conn.cursor()
        oltp_cur.execute("DELETE FROM transaction_items")
        oltp_cur.execute("DELETE FROM transactions")
        oltp_cur.execute("DELETE FROM purchase_orders")
        oltp_cur.execute("UPDATE inventory SET quantity_on_hand = 150, last_restocked = NULL")
        oltp_conn.commit()
        oltp_cur.close()
        oltp_conn.close()
        print("  OLTP cleared and inventory reset.")

        # If ETL had started, remove any partial OLAP data for that day
        if stage == "etl":
            olap_conn = psycopg2.connect(**OLAP_CONFIG)
            olap_cur  = olap_conn.cursor()
            olap_cur.execute("DELETE FROM fact_sales WHERE simulated_day = %s", (incomplete_day,))
            olap_cur.execute("DELETE FROM dim_time   WHERE simulated_day = %s", (incomplete_day,))
            olap_conn.commit()
            olap_cur.close()
            olap_conn.close()
            print(f"  Partial OLAP data for day {incomplete_day} removed.")

        print(f"  Recovery complete. Restarting day {incomplete_day} fresh.\n")

    except Exception as e:
        print(f"  Recovery error: {e}")
        print("  Proceeding anyway -- check your data manually if needed.")

    return incomplete_day


# ------------------------------------------------------------------
# Health checks
# ------------------------------------------------------------------

def check_databases():
    print("Checking database connections...")
    for label, config in [("OLTP", OLTP_CONFIG), ("OLAP", OLAP_CONFIG)]:
        try:
            conn = psycopg2.connect(**config)
            conn.close()
            print(f"  {label} connection OK.")
        except Exception as e:
            print(f"  {label} connection FAILED: {e}")
            return False
    return True


def check_seeded():
    try:
        conn  = psycopg2.connect(**OLTP_CONFIG)
        cur   = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM products")
        count = cur.fetchone()[0]
        cur.close()
        conn.close()
        if count == 0:
            print("  WARNING: No products found. Run seeder.py first.")
            return False
        print(f"  Seed data OK ({count} products found).")
        return True
    except Exception as e:
        print(f"  Seed check failed: {e}")
        return False


# ------------------------------------------------------------------
# Main loop
# ------------------------------------------------------------------

def run_forever():
    print("=" * 50)
    print("GROCERY STORE SIMULATION - CONTINUOUS RUNNER")
    print(f"Started at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 50)

    if not check_databases():
        print("\nCannot start. Check that Docker containers are running.")
        return

    if not check_seeded():
        print("\nCannot start. Run seeder.py first.")
        return

    # Wire simulator events to the UI
    simulator.set_push_event(server.push_event)

    # Start web server in background
    server.start_server(host="0.0.0.0", port=5000)

    day = load_current_day()

    # Recover from any interrupted run before starting
    day = recover_if_needed(day)

    print(f"\nResuming from day {day}.")
    print("Live feed available at http://localhost:5000")
    print("Press Ctrl+C to stop.\n")

    server.push_event('{"type":"system","time":"","message":"Runner started. Simulation beginning..."}')

    try:
        while True:
            day_started = datetime.now()
            print(f"\n{'=' * 50}")
            print(f"STARTING DAY {day} | {day_started.strftime('%Y-%m-%d %H:%M:%S')}")
            print(f"{'=' * 50}\n")

            # Mark simulation started so recovery knows what to clean up
            mark_day_started(day)

            simulator.run_simulation(sim_day_number=day)

            # Mark ETL started before we begin migration
            mark_etl_started(day)
            server.push_event(f'{{"type":"etl","message":"Running end-of-day ETL for day {day}..."}}')
            print()
            run_etl(sim_day=day)
            server.push_event(f'{{"type":"etl","message":"ETL complete. OLAP updated for day {day}. OLTP reset for day {day+1}."}}')

            # Mark complete and advance day counter
            mark_day_complete(day)
            save_current_day(day + 1)

            elapsed = (datetime.now() - day_started).total_seconds()
            print(f"\nDay {day} complete in {elapsed:.1f} seconds.")
            print(f"Next day starts in {PAUSE_BETWEEN_DAYS} seconds...")
            time.sleep(PAUSE_BETWEEN_DAYS)

            day += 1

    except KeyboardInterrupt:
        print(f"\n\nRunner stopped during day {day}.")
        print("State saved. Restart runner to recover and resume cleanly.")
        save_current_day(day)


if __name__ == "__main__":
    run_forever()
