"""
The headline tests: a packet delivered by multiple bridges settles exactly
once, and a tampered ciphertext is rejected before touching the ledger.

Run with: pytest tests/ -v   (from the backend/ directory, inside the venv)
"""
import os
import time
from concurrent.futures import ThreadPoolExecutor

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app import bridge_ingestion, ledger_service, server_keys
from app.crypto_service import encrypt_for_server
from app.database import Base
from app.idempotency_service import IdempotencyService
from app.schemas import MeshPacket, PaymentInstruction


@pytest.fixture(params=["sqlite", "mysql"])
def db_session(request):
    """
    Runs every test against two backends:

    - sqlite:   fresh in-memory DB, always available. StaticPool +
                check_same_thread=False pins all threads to one connection
                (a plain ":memory:" URL gives each connection its own DB).
    - mysql: only when TEST_DATABASE_URL is set, e.g.
                mysql+pymysql://user:pass@localhost:3306/upimesh_test
                Tables are DROPPED and recreated, so the database name must
                contain "test" - the fixture refuses anything else.
    """
    if request.param == "sqlite":
        engine = create_engine(
            "sqlite:///:memory:",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
    else:
        url = os.getenv("TEST_DATABASE_URL")
        if not url:
            pytest.skip("TEST_DATABASE_URL not set; skipping MySQL run")
        engine = create_engine(url, pool_pre_ping=True)
        if "test" not in (engine.url.database or "").lower():
            engine.dispose()
            pytest.fail("TEST_DATABASE_URL must point at a database whose name contains 'test'")
        Base.metadata.drop_all(bind=engine)

    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    ledger_service.seed_accounts(session)
    yield session
    session.close()
    if request.param == "mysql":
        Base.metadata.drop_all(bind=engine)
    engine.dispose()


@pytest.fixture
def fresh_idempotency(monkeypatch):
    """Swap in a clean IdempotencyService so tests don't leak claims between each other."""
    fresh = IdempotencyService()
    monkeypatch.setattr(bridge_ingestion, "idempotency_service", fresh)
    return fresh


def _build_packet(sender="alice", receiver="bob", amount=300) -> MeshPacket:
    payload = PaymentInstruction(
        sender=sender, receiver=receiver, amount=amount,
        pin_hash="pinhash", nonce="test-nonce", signed_at=int(time.time() * 1000),
    )
    ciphertext = encrypt_for_server(server_keys.get_public_key(), payload)
    return MeshPacket(packet_id="test-packet", ttl=2, created_at=int(time.time() * 1000), ciphertext=ciphertext)


def test_single_packet_delivered_by_three_bridges_settles_exactly_once(db_session, fresh_idempotency):
    packet = _build_packet(amount=300)
    alice_before = ledger_service.get_account(db_session, "alice").balance

    with ThreadPoolExecutor(max_workers=3) as pool:
        results = list(pool.map(lambda _: bridge_ingestion.ingest_packet(db_session, packet), range(3)))

    outcomes = [r.outcome for r in results]
    assert outcomes.count("SETTLED") == 1, "exactly one delivery should settle"
    assert outcomes.count("DUPLICATE_DROPPED") == 2, "the other two should be dropped as duplicates"

    alice_after = ledger_service.get_account(db_session, "alice").balance
    assert alice_after == alice_before - 300, "sender should be debited exactly once"


def test_tampered_ciphertext_is_rejected(db_session, fresh_idempotency):
    packet = _build_packet(amount=100)
    tampered_ciphertext = ("X" if packet.ciphertext[0] != "X" else "Y") + packet.ciphertext[1:]
    tampered_packet = packet.model_copy(update={"ciphertext": tampered_ciphertext})

    result = bridge_ingestion.ingest_packet(db_session, tampered_packet)

    assert result.outcome == "INVALID"
    assert "decryption" in result.reason.lower() or "authentication" in result.reason.lower()


def test_unknown_account_is_rejected(db_session, fresh_idempotency):
    packet = _build_packet(sender="alice", receiver="nobody", amount=50)
    result = bridge_ingestion.ingest_packet(db_session, packet)
    assert result.outcome == "REJECTED"
    assert "unknown account" in result.reason.lower()


def test_insufficient_funds_is_rejected(db_session, fresh_idempotency):
    packet = _build_packet(sender="bob", receiver="alice", amount=999_999)
    result = bridge_ingestion.ingest_packet(db_session, packet)
    assert result.outcome == "REJECTED"
    assert "insufficient" in result.reason.lower()
