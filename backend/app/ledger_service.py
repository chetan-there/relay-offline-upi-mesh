"""
Debit sender, credit receiver, write a ledger row - all inside one SQL
transaction, committed or rolled back together. The unique constraint on
transactions.packet_hash is the final backstop: if this function is somehow
invoked twice for the same packet, the second insert fails on commit and is
treated as a duplicate rather than a double-settlement.
"""
import threading

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from . import models
from .schemas import IngestResult

SEED_ACCOUNTS = [
    ("alice", "Alice", 2000),
    ("bob", "Bob", 500),
    ("carol", "Carol", 1200),
]

# In-process guard around the read-modify-write below (also keeps a single
# shared Session safe across threads). Across processes/workers, correctness
# comes from MySQL: SELECT ... FOR UPDATE row locks on the two accounts
# plus the UNIQUE constraint on transactions.packet_hash.
_settle_lock = threading.Lock()


def seed_accounts(db: Session):
    if db.query(models.Account).count() > 0:
        return
    for account_id, label, balance in SEED_ACCOUNTS:
        db.add(models.Account(id=account_id, label=label, balance=balance))
    db.commit()


def list_accounts(db: Session):
    return db.query(models.Account).order_by(models.Account.id).all()


def get_account(db: Session, account_id: str):
    return db.query(models.Account).filter(models.Account.id == account_id).first()


def list_transactions(db: Session, limit: int = 20):
    return (
        db.query(models.Transaction)
        .order_by(models.Transaction.id.desc())
        .limit(limit)
        .all()
    )


def settle(db: Session, sender: str, receiver: str, amount: int, packet_hash: str, nonce: str) -> IngestResult:
    with _settle_lock:
        existing = db.query(models.Transaction).filter(models.Transaction.packet_hash == packet_hash).first()
        if existing:
            return IngestResult(outcome="DUPLICATE_DROPPED", packet_hash=packet_hash,
                                 reason="packetHash already settled (DB constraint)")

        # Row-lock both accounts (always in id order, so concurrent settlements
        # can't deadlock). MySQL holds the locks until commit/rollback.
        locked = (
            db.query(models.Account)
            .filter(models.Account.id.in_({sender, receiver}))
            .order_by(models.Account.id)
            .with_for_update()
            .all()
        )
        by_id = {a.id: a for a in locked}
        sender_acct = by_id.get(sender)
        receiver_acct = by_id.get(receiver)

        if sender_acct is None or receiver_acct is None:
            db.rollback()  # release the row locks
            unknown = sender if sender_acct is None else receiver
            return IngestResult(outcome="REJECTED", packet_hash=packet_hash, reason=f"Unknown account: {unknown}")

        if sender_acct.balance < amount:
            db.rollback()  # release the row locks
            return IngestResult(outcome="REJECTED", packet_hash=packet_hash,
                                 reason="Insufficient funds at settlement time")

        sender_acct.balance -= amount
        receiver_acct.balance += amount

        tx = models.Transaction(
            sender=sender, receiver=receiver, amount=amount,
            packet_hash=packet_hash, nonce=nonce, status="SETTLED",
        )
        db.add(tx)

        try:
            db.commit()
        except IntegrityError:
            db.rollback()
            return IngestResult(outcome="DUPLICATE_DROPPED", packet_hash=packet_hash,
                                 reason="packetHash already settled (race on DB constraint)")

        db.refresh(tx)
        return IngestResult(outcome="SETTLED", packet_hash=packet_hash, transaction_id=tx.id)


def reset(db: Session):
    db.query(models.Transaction).delete()
    db.query(models.Account).delete()
    db.commit()
    seed_accounts(db)
