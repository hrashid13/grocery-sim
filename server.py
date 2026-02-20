import queue
import threading
from flask import Flask, Response, render_template_string
from datetime import datetime

app = Flask(__name__)

# ------------------------------------------------------------------
# Shared event queue - simulator pushes to this, SSE reads from it
# ------------------------------------------------------------------

event_queue = queue.Queue(maxsize=500)


def push_event(message):
    try:
        event_queue.put_nowait(message)
    except queue.Full:
        pass  # drop oldest if queue is full


# ------------------------------------------------------------------
# HTML page
# ------------------------------------------------------------------

HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>Grocery Store - Live Transactions</title>
    <style>
        * { box-sizing: border-box; margin: 0; padding: 0; }

        body {
            background: #1a1a2e;
            color: #e0e0e0;
            font-family: 'Courier New', monospace;
            display: flex;
            flex-direction: column;
            height: 100vh;
        }

        header {
            background: #16213e;
            border-bottom: 2px solid #0f3460;
            padding: 16px 24px;
            display: flex;
            align-items: center;
            gap: 16px;
        }

        header h1 {
            font-size: 1.2rem;
            color: #e94560;
            letter-spacing: 2px;
            text-transform: uppercase;
        }

        #status {
            font-size: 0.75rem;
            color: #4caf50;
            margin-left: auto;
        }

        #stats-bar {
            background: #16213e;
            padding: 10px 24px;
            display: flex;
            gap: 40px;
            border-bottom: 1px solid #0f3460;
            font-size: 0.8rem;
            color: #a0a0b0;
        }

        #stats-bar span { color: #e0e0e0; font-weight: bold; }

        #feed {
            flex: 1;
            overflow-y: auto;
            padding: 12px 24px;
            display: flex;
            flex-direction: column;
            gap: 6px;
        }

        .event {
            background: #16213e;
            border-left: 3px solid #0f3460;
            padding: 8px 12px;
            border-radius: 2px;
            font-size: 0.82rem;
            line-height: 1.5;
            animation: fadeIn 0.3s ease;
        }

        .event.transaction  { border-left-color: #4caf50; }
        .event.reorder      { border-left-color: #ff9800; }
        .event.hour         { border-left-color: #e94560; background: #1f1f3a; }
        .event.etl          { border-left-color: #9c27b0; background: #1f1f3a; }
        .event.day          { border-left-color: #e94560; background: #0f3460;
                              font-size: 0.9rem; font-weight: bold; }
        .event.system       { border-left-color: #607d8b; color: #a0a0b0; }

        .time   { color: #607d8b; margin-right: 8px; }
        .label  { font-weight: bold; margin-right: 8px; }
        .amount { color: #4caf50; }
        .warn   { color: #ff9800; }
        .purple { color: #ce93d8; }

        @keyframes fadeIn {
            from { opacity: 0; transform: translateX(-6px); }
            to   { opacity: 1; transform: translateX(0); }
        }

        #feed::-webkit-scrollbar { width: 6px; }
        #feed::-webkit-scrollbar-track { background: #1a1a2e; }
        #feed::-webkit-scrollbar-thumb { background: #0f3460; border-radius: 3px; }
    </style>
</head>
<body>
    <header>
        <h1>Grocery Store Live Feed</h1>
        <div id="status">Connecting...</div>
    </header>

    <div id="stats-bar">
        Day: <span id="stat-day">-</span>
        &nbsp;&nbsp;|&nbsp;&nbsp;
        Hour: <span id="stat-hour">-</span>
        &nbsp;&nbsp;|&nbsp;&nbsp;
        Transactions today: <span id="stat-txn">0</span>
        &nbsp;&nbsp;|&nbsp;&nbsp;
        Revenue today: $<span id="stat-rev">0.00</span>
    </div>

    <div id="feed"></div>

    <script>
        const feed     = document.getElementById('feed');
        const status   = document.getElementById('status');
        const statDay  = document.getElementById('stat-day');
        const statHour = document.getElementById('stat-hour');
        const statTxn  = document.getElementById('stat-txn');
        const statRev  = document.getElementById('stat-rev');

        let txnCount = 0;
        let revenue  = 0.0;

        function addEvent(html, type) {
            const div = document.createElement('div');
            div.className = 'event ' + (type || '');
            div.innerHTML = html;
            feed.appendChild(div);
            feed.scrollTop = feed.scrollHeight;

            // Keep max 300 rows in DOM
            while (feed.children.length > 300) {
                feed.removeChild(feed.firstChild);
            }
        }

        const es = new EventSource('/stream');

        es.onopen = () => { status.textContent = 'Live'; status.style.color = '#4caf50'; };

        es.onerror = () => { status.textContent = 'Reconnecting...'; status.style.color = '#ff9800'; };

        es.onmessage = (e) => {
            const data = JSON.parse(e.data);

            if (data.type === 'transaction') {
                txnCount++;
                revenue += data.total;
                statTxn.textContent = txnCount;
                statRev.textContent = revenue.toFixed(2);
                statDay.textContent = data.day;
                statHour.textContent = data.hour + ':00';

                const items = data.items.map(i =>
                    i.quantity + 'x ' + i.product
                ).join(', ');

                addEvent(
                    '<span class="time">' + data.sim_time + '</span>' +
                    '<span class="label">SALE</span>' +
                    data.customer + ' &mdash; ' + items +
                    ' &mdash; <span class="amount">$' + data.total.toFixed(2) + '</span>' +
                    ' [' + data.payment + ']',
                    'transaction'
                );

            } else if (data.type === 'reorder') {
                addEvent(
                    '<span class="time">' + data.sim_time + '</span>' +
                    '<span class="label warn">REORDER</span>' +
                    '<span class="warn">' + data.product + ' stock low &mdash; purchase order placed (+100 units)</span>',
                    'reorder'
                );

            } else if (data.type === 'hour') {
                statHour.textContent = data.hour + ':00';
                addEvent(
                    '<span class="label">HOUR</span>' +
                    data.label + ' &mdash; ' + data.customers + ' customers &mdash; ' +
                    data.reorders + ' reorder(s)',
                    'hour'
                );

            } else if (data.type === 'day_start') {
                txnCount = 0;
                revenue  = 0.0;
                statTxn.textContent = '0';
                statRev.textContent = '0.00';
                statDay.textContent = data.day;
                addEvent(
                    'DAY ' + data.day + ' &mdash; Store opening at 08:00',
                    'day'
                );

            } else if (data.type === 'day_end') {
                addEvent(
                    '<span class="label">DAY ' + data.day + ' CLOSED</span>' +
                    'Transactions: ' + data.transactions +
                    ' &mdash; Revenue: <span class="amount">$' + data.revenue.toFixed(2) + '</span>' +
                    ' &mdash; Profit: <span class="amount">$' + data.profit.toFixed(2) + '</span>',
                    'day'
                );

            } else if (data.type === 'etl') {
                addEvent(
                    '<span class="label purple">ETL</span>' +
                    '<span class="purple">' + data.message + '</span>',
                    'etl'
                );

            } else if (data.type === 'system') {
                addEvent(
                    '<span class="time">' + data.time + '</span>' + data.message,
                    'system'
                );
            }
        };
    </script>
</body>
</html>
"""


@app.route("/")
def index():
    return render_template_string(HTML)


@app.route("/stream")
def stream():
    def event_stream():
        while True:
            try:
                message = event_queue.get(timeout=30)
                yield f"data: {message}\n\n"
            except queue.Empty:
                yield ": keepalive\n\n"

    return Response(event_stream(), mimetype="text/event-stream")


# ------------------------------------------------------------------
# Start server in background thread
# ------------------------------------------------------------------

def start_server(host="0.0.0.0", port=5000):
    thread = threading.Thread(
        target=lambda: app.run(host=host, port=port, debug=False, use_reloader=False),
        daemon=True
    )
    thread.start()
    print(f"Live feed running at http://localhost:{port}")
