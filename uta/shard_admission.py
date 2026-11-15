"""EXPERIMENTAL bounded admission groups behind the single-host router gate.

One bounded pending queue feeds a finite worker pool. Each shard has at most one
in-flight group; commands retain FIFO order within their shard. Different shards
may commit in either order. Only ShardRouter owns the financial transaction.
"""
from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from decimal import Decimal
import math
from threading import Condition, Thread, current_thread
from time import monotonic, monotonic_ns

from .admission import AdmissionFuture
from .service import ExchangeService, ServiceError
from .sharding import ShardRouter


class _RouterFuture(AdmissionFuture):
    def __init__(self, workers):
        super().__init__()
        self._workers = workers

    def _check_owner_wait(self, timeout):
        if (current_thread() in self._workers and not self.done()
                and (timeout is None or not timeout <= 0)):
            raise RuntimeError("router admission callbacks cannot wait for an unfinished Future from their worker pool")


@dataclass(frozen=True)
class _Command:
    shard: int
    kind: str
    arguments: tuple
    reduce_only: bool
    future: AdmissionFuture


class RouterAdmissionBatcher:
    """Auto-start a local, bounded per-shard group-commit worker pool.

    No HTTP integration, replication, ownership lease, cross-shard transaction,
    or persistent queue is provided. Call close() to drain. A cancelled pending
    Future has no financial effect; a running Future may already have committed.
    A timeout alone never proves rejection. Retry/query the original order ID.
    """
    def __init__(self, router: ShardRouter, *, max_batch_size: int = 32,
                 max_delay_ms: float = 2, queue_capacity: int = 1024,
                 cancel_reserve: int = 16, worker_count: int | None = None):
        if not isinstance(router, ShardRouter):
            raise ValueError("router must be a ShardRouter")
        if type(max_batch_size) is not int or not 1 <= max_batch_size <= 256:
            raise ValueError("max_batch_size must be an integer in 1..256")
        if (isinstance(max_delay_ms, bool) or not isinstance(max_delay_ms, (float, int))
                or not math.isfinite(max_delay_ms) or not 0 <= max_delay_ms <= 1000):
            raise ValueError("max_delay_ms must be finite and in 0..1000")
        if type(queue_capacity) is not int or not 1 <= queue_capacity <= 65536:
            raise ValueError("queue_capacity must be an integer in 1..65536")
        if type(cancel_reserve) is not int or not 0 <= cancel_reserve <= 4096:
            raise ValueError("cancel_reserve must be an integer in 0..4096")
        if worker_count is None:
            worker_count = min(router.layout["shard_count"], 4)
        if type(worker_count) is not int or not 1 <= worker_count <= min(router.layout["shard_count"], 32):
            raise ValueError("worker_count must be an integer in 1..min(shard_count,32)")
        self.router = router
        self.max_batch_size, self.max_delay_ms = max_batch_size, max_delay_ms
        self.queue_capacity, self.cancel_reserve = queue_capacity, cancel_reserve
        self.worker_count = worker_count
        self._condition = Condition()
        self._queue = deque()
        self._active_shards = set()
        self._accepting = True
        self._inflight = self._running = 0
        self._counts = {key: 0 for key in ("committed_batches", "committed_commands", "business_rejected",
            "market_rejected", "cancelled_pending", "technical_failed", "overloaded", "callback_failures")}
        self._threads = [Thread(target=self._run, name=f"uta-router-admission-{index}", daemon=False)
                         for index in range(worker_count)]
        try:
            for thread in self._threads:
                thread.start()
        except BaseException:
            with self._condition:
                self._accepting = False
                self._condition.notify_all()
            for thread in self._threads:
                if thread.ident is not None:
                    thread.join()
            raise

    def _error(self, code, message, status=503):
        future = _RouterFuture(self._threads)
        future._admission_completed_ns = monotonic_ns()
        future.set_exception(ServiceError(code, message, status))
        return future

    def submit_order(self, account_id: str, order_id: str, symbol: str,
                     quantity: Decimal, limit_price: Decimal, *, reduce_only: bool = False) -> AdmissionFuture:
        try:
            ExchangeService._validate_order_command(account_id, order_id, symbol, quantity, limit_price,
                                                    reduce_only=reduce_only)
            shard = self.router.shard_for(account_id)
        except ServiceError as exc:
            return self._error(exc.code, str(exc), exc.status)
        return self._enqueue(shard, "submit", (account_id, order_id, symbol, quantity, limit_price), reduce_only)

    def cancel_order(self, account_id: str, order_id: str) -> AdmissionFuture:
        try:
            ExchangeService._validate_cancel_command(account_id, order_id)
            shard = self.router.shard_for(account_id)
        except ServiceError as exc:
            return self._error(exc.code, str(exc), exc.status)
        return self._enqueue(shard, "cancel", (account_id, order_id), False)

    def _enqueue(self, shard, kind, arguments, reduce_only):
        if current_thread() in self._threads:
            return self._error("admission_reentrant", "worker callbacks cannot submit to their router admission pool")
        with self._condition:
            if not self._accepting:
                return self._error("admission_closed", "router admission pool is closed")
            limit = self.queue_capacity + (self.cancel_reserve if kind == "cancel" else 0)
            if len(self._queue) >= limit:
                self._counts["overloaded"] += 1
                return self._error("admission_overloaded", "router admission queue is full; retry using the original command ID")
            future = _RouterFuture(self._threads)
            future._admission_enqueued_ns = monotonic_ns()
            self._queue.append(_Command(shard, kind, arguments, reduce_only, future))
            self._condition.notify_all()
            return future

    def stats(self):
        with self._condition:
            return {**self._counts, "accepting": self._accepting,
                    "worker_alive": all(thread.is_alive() for thread in self._threads),
                    "workers_alive": sum(thread.is_alive() for thread in self._threads),
                    "worker_count": self.worker_count, "queued": len(self._queue),
                    "inflight": self._inflight, "running": self._running,
                    "active_shards": len(self._active_shards),
                    "queue_capacity": self.queue_capacity, "cancel_reserve": self.cancel_reserve,
                    "total_queue_capacity": self.queue_capacity + self.cancel_reserve,
                    "max_inflight": self.worker_count * self.max_batch_size,
                    "max_outstanding": self.queue_capacity + self.cancel_reserve + self.worker_count * self.max_batch_size}

    def close(self, wait=True):
        if type(wait) is not bool:
            raise ValueError("wait must be a boolean")
        if current_thread() in self._threads:
            raise RuntimeError("worker callbacks cannot close their own router admission pool")
        with self._condition:
            self._accepting = False
            self._condition.notify_all()
        if wait:
            for thread in self._threads:
                thread.join()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback):
        self.close()

    def _take_batch(self):
        with self._condition:
            while True:
                first = next((command for command in self._queue
                              if command.shard not in self._active_shards), None)
                if first is not None:
                    self._active_shards.add(first.shard)
                    break
                if not self._accepting and not self._queue:
                    return None
                self._condition.wait()
            batch = []
            deadline = monotonic() + self.max_delay_ms / 1000
            while len(batch) < self.max_batch_size:
                matching = next((command for command in self._queue if command.shard == first.shard), None)
                if matching is not None:
                    self._queue.remove(matching)
                    batch.append(matching)
                    self._inflight += 1
                    continue
                remaining = deadline - monotonic()
                if not self._accepting or remaining <= 0:
                    break
                self._condition.wait(remaining)
            return first.shard, batch

    def _run(self):
        while True:
            selected = self._take_batch()
            if selected is None:
                return
            shard, batch = selected
            commands = []
            for command in batch:
                if command.future.set_running_or_notify_cancel():
                    command.future._admission_started_ns = monotonic_ns()
                    commands.append(command)
                else:
                    with self._condition:
                        self._counts["cancelled_pending"] += 1
            with self._condition:
                self._running += len(commands)
            try:
                if commands:
                    self._commit_batch(shard, commands)
            finally:
                with self._condition:
                    self._running -= len(commands)
                    self._inflight -= len(batch)
                    self._active_shards.remove(shard)
                    self._condition.notify_all()

    def _commit_batch(self, shard, commands):
        try:
            outcomes = self.router._admit_order_batch(shard,
                [(command.kind, command.arguments, command.reduce_only) for command in commands])
            if len(outcomes) != len(commands):
                raise RuntimeError("router returned an incomplete batch receipt")
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

    def _complete(self, future, *, result=None, error=None):
        future._admission_completed_ns = monotonic_ns()
        try:
            if error is None:
                future.set_result(result)
            else:
                future.set_exception(error)
        except BaseException:
            with self._condition:
                self._counts["callback_failures"] += 1
