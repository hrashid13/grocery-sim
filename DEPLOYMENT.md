# Raspberry Pi Zero 2 W Deployment Guide

This guide covers deploying the grocery store simulation on a Raspberry Pi Zero 2 W
using native PostgreSQL instead of Docker to keep memory usage within the 512MB RAM limit.

---

## What You Need

- Raspberry Pi Zero 2 W
- 32GB microSD card
- Power supply (micro USB, 5V 2.5A recommended)
- A computer to flash the SD card

---

## Step 1: Flash the SD Card

1. Download and install **Raspberry Pi Imager** on your laptop:
   https://www.raspberrypi.com/software/

2. Open Raspberry Pi Imager and choose:
   - Device: Raspberry Pi Zero 2 W
   - OS: Raspberry Pi OS Lite (64-bit) -- no desktop needed
   - Storage: your 32GB SD card

3. Before writing, click the settings gear icon and configure:
   - Hostname: `grocerypi`
   - Enable SSH: yes
   - Username: `pi`
   - Password: choose something you'll remember
   - WiFi SSID and password: your home network
   - WiFi country: US

4. Write the image to the SD card.

---

## Step 2: First Boot

Insert the SD card into the Pi and power it on. Wait about 60-90 seconds for
the first boot to complete.

Find the Pi's IP address by checking your router's connected devices list and
looking for `grocerypi`, then SSH in from your laptop:

```bash
ssh pi@grocerypi.local
```

Or use the IP address directly:

```bash
ssh pi@<pi-ip-address>
```

---

## Step 3: Update the System

```bash
sudo apt update && sudo apt upgrade -y
```

This may take a few minutes on first run.

---

## Step 4: Install PostgreSQL

```bash
sudo apt install -y postgresql postgresql-client
```

Start the service and enable it on boot:

```bash
sudo systemctl start postgresql
sudo systemctl enable postgresql
```

---

## Step 5: Create the Two Databases

Switch to the postgres user and open the PostgreSQL prompt:

```bash
sudo -u postgres psql
```

Run the following commands to create the user and both databases:

```sql
CREATE USER grocery_user WITH PASSWORD 'grocery_pass';

CREATE DATABASE grocery_oltp OWNER grocery_user;
CREATE DATABASE grocery_olap OWNER grocery_user;

GRANT ALL PRIVILEGES ON DATABASE grocery_oltp TO grocery_user;
GRANT ALL PRIVILEGES ON DATABASE grocery_olap TO grocery_user;

\q
```

---

## Step 6: Load the Schemas

Copy the schema files to the Pi (run these from your laptop, not the Pi):

```bash
scp init/oltp_schema.sql pi@grocerypi.local:~/
scp init/olap_schema.sql pi@grocerypi.local:~/
```

Back on the Pi, load both schemas:

```bash
psql -U grocery_user -d grocery_oltp -f ~/oltp_schema.sql
psql -U grocery_user -d grocery_olap -f ~/olap_schema.sql
```

---

## Step 7: Install Python Dependencies

```bash
sudo apt install -y python3-pip python3-psycopg2
pip3 install flask --break-system-packages
```

---

## Step 8: Copy the Project Files

From your laptop, copy the project folder to the Pi:

```bash
scp seeder.py simulator.py etl.py server.py runner.py pi@grocerypi.local:~/grocery-sim/
```

Or clone directly from GitHub on the Pi:

```bash
sudo apt install -y git
git clone https://github.com/YOUR_USERNAME/grocery-sim.git ~/grocery-sim
cd ~/grocery-sim
```

---

## Step 9: Update Port Configuration

The Pi runs Postgres natively, so both databases share the default port 5432
but are separate databases. Update the port in all Python files from `5434`/`5435`
to `5432` for both OLTP and OLAP configs.

The quickest way is to run these two commands from inside the `grocery-sim` folder:

```bash
sed -i 's/"port":     5434/"port":     5432/g' seeder.py simulator.py etl.py runner.py
sed -i 's/"port":     5435/"port":     5432/g' etl.py runner.py
```

---

## Step 10: Seed and Run

```bash
cd ~/grocery-sim
python3 seeder.py
python3 runner.py
```

The live feed will be available at:

```
http://grocerypi.local:5000
```

Or via IP address from any device on the same WiFi network:

```
http://<pi-ip-address>:5000
```

---

## Step 11: Allow Remote Database Connections (Optional)

To connect DBeaver on your laptop directly to the Pi's OLAP database for
running analytical queries, you need to allow remote connections to Postgres.

Edit the PostgreSQL config to listen on all interfaces:

```bash
sudo nano /etc/postgresql/15/main/postgresql.conf
```

Find and change:
```
#listen_addresses = 'localhost'
```
to:
```
listen_addresses = '*'
```

Then edit the host-based authentication file:

```bash
sudo nano /etc/postgresql/15/main/pg_hba.conf
```

Add this line at the bottom:
```
host    all             grocery_user        0.0.0.0/0               md5
```

Restart Postgres:

```bash
sudo systemctl restart postgresql
```

Now in DBeaver on your laptop, create a new connection with:

| Field    | Value                  |
|----------|------------------------|
| Host     | grocerypi.local        |
| Port     | 5432                   |
| Database | grocery_olap           |
| Username | grocery_user           |
| Password | grocery_pass           |

---

## Step 12: Run the Simulation Automatically on Boot (Optional)

To have the simulation start automatically whenever the Pi powers on,
create a systemd service:

```bash
sudo nano /etc/systemd/system/grocery-sim.service
```

Paste the following:

```ini
[Unit]
Description=Grocery Store Simulation
After=network.target postgresql.service

[Service]
Type=simple
User=pi
WorkingDirectory=/home/pi/grocery-sim
ExecStart=/usr/bin/python3 /home/pi/grocery-sim/runner.py
Restart=on-failure
RestartSec=10

[Install]
WantedBy=multi-user.target
```

Enable and start it:

```bash
sudo systemctl daemon-reload
sudo systemctl enable grocery-sim
sudo systemctl start grocery-sim
```

To check if it is running:

```bash
sudo systemctl status grocery-sim
```

To watch the logs live:

```bash
journalctl -u grocery-sim -f
```

Now the simulation will start automatically on every boot without you needing
to SSH in.

---

## Troubleshooting

**Cannot connect via SSH:**
Make sure the Pi has fully booted (wait 90 seconds), and that the WiFi
credentials were set correctly in Raspberry Pi Imager. Try the IP address
directly if `grocerypi.local` does not resolve.

**psql: error: connection refused:**
Make sure PostgreSQL is running: `sudo systemctl status postgresql`

**Port number in pg_hba.conf not found:**
The PostgreSQL version folder name may differ. Check with:
`ls /etc/postgresql/`

**Runner exits immediately:**
Check that seeder.py was run first and that both databases exist with the
correct schema loaded.
