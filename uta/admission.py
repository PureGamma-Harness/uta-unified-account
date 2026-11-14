"""Bounded group commit for the authoritative local order admission path.

Each group holds the same BEGIN IMMEDIATE authority as synchronous commands.
Business rejections roll back one savepoint. Storage, configuration corruption,
or unexpected errors roll back the entire group. No successful Future or queued
rejection is published until the outer transaction commits. This is not an
atomic client multi-order instruction, replicated log, or cross-shard commit.
"""
from __future__ import annotations

from collections import deque
from concurrent.futures import Future
from dataclasses import dataclass
from decimal import Decimal
import math
import sqlite3
from threading import Condition, Thread, current_thread
from time import monotonic, monotonic_ns

from .ledger import LedgerError
from .service import ExchangeService, ServiceError
from .storage import StorageError


class AdmissionFuture(Future):
    """A normal Future with process-local monotonic diagnostics, not a receipt."""
    def __init__(self):
        super().__init__()
        self._admission_enqueued_ns = None
        self._admission_started_ns = None
        self._admission_completed_ns = None

    @property
    def admission_enqueued_ns(self):
        return self._admission_enqueued_ns

    @property
    def admission_started_ns(self):
        return self._admission_started_ns

    @property
    def admission_completed_ns(self):
        return self._admission_completed_ns


@dataclass(frozen=True)
class _Command:
    kind: str
    arguments: tuple
    reduce_only: bool
    future: AdmissionFuture


_FATAL_CODES = {"storage_unavailable", "storage_corrupt", "configuration_corrupt",
                "configuration_conflict", "invalid_configuration", "invalid_clock",
                "schema_version", "wrong_authority", "ledger_rejected", "precision_error"}
_EXPECTED_UNAVAILABLE = {"market_unavailable", "market_incomplete"}


def _business_rejection(error: ServiceError) -> bool:
    # A SQL/FULL error hidden under a service wrapper is still a transaction
    # failure, even when another layer assigned it a business-like status.
    pending, seen = [error], set()
    while pending:
        current = pending.pop()
        if current is None or id(current) in seen:
            continue
        seen.add(id(current))
        if isinstance(current, (sqlite3.Error, LedgerError, StorageError)):
            return False
        pending.extend((current.__cause__, current.__context__))
    return (error.code not in _FATAL_CODES
            and (400 <= error.status < 500 or error.code in _EXPECTED_UNAVAILABLE))


class AdmissionBatcher:
    """One auto-started non-daemon writer with a bounded pending queue.

    Only input validation is done before enqueue. Financial state, freshness and
    policy are revalidated by the core inside the transaction. Pending Futures
    may be cancelled without financial effects; running Futures cannot cancel an
    execution. Use close() or a context manager to drain accepted work. Callbacks
    must be nonblocking and cannot submit/close this same worker recursively.
    """
    def __init__(self, exchange: ExchangeService, *, max_batch_size: int = 32,
                 max_delay_ms: float = 2, queue_capacity: int = 1024):
        if not isinstance(exchange, ExchangeService):
            raise ValueError("exchange must be an ExchangeService")
        if type(max_batch_size) is not int or not 1 <= max_batch_size <= 256:
            raise ValueError("max_batch_size must be an integer in 1..256")
        if (isinstance(max_delay_ms, bool) or not isinstance(max_delay_ms, (float, int))
                or not math.isfinite(max_delay_ms) or not 0 <= max_delay_ms <= 1000):
            raise ValueError("max_delay_ms must be finite and in 0..1000")
        if type(queue_capacity) is not int or not 1 <= queue_capacity <= 65536:
            raise ValueError("queue_capacity must be an integer in 1..65536")
        self.exchange = exchange
        self.max_batch_size, self.max_delay_ms, self.queue_capacity = max_batch_size, max_delay_ms, queue_capacity
        self._condition = Condition()
        self._queue = deque()
        self._accepting = True
        self._running = 0
        self._counts = {name: 0 for name in ("committed_batches", "committed_commands", "business_rejected",
            "market_rejected", "cancelled_pending", "technical_failed", "overloaded", "callback_failures")}
        self._thread = Thread(target=self._run, name="uta-admission", daemon=False)
        try:
            self._thread.start()
        except BaseException:
            # If native thread creation succeeded before an interruption, it
            # will observe the closed, empty queue and exit without any writes.
            with self._condition:
                self._accepting = False
                self._condition.notify_all()
            if self._thread.ident is not None:
                self._thread.join()
            raise

    def _error(self, code: str, message: str, status: int = 503) -> AdmissionFuture:
        future = AdmissionFuture()
        future._admission_completed_ns = monotonic_ns()
        future.set_exception(ServiceError(code, message, status))
        return future

    def submit_order(self, account_id: str, order_id: str, symbol: str,
                     quantity: Decimal, limit_price: Decimal, *, reduce_only: bool = False) -> AdmissionFuture:
        try:
            self.exchange._validate_order_command(account_id, order_id, symbol, quantity, limit_price,
                                                 reduce_only=reduce_only)
        except ServiceError as exc:
            return self._error(exc.code, str(exc), exc.status)
        return self._enqueue("submit", (account_id, order_id, symbol, quantity, limit_price), reduce_only)

    def cancel_order(self, account_id: str, order_id: str) -> AdmissionFuture:
        try:
            self.exchange._validate_cancel_command(account_id, order_id)
        except ServiceError as exc:
            return self._error(exc.code, str(exc), exc.status)
        return self._enqueue("cancel", (account_id, order_id), False)

    def _enqueue(self, kind: str, arguments: tuple, reduce_only: bool) -> AdmissionFuture:
        if current_thread() is self._thread:
            return self._error("admission_reentrant", "worker callbacks cannot submit to the same admission worker")
        with self._condition:
            if not self._accepting:
                return self._error("admission_closed", "admission worker is closed")
            if len(self._queue) >= self.queue_capacity:
                self._counts["overloaded"] += 1
                return self._error("admission_overloaded", "admission queue is full; retry using the original command ID")
            future = AdmissionFuture()
            future._admission_enqueued_ns = monotonic_ns()
            self._queue.append(_Command(kind, arguments, reduce_only, future))
            self._condition.notify()
            return future

    def stats(self) -> dict:
        with self._condition:
            return {**self._counts, "queued": len(self._queue), "running": self._running,
                    "accepting": self._accepting, "worker_alive": self._thread.is_alive()}

    def close(self, wait: bool = True) -> None:
        if type(wait) is not bool:
            raise ValueError("wait must be a boolean")
        if current_thread() is self._thread:
            raise RuntimeError("worker callbacks cannot close their own admission worker")
        with self._condition:
            self._accepting = False
            self._condition.notify_all()
        if wait:
            self._thread.join()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback):
        self.close()

    def _run(self) -> None:
        while True:
            with self._condition:
                while not self._queue and self._accepting:
                    self._condition.wait()
                if not self._queue:
                    return
                batch = [self._queue.popleft()]
                deadline = monotonic() + self.max_delay_ms / 1000
                while len(batch) < self.max_batch_size:
                    if self._queue:
                        batch.append(self._queue.popleft())
                        continue
                    remaining = deadline - monotonic()
                    if not self._accepting or remaining <= 0:
                        break
                    self._condition.wait(remaining)
            commands = []
            for command in batch:
                if command.future.set_running_or_notify_cancel():
                    command.future._admission_started_ns = monotonic_ns()
                    commands.append(command)
                else:
                    with self._condition:
                        self._counts["cancelled_pending"] += 1
            if commands:
                with self._condition:
                    self._running = len(commands)
                self._commit_batch(commands)
                with self._condition:
                    self._running = 0

    def _commit_batch(self, commands: list[_Command]) -> None:
        outcomes = []
        try:
            with self.exchange._transaction() as connection:
                for index, command in enumerate(commands):
                    savepoint = "admission_" + str(index)
                    connection.execute("SAVEPOINT " + savepoint)
                    try:
                        if command.kind == "submit":
                            result = self.exchange._admit_order(connection, *command.arguments,
                                                               reduce_only=command.reduce_only)
                        else:
                            result = self.exchange._cancel_order(connection, *command.arguments)
                    except ServiceError as exc:
                        if not connection.in_transaction or not _business_rejection(exc):
                            raise
                        connection.execute("ROLLBACK TO SAVEPOINT " + savepoint)
                        connection.execute("RELEASE SAVEPOINT " + savepoint)
                        outcomes.append((None, exc))
                    else:
                        connection.execute("RELEASE SAVEPOINT " + savepoint)
                        outcomes.append((result, None))
            # The COMMIT (including deferred constraints) completed above.
        except BaseException as exc:
            with self._condition:
                self._counts["technical_failed"] += len(commands)
            for command in commands:
                error = ServiceError("admission_batch_failed", "batch receipt unavailable; query or retry using the original command IDs", 503)
                error.__cause__ = exc
                self._complete(command.future, error=error)
            return
        with self._condition:
            self._counts["committed_batches"] += 1
            self._counts["committed_commands"] += sum(error is None for _, error in outcomes)
            self._counts["business_rejected"] += sum(error is not None and error.status < 500 for _, error in outcomes)
            self._counts["market_rejected"] += sum(error is not None and error.status >= 500 for _, error in outcomes)
        for command, (result, error) in zip(commands, outcomes):
            self._complete(command.future, result=result, error=error)

    def _complete(self, future: AdmissionFuture, *, result=None, error=None) -> None:
        future._admission_completed_ns = monotonic_ns()
        try:
            if error is not None:
                future.set_exception(error)
            else:
                future.set_result(result)
        except BaseException:
            # Future state is settled before callbacks run. Even a callback
            # raising SystemExit must not strand another committed receipt or
            # kill the authority's delivery thread.
            with self._condition:
                self._counts["callback_failures"] += 1
