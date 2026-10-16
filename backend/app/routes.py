from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from . import bridge_ingestion, ledger_service, server_keys
from .database import get_db
from .idempotency_service import idempotency_service
from .mesh_simulator import mesh_simulator_service
from .schemas import (
    AccountOut,
    IngestResult,
    MeshPacket,
    MeshState,
    SendRequest,
    TransactionOut,
)

router = APIRouter(prefix="/api")


@router.get("/server-key")
def get_server_key():
    return {"publicKey": server_keys.get_public_key_base64()}


@router.get("/accounts", response_model=list[AccountOut])
def get_accounts(db: Session = Depends(get_db)):
    return ledger_service.list_accounts(db)


@router.get("/transactions", response_model=list[TransactionOut])
def get_transactions(db: Session = Depends(get_db)):
    return ledger_service.list_transactions(db)


@router.get("/mesh/state", response_model=MeshState)
def get_mesh_state():
    return mesh_simulator_service.state()


@router.post("/demo/send")
def demo_send(request: SendRequest, db: Session = Depends(get_db)):
    if request.sender == request.receiver:
        raise HTTPException(status_code=400, detail="Choose a sender and a different receiver.")
    if len(request.pin) < 4:
        raise HTTPException(status_code=400, detail="Enter a PIN of at least 4 digits.")
    if ledger_service.get_account(db, request.sender) is None or ledger_service.get_account(db, request.receiver) is None:
        raise HTTPException(status_code=400, detail="Unknown account.")

    packet = mesh_simulator_service.inject_payment(request.sender, request.receiver, request.amount, request.pin)
    return {"packet": packet, "meshState": mesh_simulator_service.state()}


@router.post("/mesh/gossip")
def mesh_gossip():
    delivered = mesh_simulator_service.run_gossip_round()
    return {"delivered": delivered, "meshState": mesh_simulator_service.state()}


@router.post("/mesh/flush")
def mesh_flush(db: Session = Depends(get_db)):
    results = mesh_simulator_service.flush_bridges(db)
    return {
        "results": results,
        "meshState": mesh_simulator_service.state(),
        "accounts": [AccountOut.model_validate(a) for a in ledger_service.list_accounts(db)],
        "transactions": [TransactionOut.model_validate(t) for t in ledger_service.list_transactions(db)],
    }


@router.post("/mesh/reset")
def mesh_reset(db: Session = Depends(get_db)):
    mesh_simulator_service.reset()
    idempotency_service.reset()
    ledger_service.reset(db)
    return {
        "meshState": mesh_simulator_service.state(),
        "accounts": [AccountOut.model_validate(a) for a in ledger_service.list_accounts(db)],
        "transactions": [TransactionOut.model_validate(t) for t in ledger_service.list_transactions(db)],
    }


@router.post("/bridge/ingest", response_model=IngestResult)
def bridge_ingest(packet: MeshPacket, db: Session = Depends(get_db)):
    """The production endpoint: real bridge nodes POST a MeshPacket here directly."""
    return bridge_ingestion.ingest_packet(db, packet)
