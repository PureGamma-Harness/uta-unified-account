"""Private, single-attempt owned initialization; never a verification cache.

Financial authority remains the persistent writer fence. This scope only lets
the spawned initializer run the original complete verifiers in read snapshots
while a separate restricted connection renews that exact live token.
"""
from __future__ import annotations

from copy import copy
import math
import os
from threading import Event, RLock, Thread, get_ident
from time import monotonic

from .storage import StorageError


class StartupError(StorageError):
    def __init__(self, code, message):
        super().__init__(message)
        self.code = code


_ACTIVE_LOCK = RLock()
_ACTIVE = {}  # (device, inode) -> private scope; process-local, never persisted.


def _assert_initialization_actor(database):
    """Called AFTER BEGIN by every financial-role transaction, before DML.

    The ordinary inactive path adds no filesystem check. Both inode and path
    are considered so aliases and replacement paths do not bypass exclusion.
    """
    with _ACTIVE_LOCK:
        if not _ACTIVE:
            return
        matching = next((scope for scope in _ACTIVE.values() if scope.path == database.path), None)
        if matching is None:
            info = os.stat(database.path, follow_symlinks=False)
            matching = _ACTIVE.get((info.st_dev, info.st_ino))
        if matching is not None:
            matching._require(database)


class _OwnedStartup:
    """Internal worker lifecycle, not an application-supplied success receipt.

    No context may attest success without executing the original verifiers.
    Defaults of public service constructors never select this path.
    """
    def __init__(self, database, *, lease_seconds, stop, parent_pid, timeout=60.0):
        if (isinstance(lease_seconds, bool) or not isinstance(lease_seconds, (int, float))
                or not math.isfinite(lease_seconds) or not .001 <= lease_seconds <= 3600):
            raise ValueError("lease seconds must be finite and in .001..3600")
        if (isinstance(timeout, bool) or not isinstance(timeout, (int, float))
                or not math.isfinite(timeout) or not .01 <= timeout <= 300):
            raise ValueError("startup timeout must be finite and in .01..300 seconds")
        if database.writer_token is None:
            raise StartupError("startup_token_required", "owned initialization requires a bound writer")
        self.database, self.token = database, database.writer_token
        self.path, self.owner_thread = database.path, get_ident()
        info = os.stat(self.path, follow_symlinks=False)
        database._validate_private_info(info)
        self.identity = (info.st_dev, info.st_ino)
        self.stop, self.parent_pid = stop, parent_pid
        self.lease_seconds, self.timeout = lease_seconds, float(timeout)
        self._keeper_stop = Event()
        self._lock = RLock()
        self._failure = None
        self._active = self._finished = self._entered = False
        self._keeper = None
        self._exchange = self._credit = None
        self._ledger_verified = False
        self.last_renew_started = None

    def _fail(self, exc):
        with self._lock:
            if self._failure is None:
                self._failure = exc

    def check(self):
        with self._lock:
            failure = self._failure
        if failure is not None:
            raise StartupError("startup_keeper_failed", "owned initialization lost its renewal/verification lifecycle") from failure
        if self.stop.is_set() or os.getppid() != self.parent_pid:
            raise StartupError("startup_cancelled", "initializer was stopped or lost its parent")
        if monotonic() >= self.deadline:
            raise StartupError("startup_deadline", "owned initialization exceeded its finite work budget")

    def _require(self, database):
        if not self._active or get_ident() != self.owner_thread:
            raise StartupError("initialization_in_progress", "another actor cannot write an initializing authority")
        if database.path != self.path or database.writer_token != self.token:
            raise StartupError("startup_token_conflict", "initializer authority, generation or nonce differs")
        self.check()
        self._check_identity(database)

    def _check_identity(self, database):
        info = os.stat(self.path, follow_symlinks=False)
        database._validate_private_info(info)
        if (info.st_dev, info.st_ino) != self.identity:
            raise StartupError("startup_identity_changed", "authority file changed during initialization")

    def _renew(self):
        from .writer_fence import WriterFence
        self.check()
        self._check_identity(self.database)
        started = monotonic()
        # Copy preserves bound-shard identity checks and the token. This role
        # permits lease-control writes only, never financial data or DDL.
        keeper_database = copy(self.database)
        keeper_database.timeout = min(self.database.timeout, self.lease_seconds / 12, .1)
        WriterFence(keeper_database).renew(self.token, self.lease_seconds)
        self._check_identity(self.database)
        with self._lock:
            self.last_renew_started = started

    def _keep(self):
        next_renew = monotonic()
        try:
            while not self._keeper_stop.is_set():
                self.check()
                now = monotonic()
                if now >= next_renew:
                    self._renew()
                    next_renew = self.last_renew_started + self.lease_seconds / 3
                self._keeper_stop.wait(min(.05, max(0, next_renew - monotonic())))
        except BaseException as exc:
            # Even an exception after a real COMMIT is not a known successful
            # renewal. Conservatively poison this attempt; never wash it away.
            self._fail(exc)

    def __enter__(self):
        from .writer_fence import WriterFence
        if self._entered or get_ident() != self.owner_thread:
            raise StartupError("startup_context_invalid", "initialization context is single-use and thread-bound")
        self._entered = True
        self.deadline = monotonic() + self.timeout
        with _ACTIVE_LOCK:
            if self.identity in _ACTIVE or any(scope.path == self.path for scope in _ACTIVE.values()):
                raise StartupError("startup_nested", "an authority already has an initialization scope")
            _ACTIVE[self.identity] = self
            self._active = True
        try:
            self._keeper = Thread(target=self._keep, name="uta-startup-lease", daemon=True)
            self._keeper.start()
            # Drain writers that entered before registration. Acquire itself
            # drained the previous generation; this also handles same-PID actors.
            with self.database.transaction() as connection:
                WriterFence(self.database).assert_writer(connection, self.token)
                # A no-op version write requires the normal transaction-end
                # fence check as well as the entry assertion. No schema value
                # or financial projection is changed.
                connection.execute("UPDATE uta_schema SET version=version")
            return self
        except BaseException:
            self._cleanup()
            raise

    def require_database(self, database):
        with _ACTIVE_LOCK:
            if _ACTIVE.get(self.identity) is not self:
                raise StartupError("startup_context_invalid", "initialization scope is not active")
        self._require(database)

    def verify_ledger(self, exchange):
        from .writer_fence import WriterFence
        self.require_database(exchange.database)
        if self._exchange is not None:
            raise StartupError("startup_context_reused", "ledger verification cannot be reused")
        self._exchange = exchange
        with self.database.read_transaction() as connection:
            WriterFence(self.database).assert_writer(connection, self.token)
            exchange.ledger.verify(connection=connection)
        # The read snapshot's lease row is deliberately NOT checked afterward:
        # it predates concurrent successful renewals. Fresh binding happens later.
        self.check()
        self._ledger_verified = True

    def require_ledger(self, exchange):
        self.require_database(exchange.database)
        if self._exchange is not exchange or not self._ledger_verified:
            raise StartupError("startup_not_verified", "this exact exchange has not completed full replay")

    def verify_credit(self, credit):
        from .writer_fence import WriterFence
        self.require_ledger(credit.exchange)
        if self._credit is not None:
            raise StartupError("startup_context_reused", "credit verification cannot be reused")
        with self.database.read_transaction() as connection:
            WriterFence(self.database).assert_writer(connection, self.token)
            credit._verify(connection)
        self.check()
        self._credit = credit

    def finish(self):
        """Stop keeper, fresh renew/bind and COMMIT before permitting READY."""
        from .writer_fence import WriterFence
        self.require_database(self.database)
        if self._finished or not self._ledger_verified or self._credit is None:
            raise StartupError("startup_not_verified", "complete exchange and credit verification is required")
        self._stop_keeper()
        self.check()
        self._renew()
        with self.database.transaction() as connection:
            self._require(self.database)
            WriterFence(self.database).assert_writer(connection, self.token)
            connection.execute("UPDATE uta_schema SET version=version")
        self.check()
        self._finished = True

    def _stop_keeper(self):
        self._keeper_stop.set()
        if self._keeper is not None and self._keeper.ident is not None:
            self._keeper.join(timeout=1)
            if self._keeper.is_alive():
                raise StartupError("startup_keeper_stuck", "startup renewal did not drain")

    def _cleanup(self):
        try:
            self._stop_keeper()
        finally:
            with _ACTIVE_LOCK:
                if _ACTIVE.get(self.identity) is self:
                    del _ACTIVE[self.identity]
                self._active = False

    def __exit__(self, exc_type, exc, traceback):
        self._cleanup()
        if exc_type is None and not self._finished:
            raise StartupError("startup_not_finished", "owned initialization did not complete its final binding")
