from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, ConfigDict, field_validator
from pydantic.alias_generators import to_camel

# All response models serialize as camelCase over the wire (to match the
# same API contract as the Node.js and Java rebuilds of this project) while
# staying snake_case internally, which is idiomatic Python. FastAPI's
# jsonable_encoder defaults to by_alias=True, so this "just works" for every
# route that returns these models, including when nested inside a plain dict.
_CAMEL_CONFIG = ConfigDict(alias_generator=to_camel, populate_by_name=True)


# ---- DB-backed response shapes ----

class AccountOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    label: str
    balance: int


class TransactionOut(BaseModel):
    model_config = _CAMEL_CONFIG | ConfigDict(from_attributes=True)

    id: int
    sender: str
    receiver: str
    amount: int
    packet_hash: str
    nonce: str
    status: str
    settled_at: Optional[datetime] = None


# ---- Mesh wire types ----

class MeshPacket(BaseModel):
    model_config = _CAMEL_CONFIG

    packet_id: str
    ttl: int
    created_at: int  # epoch millis
    ciphertext: str


class PaymentInstruction(BaseModel):
    model_config = _CAMEL_CONFIG

    sender: str
    receiver: str
    amount: int
    pin_hash: str
    nonce: str
    signed_at: int  # epoch millis


# ---- Requests ----

class SendRequest(BaseModel):
    sender: str
    receiver: str
    amount: int
    pin: str

    @field_validator("amount")
    @classmethod
    def amount_positive(cls, v):
        if v <= 0:
            raise ValueError("Amount must be a positive number.")
        return v


# ---- Pipeline results ----

class IngestResult(BaseModel):
    model_config = _CAMEL_CONFIG

    outcome: str  # SETTLED | DUPLICATE_DROPPED | INVALID | REJECTED
    packet_hash: Optional[str] = None
    reason: Optional[str] = None
    transaction_id: Optional[int] = None


class FlushResultEntry(IngestResult):
    bridge_id: str
    packet_id: str


class DeviceState(BaseModel):
    model_config = _CAMEL_CONFIG

    id: str
    label: str
    has_internet: bool
    packet_count: int


class LogEntry(BaseModel):
    model_config = _CAMEL_CONFIG

    at: str
    message: str


class MeshState(BaseModel):
    model_config = _CAMEL_CONFIG

    devices: List[DeviceState]
    log: List[LogEntry]
