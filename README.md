# Grocery Store Simulation

A self-running grocery store simulation that demonstrates a full OLTP to OLAP data pipeline. The simulation generates realistic transactions throughout a store day, migrates the data to an analytical database at end of day, and includes a live web feed showing transactions as they happen.

## Architecture

- **OLTP Database** (PostgreSQL) - Handles live transactional data. Resets each simulated day.
- **OLAP Database** (PostgreSQL) - Star schema data warehouse. Accumulates history across all simulated days.
- **Simulation Engine** - Generates customer arrivals, purchases, and inventory changes using realistic traffic patterns.
- **ETL Script** - Migrates end-of-day OLTP data into the OLAP star schema.
- **Live Feed** - Flask web server showing transactions in real time at `http://localhost:5000`.
- **Continuous Runner** - Runs the simulation indefinitely with crash recovery. Designed for deployment on a Raspberry Pi.

## Simulated Store Details

- Store hours: 8:00 AM to 10:00 PM (14 simulated hours)
- Each simulated hour = 1 real minute (full day = 14 minutes)
- 44 products across 7 categories: Produce, Dairy, Bakery, Frozen, Pantry, Meat, Beverages
- 8 employees with realistic shift times
- 20 loyalty customers plus anonymous walk-in customers
- Rush hour traffic spikes at 9am, 12pm, 5pm, and 6pm
- Automatic inventory reordering when stock drops below threshold

## Project Structure

```
grocery-sim/
├── docker-compose.yml      # Spins up OLTP and OLAP Postgres containers
├── seeder.py               # Populates static reference data (run once)
├── simulator.py            # Simulation engine
├── etl.py                  # End-of-day OLTP to OLAP migration
├── server.py               # Flask live feed web server
├── runner.py               # Continuous runner with crash recovery
├── main.py                 # Manual multi-day runner
├── init/
│   ├── oltp_schema.sql     # Transactional schema
│   └── olap_schema.sql     # Star schema
└── reports/
    └── queries.sql         # Analytical queries for the OLAP database
```

## Setup

### Requirements

- Docker and Docker Compose
- Python 3.8+
- pip packages: `psycopg2-binary`, `flask`

```bash
pip install psycopg2-binary flask
```

### 1. Start the databases

```bash
docker compose up -d
```

This starts two Postgres containers:
- OLTP on port `5434`
- OLAP on port `5435`

### 2. Seed the OLTP database (run once)

```bash
python seeder.py
```

### 3. Run the simulation

**Continuous runner (recommended):**
```bash
python runner.py
```

**Manual run for a specific number of days:**
```bash
python main.py 7        # run 7 days starting from day 1
python main.py 5 8      # run 5 days starting from day 8
```

Open `http://localhost:5000` to watch the live transaction feed.

## Crash Recovery

The runner tracks simulation state in `sim_state.json`. If stopped mid-day with Ctrl+C, restarting `runner.py` will automatically detect the incomplete day, clean up any partial data from both databases, and restart that day fresh.

## Connecting to the OLAP Database

Use any Postgres client (DBeaver recommended):

| Field    | Value         |
|----------|---------------|
| Host     | localhost     |
| Port     | 5435          |
| Database | grocery_olap  |
| Username | grocery_user  |
| Password | grocery_pass  |

## Analytical Queries

See `reports/queries.sql` for pre-built queries covering:

- Daily revenue summary
- Revenue by hour of day
- Top 10 best selling products
- Revenue by product category
- Loyalty vs walk-in customer spend
- Payment method breakdown
- Cashier performance
- Rush hour vs off-peak comparison
- Category trends across days
- Slowest moving products

## Raspberry Pi Deployment

The continuous runner is designed to run headlessly on a Raspberry Pi. Tested target hardware is Raspberry Pi 2 Model B (1GB RAM) with a 32GB SD card running Raspberry Pi OS Lite.

To connect to the OLAP database remotely from another machine on the same network, use the Pi's local IP address instead of `localhost` in your database client.
