"""Virtual device mesh + gossip protocol simulator, mirroring the Node/Java versions."""
import hashlib
import threading
import time
import uuid
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from . import bridge_ingestion, server_keys
from .crypto_service import encrypt_for_server
from .schemas import DeviceState, FlushResultEntry, LogEntry, MeshPacket, MeshState, PaymentInstruction

DEFAULT_TTL = 5
MAX_LOG_ENTRIES = 50

DEVICE_SEED = [
    ("phone-alice", "Alice's phone", False),
    ("phone-stranger1", "Stranger 1", False),
    ("phone-stranger2", "Stranger 2", False),
    ("phone-bridge", "Bridge node", True),
    ("phone-bob", "Bob's phone", False),
]


class VirtualDevice:
    def __init__(self, id_: str, label: str, has_internet: bool):
        self.id = id_
        self.label = label
        self.has_internet = has_internet
        self.packets: list[MeshPacket] = []


class MeshSimulatorService:
    def __init__(self):
        self._lock = threading.Lock()
        self.devices: dict[str, VirtualDevice] = {}
        self.log: list[LogEntry] = []
        self._seed_devices()

    def _seed_devices(self):
        self.devices = {id_: VirtualDevice(id_, label, has_internet) for id_, label, has_internet in DEVICE_SEED}

    def _push_log(self, message: str):
        self.log.append(LogEntry(at=datetime.now(timezone.utc).isoformat(), message=message))
        if len(self.log) > MAX_LOG_ENTRIES:
            self.log.pop(0)

    def state(self) -> MeshState:
        with self._lock:
            devices = [
                DeviceState(id=d.id, label=d.label, has_internet=d.has_internet, packet_count=len(d.packets))
                for d in self.devices.values()
            ]
            return MeshState(devices=devices, log=list(reversed(self.log)))

    def inject_payment(self, sender: str, receiver: str, amount: int, pin: str) -> MeshPacket:
        with self._lock:
            pin_hash = hashlib.sha256((pin or "").encode("utf-8")).hexdigest()
            payload = PaymentInstruction(
                sender=sender, receiver=receiver, amount=amount,
                pin_hash=pin_hash, nonce=str(uuid.uuid4()), signed_at=int(time.time() * 1000),
            )
            ciphertext = encrypt_for_server(server_keys.get_public_key(), payload)

            packet = MeshPacket(
                packet_id=str(uuid.uuid4()), ttl=DEFAULT_TTL,
                created_at=int(time.time() * 1000), ciphertext=ciphertext,
            )

            origin = self.devices["phone-alice"]
            origin.packets.append(packet)
            self._push_log(
                f"Injected packet {packet.packet_id[:8]}\u2026 at {origin.label} "
                f"(\u20B9{amount}, {sender} \u2192 {receiver})"
            )
            return packet

    def run_gossip_round(self) -> int:
        with self._lock:
            delivered = 0
            snapshot = list(self.devices.values())

            for holder in snapshot:
                for packet in list(holder.packets):
                    if packet.ttl <= 0:
                        continue
                    for other in snapshot:
                        if other.id == holder.id:
                            continue
                        if any(p.packet_id == packet.packet_id for p in other.packets):
                            continue
                        other.packets.append(packet.model_copy(update={"ttl": packet.ttl - 1}))
                        delivered += 1

            self._push_log(f"Gossip round: {delivered} new hop(s) delivered")
            return delivered

    def flush_bridges(self, db: Session) -> list[FlushResultEntry]:
        with self._lock:
            results: list[FlushResultEntry] = []
            for device in self.devices.values():
                if not device.has_internet:
                    continue
                for packet in device.packets:
                    result = bridge_ingestion.ingest_packet(db, packet)
                    results.append(FlushResultEntry(bridge_id=device.id, packet_id=packet.packet_id, **result.model_dump()))
                device.packets = []
            self._push_log(f"Bridges flushed: {len(results)} packet(s) uploaded")
            return results

    def reset(self):
        with self._lock:
            self._seed_devices()
            self.log = []
            self._push_log("Mesh reset")


mesh_simulator_service = MeshSimulatorService()
