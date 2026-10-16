# Relay — Offline UPI Payments Over a Mesh

Relay is a full-stack educational demo of **offline payment packet forwarding with deferred settlement**. A sender creates a payment while disconnected, virtual phones pass the encrypted packet through a simulated mesh, and a bridge device uploads it to the backend when it regains internet access.

> **Important:** This is a simulation, not real UPI or a production payment system. It does not connect to NPCI, banks, UPI IDs, or real Bluetooth hardware. The mesh is simulated in software, and the demo accounts are seeded test accounts.

## Table of contents

- [What the project demonstrates](#what-the-project-demonstrates)
- [Tech stack](#tech-stack)
- [How the demo works](#how-the-demo-works)
- [Architecture](#architecture)
- [Security and reliability concepts](#security-and-reliability-concepts)
- [Project structure](#project-structure)
- [Requirements](#requirements)
- [Run locally](#run-locally)
- [Demo walkthrough](#demo-walkthrough)
- [API reference](#api-reference)
- [Database design](#database-design)
- [Tests](#tests)
- [Limitations and production considerations](#limitations-and-production-considerations)
- [Troubleshooting](#troubleshooting)

## What the project demonstrates

Relay brings together a React dashboard and a Python API to demonstrate three engineering challenges:

1. **Confidentiality and tamper detection:** payment details are encrypted before the packet is carried through the simulated mesh.
2. **Duplicate-delivery protection:** repeated delivery of the same packet should not debit the sender multiple times. The service uses an idempotency claim and a unique database constraint as a second line of defense.
3. **Replay resistance:** the encrypted payment contains a timestamp and unique nonce. Old packets are rejected, and duplicate deliveries are detected.

It also demonstrates REST API design, MySQL persistence, SQL transactions, a simulated gossip protocol, and a transaction ledger.

## Tech stack

| Layer | Technology | Responsibility |
|---|---|---|
| Frontend | React 19, Vite, JavaScript, CSS | Interactive dashboard and payment-flow controls |
| Backend API | Python, FastAPI, Uvicorn | HTTP endpoints and application orchestration |
| Validation | Pydantic | Request/response schemas and JSON field aliases |
| Database access | SQLAlchemy | ORM models, database sessions, and queries |
| Database | MySQL | Persistent demo accounts and transaction ledger |
| MySQL driver | PyMySQL | Python-to-MySQL connection |
| Cryptography | Python `cryptography` package | RSA-OAEP, AES-GCM, and SHA-256 |
| Tests | pytest, HTTPX | Automated tests and API testing support |

## How the demo works

The intended flow is:

1. **Compose a payment.** The dashboard submits the sender, receiver, amount, and demo PIN to the backend.
2. **Create an encrypted packet.** The backend simulates the sender phone, creates a payment instruction with a nonce and timestamp, encrypts it, and injects it into a virtual device.
3. **Spread the packet.** Each gossip round forwards packets between simulated devices and decreases their time-to-live (TTL).
4. **Upload from a bridge.** A virtual device marked as having internet access uploads its packets to the backend.
5. **Validate and settle.** The backend hashes the ciphertext, claims the hash for idempotency, decrypts and validates the payload, checks freshness and account funds, then updates balances and writes a ledger entry in a database transaction.
6. **Inspect the result.** The dashboard refreshes account balances, transaction history, mesh state, and bridge outcomes.

## Architecture

```text
React + Vite dashboard
        |
        | HTTP /api/*
        v
FastAPI routes
        |
        +--> Mesh simulator --> virtual devices / gossip / bridge flush
        |
        +--> Crypto service --> RSA-OAEP + AES-256-GCM
        |
        +--> Bridge ingestion --> hash / idempotency / freshness checks
                                      |
                                      v
                                Ledger service
                                      |
                                      v
                              SQLAlchemy + MySQL
                              accounts + transactions
```

The frontend's Vite development server proxies `/api/*` requests to the backend at `http://localhost:8000`.

## Security and reliability concepts

### 1. Hybrid encryption

The demo uses a hybrid encryption pattern:

- A fresh AES key encrypts the payment payload with AES-GCM.
- The AES key is encrypted with the server's RSA public key using RSA-OAEP.
- The backend uses its RSA private key to recover the AES key and decrypt the payload.
- AES-GCM authenticates the encrypted content. If ciphertext is modified, authentication should fail during decryption.
- SHA-256 produces a fingerprint of the ciphertext for duplicate detection.

The virtual relay devices carry the ciphertext rather than needing to interpret the payment details.

### 2. Idempotency and duplicate deliveries

A bridge may upload the same packet more than once. The ingestion pipeline attempts to claim the ciphertext hash before expensive processing. A repeated claim is treated as a duplicate.

The MySQL database also gives `transactions.packet_hash` a unique constraint. This protects against a second ledger entry for the same packet if application-level duplicate protection is bypassed or lost.

**Implementation note:** the current idempotency cache is in-memory and process-local. It is not a distributed Redis implementation. MySQL's unique constraint is the persistent backstop.

### 3. Replay checks

The encrypted instruction includes a timestamp (`signedAt`) and nonce. The backend rejects packets outside the configured freshness window and uses the packet hash to reject the same ciphertext delivered again. A nonce distinguishes separate payment instructions, including two legitimate payments with the same sender, receiver, and amount.

### 4. Atomic settlement

The ledger service performs the sender debit, receiver credit, and transaction insert in a database transaction. If settlement fails, the database transaction should roll back rather than leave a partial transfer. The unique packet-hash constraint provides an additional safeguard against duplicate ledger rows.

These are demonstrations of engineering patterns, not a claim that the application is safe for real money.

## Project structure

```text
upi-mesh-react-fastapi/
├── README.md
├── RUNNING_STEPS.md
├── backend/
│   ├── .env.example
│   ├── requirements.txt
│   ├── app/
│   │   ├── main.py                  # FastAPI app and startup initialization
│   │   ├── routes.py                # REST API endpoints
│   │   ├── database.py              # MySQL URL, engine, and sessions
│   │   ├── init_db.py               # Create tables and seed demo accounts
│   │   ├── models.py                # Account and Transaction ORM models
│   │   ├── schemas.py               # Pydantic request/response schemas
│   │   ├── crypto_service.py        # Encryption, decryption, and hashing
│   │   ├── server_keys.py           # Demo RSA key pair
│   │   ├── idempotency_service.py   # In-memory duplicate claim
│   │   ├── bridge_ingestion.py      # Packet validation and ingestion flow
│   │   ├── ledger_service.py        # Balances and settlement
│   │   └── mesh_simulator.py        # Virtual devices, gossip, and bridge upload
│   └── tests/
│       ├── conftest.py
│       └── test_idempotency.py
└── frontend/
    ├── package.json
    ├── vite.config.js
    ├── index.html
    └── src/
        ├── main.jsx
        ├── App.jsx
        ├── api.js
        ├── styles.css
        └── components/
            ├── Topbar.jsx
            ├── ControlsPanel.jsx
            ├── MeshPanel.jsx
            ├── LedgerPanel.jsx
            └── Explainer.jsx
```

## Requirements

Install the following before running the application:

- Python 3.12 (the current project environment was set up with Python 3.12)
- Node.js 18 or newer and npm
- MySQL Server 8.x or another compatible MySQL version
- `uv` (used for the Python virtual environment and dependency installation in the current setup)

Check your installations:

```powershell
python --version
node --version
npm --version
mysql --version
uv --version
```

## Run locally

Run the backend and frontend in separate terminals.

### 1. Create a MySQL database

Start MySQL Server, then open MySQL Workbench or a MySQL terminal and run:

```sql
CREATE DATABASE upimesh;
```

If the database already exists, you do not need to create it again. The application creates its tables and seeds demo accounts during startup, as implemented by the backend initialization code.

### 2. Configure the backend

From the repository root, move into the backend directory:

```powershell
cd backend
```

Create `backend/.env` and add your MySQL connection URL:

```dotenv
DATABASE_URL=mysql+pymysql://root:YOUR_PASSWORD@localhost:3306/upimesh
```

Replace `YOUR_PASSWORD` with your local MySQL password. If your MySQL account has no password, the URL format is:

```dotenv
DATABASE_URL=mysql+pymysql://root:@localhost:3306/upimesh
```

Do not commit `.env` or publish your database password. If your password contains URL-reserved characters such as `@`, `:`, `/`, `#`, or `?`, URL-encode those characters in the connection URL.

Create a Python virtual environment and install dependencies using `uv`:

```powershell
uv venv --python 3.12
uv pip install --python .venv\Scripts\python.exe -r requirements.txt
```

Start the API:

```powershell
.venv\Scripts\python.exe -m uvicorn app.main:app --reload --port 8000
```

The API should be available at:

- Backend root: `http://localhost:8000/`
- Interactive API documentation: `http://localhost:8000/docs`
- OpenAPI schema: `http://localhost:8000/openapi.json`
- Demo accounts: `http://localhost:8000/api/accounts`

The backend must be able to connect to MySQL using the `DATABASE_URL` in `backend/.env`.

### 3. Start the frontend

Open a second terminal from the repository root:

```powershell
cd frontend
npm install
npm run dev
```

Open the Vite URL shown in the terminal, usually `http://localhost:5173`.

The Vite configuration proxies `/api/*` to the FastAPI backend on port `8000`. Keep both terminals running while using the dashboard.

## Demo walkthrough

1. **Inject into mesh:** select the sender, receiver, amount, and demo PIN, then submit the payment.
2. **Run gossip round:** click the gossip control to forward packets among virtual devices. Run another round to see the packet spread.
3. **Upload from bridges:** click the bridge-upload control. The internet-enabled virtual bridge submits its packets to the backend.
4. **Inspect settlement:** confirm the sender balance decreases, the receiver balance increases, and a transaction appears in the ledger.
5. **Reset the demo:** use the reset control to restore the demo state before another run.

The seeded demo balances are intended only for local testing. The demo PIN is not a real bank PIN and must not be treated as real authentication.

## API reference

All application endpoints use the `/api` prefix.

| Method | Endpoint | Purpose |
|---|---|---|
| `GET` | `/` | Basic backend status |
| `GET` | `/api/server-key` | Return the server's RSA public key |
| `GET` | `/api/accounts` | List account balances |
| `GET` | `/api/transactions` | List recent ledger transactions |
| `GET` | `/api/mesh/state` | Return virtual-device state and activity |
| `POST` | `/api/demo/send` | Create an encrypted demo payment and inject it into the mesh |
| `POST` | `/api/mesh/gossip` | Run one mesh gossip round |
| `POST` | `/api/mesh/flush` | Upload packets held by internet-enabled bridge devices |
| `POST` | `/api/mesh/reset` | Reset the simulated mesh, idempotency cache, and demo ledger state |
| `POST` | `/api/bridge/ingest` | Accept and process a packet from a bridge |
| `GET` | `/docs` | Interactive Swagger documentation |

### Bridge-ingestion example

`POST /api/bridge/ingest`

```json
{
  "packetId": "550e8400-e29b-41d4-a716-446655440000",
  "ttl": 2,
  "createdAt": 1730000000000,
  "ciphertext": "BASE64_ENCODED_CIPHERTEXT"
}
```

The exact validation rules are defined in `backend/app/schemas.py`. A successful ingestion can return `SETTLED`; repeated delivery can return `DUPLICATE_DROPPED`; invalid, tampered, stale, or otherwise rejected packets return an invalid/rejection outcome with a reason.

For exact request and response schemas, use `http://localhost:8000/docs`.

## Database design

The application uses MySQL through SQLAlchemy.

### `accounts`

Stores demo account identifiers, display labels, and balances.

| Field | Purpose |
|---|---|
| `id` | Account identifier / primary key |
| `label` | Display name |
| `balance` | Demo balance in the smallest configured currency unit (the UI presents rupee amounts) |

### `transactions`

Stores settled transfers.

| Field | Purpose |
|---|---|
| `id` | Transaction identifier |
| `sender` | Sender account, referencing `accounts.id` |
| `receiver` | Receiver account, referencing `accounts.id` |
| `amount` | Transfer amount |
| `packet_hash` | Unique ciphertext hash used to prevent duplicate settlement |
| `nonce` | Nonce from the payment instruction |
| `status` | Transaction status |
| `settled_at` | Database-generated settlement timestamp |

Tables are created by the application's initialization routine when missing. This project does not currently use a formal migration workflow such as Alembic, so schema changes should be managed carefully as the project evolves.

## Tests

Run tests from the `backend/` directory with the project virtual environment active:

```powershell
.venv\Scripts\python.exe -m pytest tests/ -v
```

The test suite covers duplicate/concurrent ingestion and invalid payment scenarios. Depending on the test configuration, tests may use SQLite for a lightweight local pass. If configuring tests against MySQL, use a **separate test database** and ensure `TEST_DATABASE_URL` points to that test database—not your development database—before running destructive test setup.

## Limitations and production considerations

This project is a portfolio/demo implementation. Before any real-money or production use, the following areas require substantial additional work:

- **No real UPI integration:** there is no NPCI or bank-core connection, real VPA validation, KYC, or real payment authorization.
- **No offline proof of funds:** a receiver cannot know for certain that the sender's account has sufficient funds until the backend receives the packet. Competing offline payments can therefore cause one settlement to fail.
- **Simulated mesh:** virtual devices and gossip rounds replace real Bluetooth Low Energy (BLE) or Wi-Fi Direct connections. Background connectivity, discovery, battery use, and mobile OS restrictions are not addressed.
- **Demo cryptographic key lifecycle:** the RSA key pair is generated in memory and regenerated at process startup. Production would need secure key storage, rotation, and a device key-distribution strategy.
- **Process-local idempotency cache:** the in-memory cache is not shared across backend replicas. A distributed deployment needs a shared idempotency store and robust database-level concurrency controls.
- **Bridge authentication:** bridge-ingestion requests are not protected by production-grade device identity or mutual TLS.
- **Demo PIN handling:** the PIN is part of the demo flow, not a real PIN verification or bank authentication system.
- **Operational security:** rate limiting, monitoring, audit logging, secrets management, backups, migrations, alerting, and security reviews are not complete.
- **Reset endpoint:** the demo reset endpoint is destructive to the local demo ledger state and should not be exposed publicly.

The most accurate description is **mesh-routed deferred settlement simulation**, not “real-time offline UPI.”

## Troubleshooting

### `DATABASE_URL is not set`

Ensure `backend/.env` exists and contains a valid `DATABASE_URL` beginning with `mysql+pymysql://`. Restart the backend after changing the file.

### MySQL connection refused

Confirm MySQL Server is running, listening on port `3306`, and that the hostname, username, password, and database name are correct.

### Access denied for MySQL user

Check the credentials in `backend/.env` and confirm that the MySQL user has permission to access the `upimesh` database.

### Password contains special characters

URL-encode reserved characters in the password portion of `DATABASE_URL`.

### `ModuleNotFoundError`

From the backend directory, install dependencies into the project environment:

```powershell
uv pip install --python .venv\Scripts\python.exe -r requirements.txt
```

### `npm` or `node` is not recognized

Install Node.js (including npm), reopen the terminal, and check `node --version` and `npm --version`.

### Frontend loads but API requests fail

Check that FastAPI is running on port `8000` and Vite is running on port `5173`. Inspect the browser console and backend terminal for errors.

### Port is already in use

Stop the process using the port, or start the relevant development server on a different port and update the Vite proxy configuration if necessary.

---

## Author / project notes

This repository is intended as a learning and portfolio project. Keep claims aligned with what the code actually implements, and describe the mesh and payment settlement as a simulation when presenting it to reviewers.
