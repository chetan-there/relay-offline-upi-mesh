"""
Atomic "claim" on a packet hash. FastAPI's sync routes run in a threadpool,
so real concurrent threads can call claim() with the same hash at the same
moment. A threading.Lock around the check-and-set makes this atomic - the
same guarantee ConcurrentHashMap#putIfAbsent gives in the Java version, or
Node's single-threaded event loop gives for free. In production this
becomes Redis: `SET key NX EX 86400` - identical semantics, shared across
replicas instead of one process's memory.
"""
import threading
import time

TTL_SECONDS = 24 * 60 * 60


class IdempotencyService:
    def __init__(self):
        self._lock = threading.Lock()
        self._seen: dict[str, float] = {}

    def claim(self, packet_hash: str) -> bool:
        """Returns True if this is the first claim (caller should proceed), False if a duplicate."""
        with self._lock:
            if packet_hash in self._seen:
                return False
            self._seen[packet_hash] = time.time()
            return True

    def evict_expired(self):
        cutoff = time.time() - TTL_SECONDS
        with self._lock:
            expired = [h for h, claimed_at in self._seen.items() if claimed_at < cutoff]
            for h in expired:
                del self._seen[h]

    def reset(self):
        with self._lock:
            self._seen.clear()

    def size(self) -> int:
        with self._lock:
            return len(self._seen)


idempotency_service = IdempotencyService()
