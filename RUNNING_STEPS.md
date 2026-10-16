# Relay — Running Guide (React + FastAPI + MySQL)

This is the React + Python FastAPI + MySQL rebuild of the offline-UPI-mesh concept. It has two independent halves that talk over HTTP:

```
frontend/   React 19 + Vite — the dashboard
backend/    Python 3.12 + FastAPI + SQLAlchemy + MySQL — the API, crypto, and settlement engine
```

> **Verification note:** the original SQLite version of this project was run and tested end-to-end by its author. The MySQL migration was made in an environment with no MySQL server and no package-install access, so it was only syntax-checked there (`py_compile`). Run Steps 1-4 and the test suite below to confirm it on your machine.

---

## Prerequisites

- **Python 3.10+** and `pip`. Check with `python3 --version`.
- **Node.js 18+** and npm. Check with `node -v`.
- **MySQL 8.0+** running locally (or reachable over the network). Check with `mysql --version`.

---

## Step 0 — Create the MySQL database

Make sure MySQL Server 8.0+ is running. Open MySQL Workbench or the MySQL command-line client and run (choose your own password):

```sql
CREATE DATABASE upimesh CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
CREATE USER 'upimesh_user'@'localhost' IDENTIFIED BY 'CHANGE_ME';
GRANT ALL PRIVILEGES ON upimesh.* TO 'upimesh_user'@'localhost';
FLUSH PRIVILEGES;
```

For the optional integration tests, also create a separate test database:

```sql
CREATE DATABASE upimesh_test CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
GRANT ALL PRIVILEGES ON upimesh_test.* TO 'upimesh_user'@'localhost';
```

Copy `backend/.env.example` to `backend/.env`, then set `DATABASE_URL=mysql+pymysql://upimesh_user:YOUR_PASSWORD@localhost:3306/upimesh`.

## Step 1 — Start the backend

```bash
cd backend
python3 -m venv venv

# macOS/Linux:
source venv/bin/activate
# Windows:
venv\Scripts\activate

pip install -r requirements.txt

# optional: check the connection and create tables + seed accounts without starting the server
python -m app.init_db

uvicorn app.main:app --reload --port 8000
```

What this does:
- Boots FastAPI (via uvicorn) on **http://localhost:8000**.
- Generates a fresh RSA-2048 keypair in memory (`app/server_keys.py`).
- Connects to MySQL using `DATABASE_URL`, creates the `accounts` and `transactions` tables if they don't exist, and seeds three accounts on first run: Alice (₹2000), Bob (₹500), Carol (₹1200). Existing data is **kept** across restarts — use **Reset mesh + ledger** in the UI (or `POST /api/mesh/reset`) to return to the seeded state.
- Exposes the REST API under `/api/*`, and interactive docs at **http://localhost:8000/docs** (FastAPI's built-in Swagger UI — try any endpoint directly from the browser).

**Sanity check** (in a second terminal):
```bash
curl http://localhost:8000/api/accounts
```
Expect a JSON array of the three seeded accounts.

---

## Step 2 — Start the frontend

In a new terminal:

```bash
cd frontend
npm install
npm run dev
```

Open **http://localhost:5173**. The Vite dev server proxies every `/api/*` request to `localhost:8000` (configured in `vite.config.js`), so the dashboard talks to your running backend with no CORS setup needed — this exact proxy path was tested and confirmed working during development.

You should see the "Relay" dashboard with three panels: pipeline controls on the left, mesh state in the middle, and settled state on the right, with the three balances already populated.

---

## Step 3 — Walk through the full payment flow

1. **Compose a payment.** Pick a sender/receiver/amount/PIN and click **Inject into mesh**. This calls `POST /api/demo/send`, which encrypts a `PaymentInstruction` with the backend's RSA public key and places the resulting `MeshPacket` on `phone-alice`.
2. **Run a gossip round** — click twice. Each click calls `POST /api/mesh/gossip`. After two rounds every device should hold the packet.
3. **Bridge walks outside** — click **Bridges upload to backend**. Calls `POST /api/mesh/flush`; only `phone-bridge` uploads. Watch **Balances** update and a new row land in the **Transaction ledger** with a `SETTLED` badge.
4. **Reset mesh + ledger** any time to start over.

---

## Step 4 — Verify the idempotency guarantee yourself

**Option A — the included pytest suite.** From `backend/` (with the venv active):
```bash
pytest tests/ -v
```
Each test runs against in-memory SQLite (always) and against MySQL (only when `TEST_DATABASE_URL` is set; otherwise those cases are reported as skipped). To include MySQL:
```bash
export TEST_DATABASE_URL=mysql+pymysql://upimesh_user:CHANGE_ME@localhost:3306/upimesh_test
pytest tests/ -v          # Windows PowerShell: $env:TEST_DATABASE_URL="..."
```
The test database is **dropped and recreated** on every test, so its name must contain `test` (the suite refuses to run otherwise) — never point it at `upimesh`.

The first test fires 3 real threads at `ingest_packet()` with the identical packet simultaneously and asserts exactly one comes back `SETTLED`.

**Option B — do it by hand with curl**, while the backend is running:
```bash
# 1. Inject a payment and capture its ciphertext
curl -s -X POST localhost:8000/api/demo/send \
  -H 'Content-Type: application/json' \
  -d '{"sender":"alice","receiver":"carol","amount":300,"pin":"1234"}' > send.json

CIPHERTEXT=$(python3 -c "import json; print(json.load(open('send.json'))['packet']['ciphertext'])")
PID=$(python3 -c "import json; print(json.load(open('send.json'))['packet']['packetId'])")

# 2. Fire three identical deliveries at the production endpoint concurrently
for i in 1 2 3; do
  curl -s -X POST localhost:8000/api/bridge/ingest \
    -H 'Content-Type: application/json' \
    -d "{\"packetId\":\"$PID\",\"ttl\":2,\"createdAt\":$(date +%s%3N),\"ciphertext\":\"$CIPHERTEXT\"}" &
done
wait

# 3. Confirm Alice's balance dropped by exactly 300, not 900
curl -s localhost:8000/api/accounts
```
Expect one `"outcome":"SETTLED"` and two `"outcome":"DUPLICATE_DROPPED"`.

**Tamper check:**
```bash
curl -s -X POST localhost:8000/api/bridge/ingest \
  -H 'Content-Type: application/json' \
  -d "{\"packetId\":\"tampered\",\"ttl\":2,\"createdAt\":$(date +%s%3N),\"ciphertext\":\"XcorruptedCiphertext...\"}"
```
Expect `"outcome":"INVALID"` — AES-GCM's built-in auth tag verification fails before any business logic runs.

---

## API reference

| Method | Path | What it does |
|---|---|---|
| GET | `/api/server-key` | Backend's RSA public key (base64) |
| GET | `/api/accounts` | All accounts and balances |
| GET | `/api/transactions` | Last 20 settled transactions |
| GET | `/api/mesh/state` | Current state of every virtual device + activity log |
| POST | `/api/demo/send` | Simulate the sender's phone: encrypt + inject a packet |
| POST | `/api/mesh/gossip` | Run one gossip round across the mesh |
| POST | `/api/mesh/flush` | Devices with internet upload everything they hold |
| POST | `/api/mesh/reset` | Clear the mesh, idempotency cache, and ledger |
| POST | `/api/bridge/ingest` | **The production endpoint.** Real bridges POST a `MeshPacket` here |
| GET | `/docs` | Interactive Swagger UI for the whole API |

All JSON is `camelCase` (e.g. `packetHash`, `hasInternet`) to match the same contract used by the Node.js and Java rebuilds of this project, even though the Python code itself is idiomatic `snake_case` internally (handled by Pydantic's `alias_generator`).

---

## Project structure

```
backend/
├── requirements.txt
├── .env.example             DATABASE_URL placeholder (copy to .env)
├── app/
│   ├── main.py                  FastAPI app, CORS, DB init on startup
│   ├── database.py              SQLAlchemy engine/session (MySQL via DATABASE_URL)
│   ├── init_db.py               Connection check + create tables + seed (python -m app.init_db)
│   ├── models.py                Account, Transaction (SQLAlchemy ORM models)
│   ├── schemas.py                Pydantic request/response shapes (camelCase on the wire)
│   ├── crypto_service.py        RSA-OAEP + AES-256-GCM encrypt/decrypt/hash
│   ├── server_keys.py           RSA-2048 keypair, generated once at import time
│   ├── idempotency_service.py   Thread-safe atomic claim-by-hash
│   ├── ledger_service.py        Debit/credit/ledger-write inside one SQL transaction (row-locked)
│   ├── mesh_simulator.py        Virtual devices, gossip rounds, bridge flush
│   ├── bridge_ingestion.py      hash → claim → decrypt → freshness → settle
│   └── routes.py                All REST endpoints
└── tests/
    ├── conftest.py              Placeholder DATABASE_URL so tests import cleanly
    └── test_idempotency.py      pytest: concurrency, tamper, unknown-account, insufficient-funds

frontend/
├── package.json
├── vite.config.js               Dev-server proxy to :8000
├── index.html
└── src/
    ├── main.jsx
    ├── App.jsx                  Top-level state + data flow
    ├── api.js                   fetch() wrapper for the REST API
    ├── styles.css                Design system
    └── components/
        ├── Topbar.jsx
        ├── ControlsPanel.jsx     Send form + gossip/flush/reset
        ├── MeshPanel.jsx         Device grid + activity log
        ├── LedgerPanel.jsx       Balances, ledger, flush results
        └── Explainer.jsx         "Why it's safe" footer
```

---

## Building for production

**Backend** — run behind a real ASGI server (uvicorn with multiple workers, or behind Gunicorn):
```bash
cd backend
pip install -r requirements.txt
uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 4
```
Set `DATABASE_URL` as a real environment variable on the server (it takes precedence over `backend/.env`), pointing at your production MySQL. Note that the in-memory idempotency cache and mesh simulator are per-process, so with multiple workers the MySQL row locks and the `packet_hash` UNIQUE constraint are what guarantee exactly-once settlement.

**Frontend** — produces static files in `frontend/dist/` (already verified building cleanly: `npm run build` → 22 modules, ~63 KB gzipped JS):
```bash
cd frontend
npm run build
```
Serve `dist/` with any static host, and either point `src/api.js` at the backend's real domain, or put both behind the same reverse proxy so `/api/*` routes to FastAPI.

---

## What's simplified for this demo (and what production would use instead)

| In this demo | In production |
|---|---|
| Single MySQL instance, tables created via `create_all` (no migration tool) | Managed MySQL with replicas and Alembic migrations |
| `threading.Lock` + Python dict for idempotency | Redis: `SET key NX EX 86400` — same atomicity, shared across replicas |
| `threading.Lock` plus MySQL `SELECT ... FOR UPDATE` row locks in settle() | Same row locks (the in-process lock becomes unnecessary) |
| RSA keypair regenerated on every boot | Private key in an HSM/KMS; public key baked into client apps |
| Software-simulated gossip mesh | Real BLE GATT / Wi-Fi Direct between phones |
| No auth on `/api/bridge/ingest` | Mutual TLS or signed bridge-node certificates |
| Single uvicorn process | Multiple workers behind a load balancer, with the idempotency store and DB shared across all of them |

## Honest limitations of the concept

- **The receiver can't verify the sender has funds at send time** — a payment shown on-screen is an IOU until it reaches the backend. If the sender's balance is insufficient by settlement time, the transaction comes back `REJECTED`. Real offline UPI (UPI Lite) solves this with a pre-funded, hardware-backed wallet that proves available funds offline.
- **A malicious sender could double-spend across two separate offline pockets** — whichever packet reaches the backend first wins; the other is `REJECTED`.
- **Background BLE is heavily restricted on modern phones**; a real deployment needs to solve discovery and backgrounding, which this simulation deliberately skips.
- **Metadata leaks**: a stranger's phone carries your encrypted packet even though it can't read it — worth thinking through for a real deployment.

This is best described as **mesh-routed deferred settlement**, not real-time payment.
