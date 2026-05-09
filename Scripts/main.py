import sys
import time
from datetime import datetime

from simulator import run_simulation
from etl import run_etl

# ------------------------------------------------------------------
# Configuration
# ------------------------------------------------------------------

DEFAULT_DAYS = 1
PAUSE_BETWEEN_DAYS = 5  # seconds to pause between days so you can see the summary


# ------------------------------------------------------------------
# Orchestrator
# ------------------------------------------------------------------

def run(num_days, start_day=1):
    print("=" * 50)
    print("GROCERY STORE SIMULATION - MAIN")
    print(f"Running {num_days} day(s) starting from day {start_day}")
    print("=" * 50)

    for day in range(start_day, start_day + num_days):
        day_started = datetime.now()
        print(f"\nStarting day {day} at {day_started.strftime('%H:%M:%S')}\n")

        # Step 1: Run the simulation for the day
        run_simulation(sim_day_number=day)

        # Step 2: Run ETL to migrate data to OLAP and reset OLTP
        print()
        run_etl(sim_day=day)

        elapsed = (datetime.now() - day_started).total_seconds()
        print(f"\nDay {day} completed in {elapsed:.1f} seconds.")

        # Pause between days unless it's the last one
        if day < start_day + num_days - 1:
            print(f"Pausing {PAUSE_BETWEEN_DAYS} seconds before day {day + 1}...")
            time.sleep(PAUSE_BETWEEN_DAYS)

    print("\n" + "=" * 50)
    print(f"ALL {num_days} DAY(S) COMPLETE")
    print(f"Check your OLAP database for analytical data.")
    print("=" * 50)


# ------------------------------------------------------------------
# Entry point
# ------------------------------------------------------------------

if __name__ == "__main__":
    # Usage:
    #   python main.py              -> runs 1 day starting from day 1
    #   python main.py 5            -> runs 5 days starting from day 1
    #   python main.py 5 3          -> runs 5 days starting from day 3

    num_days  = int(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_DAYS
    start_day = int(sys.argv[2]) if len(sys.argv) > 2 else 1

    run(num_days=num_days, start_day=start_day)
