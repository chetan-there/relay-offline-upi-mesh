from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .init_db import init_db
from .routes import router

app = FastAPI(title="Relay — Offline UPI Over a Mesh", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router)


@app.on_event("startup")
def on_startup():
    # Creates missing tables and seeds the demo accounts on first run. Existing
    # MySQL data is kept across restarts; use the "Reset mesh + ledger"
    # button (POST /api/mesh/reset) to return to the seeded state.
    init_db()


@app.get("/")
def root():
    return {"status": "ok", "service": "upi-mesh-relay-fastapi"}
