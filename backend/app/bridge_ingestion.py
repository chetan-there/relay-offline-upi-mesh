"""
The one function real bridge nodes' HTTP calls resolve to. Same pipeline as
the Node.js and Java rebuilds:
  [1] hash ciphertext
  [2] atomically claim the hash (dedupe before spending CPU on RSA)
  [3] decrypt + verify (AES-GCM tag catches tampering)
  [4] freshness check (reject anything older than 24h - replay defense)
  [5] settle inside the ledger
"""
import time

from sqlalchemy.orm import Session

from . import ledger_service, server_keys
from .crypto_service import DecryptionError, decrypt_from_client, hash_ciphertext
from .idempotency_service import idempotency_service
from .schemas import IngestResult, MeshPacket

FRESHNESS_WINDOW_MS = 24 * 60 * 60 * 1000
CLOCK_SKEW_TOLERANCE_MS = 60_000


def ingest_packet(db: Session, packet: MeshPacket) -> IngestResult:
    if not packet.ciphertext:
        return IngestResult(outcome="INVALID", reason="Missing or malformed ciphertext")

    packet_hash = hash_ciphertext(packet.ciphertext)

    first_claimer = idempotency_service.claim(packet_hash)
    if not first_claimer:
        return IngestResult(outcome="DUPLICATE_DROPPED", packet_hash=packet_hash,
                             reason="Already claimed by an earlier delivery")

    try:
        payload = decrypt_from_client(server_keys.get_private_key(), packet.ciphertext)
    except DecryptionError:
        return IngestResult(outcome="INVALID", packet_hash=packet_hash,
                             reason="Decryption/authentication failed (tampered or malformed)")

    if not payload.sender or not payload.receiver or payload.amount <= 0 or not payload.nonce or not payload.signed_at:
        return IngestResult(outcome="INVALID", packet_hash=packet_hash,
                             reason="Decrypted payload missing required fields")

    age_ms = int(time.time() * 1000) - payload.signed_at
    if age_ms > FRESHNESS_WINDOW_MS or age_ms < -CLOCK_SKEW_TOLERANCE_MS:
        return IngestResult(outcome="INVALID", packet_hash=packet_hash,
                             reason=f"Packet outside freshness window (age {age_ms // 1000}s)")

    return ledger_service.settle(db, payload.sender, payload.receiver, payload.amount, packet_hash, payload.nonce)
