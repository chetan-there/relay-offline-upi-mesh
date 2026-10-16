
"""
Account and Transaction tables.

Transaction.packet_hash has a UNIQUE constraint to prevent
duplicate settlement of the same payment packet.
"""

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, func
from sqlalchemy.orm import relationship

from .database import Base


class Account(Base):
    __tablename__ = "accounts"

    id = Column(String(36), primary_key=True)
    label = Column(String(255), nullable=False)
    balance = Column(Integer, nullable=False)


class Transaction(Base):
    __tablename__ = "transactions"

    id = Column(String(36), primary_key=True)
    sender = Column(
        String(36),
        ForeignKey("accounts.id"),
        nullable=False,
    )
    receiver = Column(
        String(36),
        ForeignKey("accounts.id"),
        nullable=False,
    )
    amount = Column(Integer, nullable=False)
    packet_hash = Column(String(255), unique=True, nullable=False, index=True)
    nonce = Column(String(255), nullable=False)
    status = Column(String(50), nullable=False, default="SETTLED")
    settled_at = Column(DateTime(timezone=True), server_default=func.now())
