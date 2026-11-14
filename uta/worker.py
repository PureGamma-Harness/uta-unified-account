"""Recoverable, at-least-once consumption of committed exchange events.

Callbacks run outside the database transaction and MUST deduplicate using the
event's sequence. A crash after delivery and before checkpointing redelivers the
event. A lease fences checkpoints, not external systems or arbitrary callbacks.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Callable, Protocol
from uuid import uuid4

from .storage import Database


class EventSource(Protocol):
    def events(self, after: int = 0, limit: int = 100) -> list[dict]: ...


class WorkerError(RuntimeError):
    """An event stream or consumer checkpoint violates its contract."""


class LeaseBusy(WorkerError):
    """Another consumer currently owns this subscription."""


class LeaseLost(WorkerError):
    """Delivery may have occurred, but this worker may no longer checkpoint."""


class OutboxConsumer:
    """One named subscription, with durable cursor and bounded batch processing.

    The source must retain its complete, immutable stream starting at sequence 1.
    Clock synchronization is required across processes. Slow handlers can outlive
    their lease and be delivered concurrently; sink-side idempotency is required.
    """

    def __init__(self, database: Database, source: EventSource, consumer_id: str,
                 handler: Callable[[dict], None], *, batch_size: int = 100,
                 lease_seconds: int = 30,
                 clock: Callable[[], datetime] | None = None):
        if (not isinstance(consumer_id, str) or not consumer_id.strip()
                or len(consumer_id) > 128 or consumer_id != consumer_id.strip()):
            raise ValueError("consumer_id must be a trimmed string of 1..128 characters")
        if type(batch_size) is not int or not 1 <= batch_size <= 1000:
            raise ValueError("batch_size must be an integer in 1..1000")
        if type(lease_seconds) is not int or not 1 <= lease_seconds <= 3600:
            raise ValueError("lease_seconds must be an integer in 1..3600")
        if not callable(handler):
            raise ValueError("handler must be callable")
        self.database = database
        self.source = source
        self.consumer_id = consumer_id
        self.handler = handler
        self.batch_size = batch_size
        self.lease_us = lease_seconds * 1_000_000
        self.clock = clock or (lambda: datetime.now(timezone.utc))
        with database.transaction() as conn:
            conn.execute("""CREATE TABLE IF NOT EXISTS uta_event_consumers (
                consumer_id TEXT PRIMARY KEY,
                cursor INTEGER NOT NULL CHECK(cursor >= 0),
                owner TEXT,
                expires_us INTEGER NOT NULL
            )""")

    def _now(self) -> int:
        now = self.clock()
        if not isinstance(now, datetime) or now.tzinfo is None or now.utcoffset() is None:
            raise WorkerError("worker clock must be timezone-aware")
        delta = now.astimezone(timezone.utc) - datetime(1970, 1, 1, tzinfo=timezone.utc)
        return (delta.days * 86400 + delta.seconds) * 1_000_000 + delta.microseconds

    def cursor(self) -> int:
        with self.database.transaction() as conn:
            row = conn.execute("SELECT cursor FROM uta_event_consumers WHERE consumer_id = ?",
                               (self.consumer_id,)).fetchone()
            return row["cursor"] if row is not None else 0

    def run_once(self) -> int:
        owner = uuid4().hex
        now = self._now()
        with self.database.transaction() as conn:
            conn.execute("""INSERT OR IGNORE INTO uta_event_consumers
                (consumer_id,cursor,owner,expires_us) VALUES (?,0,NULL,0)""",
                         (self.consumer_id,))
            row = conn.execute("SELECT * FROM uta_event_consumers WHERE consumer_id = ?",
                               (self.consumer_id,)).fetchone()
            if row["owner"] is not None and row["expires_us"] > now:
                raise LeaseBusy("subscription has an active worker")
            cursor = row["cursor"]
            conn.execute("""UPDATE uta_event_consumers SET owner=?,expires_us=?
                WHERE consumer_id=?""", (owner, now + self.lease_us, self.consumer_id))
        delivered = 0
        try:
            events = self.source.events(after=cursor, limit=self.batch_size)
            if not isinstance(events, list) or len(events) > self.batch_size:
                raise WorkerError("invalid event batch")
            for event in events:
                if (not isinstance(event, dict) or type(event.get("sequence")) is not int
                        or event["sequence"] != cursor + 1):
                    raise WorkerError("event sequence is missing or out of order")
                sequence = event["sequence"]
                # Check ownership before delivery as well as after it. A handler
                # can still outlive the lease, so this is not sink-side fencing.
                self._check_lease(owner)
                self.handler(event)
                now = self._now()
                with self.database.transaction() as conn:
                    changed = conn.execute("""UPDATE uta_event_consumers
                        SET cursor=?, expires_us=? WHERE consumer_id=? AND owner=?
                        AND cursor=? AND expires_us>?""",
                        (sequence, now + self.lease_us, self.consumer_id,
                         owner, cursor, now)).rowcount
                    if changed != 1:
                        raise LeaseLost("delivery may have succeeded; checkpoint lease expired")
                cursor = sequence
                delivered += 1
            return delivered
        finally:
            with self.database.transaction() as conn:
                conn.execute("""UPDATE uta_event_consumers SET owner=NULL,expires_us=0
                    WHERE consumer_id=? AND owner=?""", (self.consumer_id, owner))

    def _check_lease(self, owner: str) -> None:
        now = self._now()
        with self.database.transaction() as conn:
            row = conn.execute("""SELECT owner,expires_us FROM uta_event_consumers
                WHERE consumer_id=?""", (self.consumer_id,)).fetchone()
            if row is None or row["owner"] != owner or row["expires_us"] <= now:
                raise LeaseLost("subscription lease expired before delivery")
