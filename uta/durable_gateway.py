"""Authenticated v2 command ingress: durable queue ACKs are not risk acceptance.

The parent holds only an existing producer/query surface. It never initializes
an ExchangeService, runs financial mutations, or falls back to the v1 routes.
Only a separately fenced writer can commit a financial terminal receipt.
"""
from __future__ import annotations

import json
import hashlib
import io
import os
import re
import secrets
import sqlite3
import ssl
from typing import Iterable
from urllib.parse import parse_qsl

from .durable_commands import QueueStore
from .gateway import (Credential, _Handler, _RequestError, _decimal, _fields,
                      _identifier, make_server as _authenticated_server)
from .market import MarketSnapshot
from .service import ServiceError
from .storage import StorageError
from .writer_fence import WriterFence


_TERMINAL = frozenset({"SUCCEEDED", "REJECTED", "QUARANTINED"})
_CONTROL = frozenset({"PUBLISH_MARKET", "SET_HALT"})


def _unavailable():
    raise _RequestError(501, "unsupported_durable_operation",
                        "this operation has no supported durable command protocol")


class _InboxProducer:
    def __init__(self, queue: QueueStore):
        if queue.database.writer_token is not None:
            raise ValueError("HTTP ingress requires an unbound producer, never a writer token")
        self.queue = queue
        self.fence = WriterFence(queue.database)
        state = self.fence.status()
        if not state["managed"]:
            raise ValueError("durable HTTP requires an existing managed authority")

    def submit_order(self, *args, **kwargs):
        return self.queue.enqueue_submit(*args, **kwargs)

    def cancel_order(self, *args):
        return self.queue.enqueue_cancel(*args)

    def repay(self, *args):
        operation = getattr(self.queue, "enqueue_repay", None)
        if not callable(operation):
            _unavailable()
        return operation(*args)

    def status(self, command_id, account_id):
        return self.queue.status(command_id, account_id=account_id)

    def read_view(self, account_id, resource, **options):
        from .durable_views import ManagedAccountViews
        return ManagedAccountViews(self.queue.database).read(account_id, resource, **options)

    def publish_market(self, command_id, snapshot):
        return self.queue.enqueue_market(command_id, snapshot)

    def set_halt(self, command_id, enabled):
        return self.queue.enqueue_halt(command_id, enabled)

    def control_status(self, command_id):
        record = self.queue.status(command_id)
        return record if record is not None and record["kind"] in _CONTROL else None

    def diagnostics(self):
        lease = self.fence.status()
        with self.queue.database.read_transaction() as connection:
            pending = connection.execute("SELECT COUNT(*) FROM uta_command_inbox WHERE state='PENDING'").fetchone()[0]
        return {"mode": "single_authority", "managed": lease["managed"],
                "writer": {"lease_active": lease["active"], "generation": lease.get("generation")},
                "pending_commands": pending,
                "capacity": {"queue": self.queue.queue_capacity, "cancel_reserve": self.queue.cancel_reserve,
                             "control": self.queue.market_capacity},
                "qualification": "lease_observation_only; not a risk acceptance or trading readiness result"}


class _RouterProducer:
    def __init__(self, router):
        self.router = router

    def submit_order(self, *args, **kwargs):
        return self.router.submit_order(*args, **kwargs)

    def cancel_order(self, *args):
        return self.router.cancel_order(*args)

    def repay(self, *args):
        operation = getattr(self.router, "repay", None)
        if not callable(operation):
            _unavailable()
        return operation(*args)

    def status(self, command_id, account_id):
        return self.router.status(command_id, account_id=account_id)

    def read_view(self, account_id, resource, **options):
        from .durable_views import ManagedAccountViews
        shard = self.router.shard_for(account_id)
        layout_hash = hashlib.sha256(self.router._control._descriptor.encode()).hexdigest()
        return ManagedAccountViews(self.router._database(shard), shard=shard,
                                   layout_hash=layout_hash).read(account_id, resource, **options)

    def publish_market(self, *args):
        # The parent's control fanout currently has no stable client command-ID
        # contract. Never substitute that synchronous method for queued ingress.
        _unavailable()

    def set_halt(self, *args):
        _unavailable()

    def control_status(self, command_id):
        _unavailable()

    def diagnostics(self):
        report = self.router.diagnostics()
        if not isinstance(report, dict) or not isinstance(report.get("workers"), list) or any(not isinstance(worker, dict) for worker in report["workers"]):
            raise ServiceError("diagnostic_unavailable", "router diagnostic observation is malformed", 503)
        state = report.get("state")
        state_observed = (isinstance(state, dict) and report.get("state_observed", True) is True
                          and type(state.get("halted")) is bool and type(state.get("publishing")) is bool
                          and type(state.get("epoch")) is int and state["epoch"] >= 0
                          and (state.get("market_version") is None or
                               type(state.get("market_version")) is int and state["market_version"] >= 0))
        def code(value):
            return value if isinstance(value, str) and 1 <= len(value) <= 80 and value.isascii() and value.replace("_", "").isalnum() else "diagnostic_unavailable"
        control = None
        if state_observed:
            control = {key: state.get(key) for key in ("halted", "publishing", "epoch", "market_version")}
            control["error"] = None if state.get("error") is None else code(state["error"])
        workers = []
        for worker in report["workers"]:
            observed = {key: worker.get(key) for key in ("shard", "pid", "owner_pid", "lease_active", "generation")}
            for key in ("alive", "owner_ready", "locally_active", "market_ready", "funding_registry_ready"):
                if key in worker:
                    observed[key] = worker[key] is True
            for key in ("market_version", "market_digest", "market_observed_at"):
                if key in worker:
                    observed[key] = worker[key]
            if "reason" in worker:
                observed["reason"] = code(worker["reason"])
            workers.append(observed)
        dispatch_available = (state_observed and not state["halted"] and not state["publishing"]
                              and report.get("ready") is True)
        financial_ready = dispatch_available and report.get("financial_ready") is True
        return {"mode": "process_router", "managed": report.get("managed") is True,
                "state_observed": state_observed, "control_observed": state_observed, "control": control, "workers": workers,
                "workers_alive": report.get("workers_alive") is True,
                "dispatch_available": dispatch_available, "ready": financial_ready, "financial_ready": financial_ready,
                "readiness_source": "persistent_market_and_owner" if "financial_ready" in report else "legacy_process_control_only",
                "reason": code(report.get("reason")),
                "qualification": "bounded process/control/market observation; not an individual account risk acceptance or execution permission"}


class DurableCommandAPI:
    """Existing-inbox adapter; construction never initializes financial state.

    ``producer`` is either QueueStore(initialize=False) on an already managed
    authority, or an existing DurableProcessRouter. Bootstrap and process
    supervision belong to the operator, not to HTTP request handling.
    """

    def __init__(self, producer):
        if isinstance(producer, QueueStore):
            self._producer = _InboxProducer(producer)
        else:
            from .durable_process import DurableProcessRouter
            if not isinstance(producer, DurableProcessRouter):
                raise ValueError("producer must be an existing QueueStore or DurableProcessRouter")
            self._producer = _RouterProducer(producer)

    def call(self, operation: str, *args, **kwargs):
        try:
            return getattr(self._producer, operation)(*args, **kwargs)
        except (StorageError, sqlite3.Error) as exc:
            # A COMMIT may have completed before its caller saw an exception.
            # Never invent a negative result or a replacement command ID.
            writes = {"submit_order", "cancel_order", "repay", "publish_market", "set_halt"}
            if operation in writes:
                raise ServiceError("command_outcome_unknown",
                    "durable enqueue outcome is unknown; query or retry the original account and command ID", 503) from exc
            raise ServiceError("command_query_unavailable",
                               "durable command query is unavailable; retain the original command ID", 503) from exc


def _receipt(record, *, status_url: str):
    if not isinstance(record, dict) or record.get("state") not in _TERMINAL | {"PENDING"}:
        raise ServiceError("invalid_command_receipt", "durable command receipt is malformed", 503)
    pending = record["state"] == "PENDING"
    if (pending and (record.get("result") is not None or record.get("error") is not None)
            or record["state"] == "SUCCEEDED" and (not isinstance(record.get("result"), dict) or record.get("error") is not None)
            or record["state"] in ("REJECTED", "QUARANTINED") and (record.get("result") is not None or not isinstance(record.get("error"), dict))):
        raise ServiceError("invalid_command_receipt", "durable command receipt is inconsistent", 503)
    return (202 if pending else 200), {**record, "ack": "durably_queued" if pending else "terminal_receipt",
                                      "status_url": status_url}


def _view_options(query, *, pageable):
    try:
        pairs = parse_qsl(query, keep_blank_values=True, strict_parsing=True, max_num_fields=5)
        fields = dict(pairs)
        allowed = {"at_version", "stream_id"} | ({"after", "until", "limit"} if pageable else set())
        if len(fields) != len(pairs) or set(fields) - allowed:
            raise ValueError("unsupported or duplicate query")
        for name, value in fields.items():
            if name == "stream_id":
                if not re.fullmatch(r"account-stream:[0-9a-f]{64}", value):
                    raise ValueError("invalid stream ID")
            else:
                if not re.fullmatch(r"[0-9]{1,19}", value, re.ASCII) or int(value) > 2**63 - 1:
                    raise ValueError("invalid integer")
                fields[name] = int(value)
        return fields
    except ValueError:
        raise _RequestError(400, "invalid_query", "invalid managed-view cursor or query fields") from None


class _DurableHandler(_Handler):
    """Reuse v1 authentication/framing, with no route delegation to v1."""

    def _route(self, principal, path, query, payload, body):
        parts = path.split("/")
        if self.command == "GET" and len(parts) >= 4 and parts[:3] == ["", "v2", "accounts"]:
            resource = "account" if len(parts) == 4 else parts[4]
            identity = None
            recognized = (len(parts) == 4 or len(parts) == 5 and resource in {"orders", "positions", "ledger", "events", "liquidation"}
                          or len(parts) == 6 and resource in {"orders", "decisions"})
            if recognized:
                account_id = _identifier(parts[3])
                self._account(principal, account_id)
                self._permit(principal, "reader", "trader", "risk")
                if len(parts) == 6:
                    identity = _identifier(parts[5])
                options = _view_options(query, pageable=resource in {"orders", "positions", "ledger", "events"} and identity is None)
                return 200, self.server.service.call("read_view", account_id, resource,
                                                      identity=identity, **options)
        if query:
            raise _RequestError(400, "invalid_query", "durable routes do not accept query parameters")
        api = self.server.service
        method = self.command
        if method == "GET" and path in ("/v2/worker-health", "/v2/metrics"):
            self._permit(principal, "risk")
            observed = api.call("diagnostics")
            return 200, observed if path.endswith("worker-health") else {**self.server.counters(), "durable": observed}

        if len(parts) >= 4 and parts[:3] == ["", "v2", "accounts"]:
            account_id = _identifier(parts[3])
            self._account(principal, account_id)
            if method == "GET" and len(parts) == 6 and parts[4] == "commands":
                self._permit(principal, "reader", "trader", "funding", "risk")
                command_id = _identifier(parts[5])
                record = api.call("status", command_id, account_id)
                if record is None or principal.role == "funding" and record["kind"] != "REPAY":
                    raise _RequestError(404, "command_not_found", "command not found in the permitted account scope")
                return _receipt(record, status_url=path)
            if method == "POST" and len(parts) == 5 and parts[4] == "orders":
                self._permit(principal, "trader")
                data = _fields(payload, {"command_id", "order_id", "symbol", "quantity", "limit_price"}, {"reduce_only"})
                command_id = _identifier(data["command_id"])
                reduce_only = data.get("reduce_only", False)
                if type(reduce_only) is not bool:
                    raise _RequestError(400, "invalid_fields", "reduce_only must be a boolean")
                record = api.call("submit_order", account_id, command_id, _identifier(data["order_id"]),
                    _identifier(data["symbol"], market=True), _decimal(data["quantity"]),
                    _decimal(data["limit_price"]), reduce_only=reduce_only)
                return _receipt(record, status_url=f"/v2/accounts/{account_id}/commands/{command_id}")
            if method == "POST" and len(parts) == 7 and parts[4] == "orders" and parts[6] == "cancel":
                self._permit(principal, "trader")
                data = _fields(payload, {"command_id"})
                command_id = _identifier(data["command_id"])
                record = api.call("cancel_order", account_id, command_id, _identifier(parts[5]))
                return _receipt(record, status_url=f"/v2/accounts/{account_id}/commands/{command_id}")
            if method == "POST" and len(parts) == 5 and parts[4] == "repay":
                self._permit(principal, "funding")
                data = _fields(payload, {"command_id", "asset", "amount"})
                command_id = _identifier(data["command_id"])
                record = api.call("repay", account_id, command_id,
                                  _identifier(data["asset"], market=True), _decimal(data["amount"]))
                return _receipt(record, status_url=f"/v2/accounts/{account_id}/commands/{command_id}")
            if len(parts) >= 5:
                _unavailable()

        if parts[:3] == ["", "v2", "control"]:
            self._permit(principal, "risk")
            if method == "GET" and len(parts) == 5 and parts[3] == "commands":
                record = api.call("control_status", _identifier(parts[4]))
                if record is None:
                    raise _RequestError(404, "command_not_found", "control command not found")
                return _receipt(record, status_url=path)
            if method == "POST" and len(parts) == 4 and parts[3] in ("market", "halt"):
                field = "snapshot" if parts[3] == "market" else "enabled"
                data = _fields(payload, {"command_id", field})
                command_id = _identifier(data["command_id"])
                if field == "snapshot":
                    if not isinstance(data[field], dict):
                        raise _RequestError(400, "invalid_market", "snapshot must be a market JSON object")
                    try:
                        snapshot = MarketSnapshot.from_json(json.dumps(data[field], allow_nan=False))
                    except (ValueError, TypeError, KeyError, RecursionError):
                        raise _RequestError(400, "invalid_market", "invalid market snapshot") from None
                    record = api.call("publish_market", command_id, snapshot)
                else:
                    if type(data[field]) is not bool:
                        raise _RequestError(400, "invalid_fields", "enabled must be a boolean")
                    record = api.call("set_halt", command_id, data[field])
                return _receipt(record, status_url=f"/v2/control/commands/{command_id}")
            _unavailable()
        raise _RequestError(404, "not_found", "durable route not found")


def producer_binding(producer):
    """Local deployment binding, independent of policy and lease generations.

    Fresh auth initialization additionally generates a persistent random audience.
    File identities make copied/moved local authorities fail closed at startup;
    this is not a cross-host anti-rollback or replicated identity protocol.
    """
    api = DurableCommandAPI(producer)
    backend = api._producer
    databases = ([backend.queue.database] if isinstance(backend, _InboxProducer) else
                 [backend.router._control.control] + [backend.router._database(i)
                    for i in range(backend.router.layout["shard_count"])])
    records = []
    for database in databases:
        info = os.stat(database.path, follow_symlinks=False)
        lease = WriterFence(database).status()
        records.append({"path": database.path, "device": info.st_dev, "inode": info.st_ino,
                        "authority_id": lease.get("authority_id")})
    return hashlib.sha256(json.dumps(records, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


class _SignedDurableHandler(_DurableHandler):
    def send_header(self, keyword, value):
        if keyword.lower() == "www-authenticate":
            value = 'UTA-HMAC-SHA256 realm="uta-v2"'
        return super().send_header(keyword, value)

    def _principal(self):
        from .request_signing import RequestAuthenticator, SigningError
        authenticator = getattr(self.server, "request_authenticator", None)
        if not isinstance(authenticator, RequestAuthenticator):
            raise _RequestError(503, "signing_store_unavailable", "HMAC authentication is unavailable; no fallback")
        if self.headers.get("Authorization", "").lower() != "uta-hmac-sha256":
            raise _RequestError(401, "signature_required", "HMAC request authentication is required")
        # BaseHTTPRequestHandler can normalize a leading // before routing.
        # Sign the exact original target and reject such ambiguous normalization.
        try:
            line = self.raw_requestline.rstrip(b"\r\n").split(b" ")
            if len(line) != 3 or line[0].decode("ascii") != self.command:
                raise ValueError("invalid request line")
            target = line[1].decode("ascii")
            if target != self.path:
                raise ValueError("normalized request target")
        except (ValueError, UnicodeError):
            raise _RequestError(400, "invalid_path", "HMAC requires an unmodified ASCII request target") from None
        length = self._framing(self.command in ("POST", "PUT"))
        body = self.rfile.read(length)
        if len(body) != length:
            raise _RequestError(400, "truncated_body", "incomplete signed request body")
        try:
            principal = authenticator.authenticate(self.headers, method=self.command, request_target=target, body=body)
        except SigningError as exc:
            raise _RequestError(exc.status, exc.code, str(exc)) from None
        self._signed_body = body
        return principal

    def _payload(self, length):
        # Authentication already consumed the exact bytes. Reuse the existing
        # content-type and strict JSON parser only after nonce COMMIT succeeds.
        original = self.rfile
        self.rfile = io.BytesIO(self._signed_body)
        try:
            return super()._payload(length)
        finally:
            self.rfile = original


def make_server(producer, host: str = "127.0.0.1", port: int = 8081, *,
                credentials: Iterable[Credential] = (), max_workers: int = 16,
                request_timeout: float = 5.0, auth_profile="bearer_dev", authenticator=None,
                require_tls: bool = True, tls_context: ssl.SSLContext | None = None):
    """Construct an authenticated, bounded loopback server for v2 only.

    This reuses the established HTTP server, credential rotation, constant-time
    authentication, size/framing limits, socket deadlines and graceful draining.
    No server thread starts until the caller invokes ``serve_forever``.
    """
    if auth_profile not in ("bearer_dev", "hmac") or type(require_tls) is not bool:
        raise ValueError("auth_profile must be bearer_dev or hmac, with a boolean TLS requirement")
    credentials = tuple(credentials)
    if tls_context is not None and (not isinstance(tls_context, ssl.SSLContext) or tls_context.minimum_version < ssl.TLSVersion.TLSv1_2):
        raise ValueError("TLS context must require TLS 1.2 or newer")
    if auth_profile == "hmac":
        from .request_signing import RequestAuthenticator
        if credentials or not isinstance(authenticator, RequestAuthenticator):
            raise ValueError("HMAC profile requires its authenticator and no Bearer credentials")
        if require_tls and tls_context is None:
            raise ValueError("HMAC production profile requires TLS; explicit require_tls=False is development only")
        if authenticator.store.producer_binding != producer_binding(producer):
            raise ValueError("authentication authority belongs to another producer deployment")
        # Only satisfy the legacy server's credential-set shape during creation.
        # This random, unused reader credential is removed before return; no
        # request thread starts, and signed requests never call Bearer auth.
        credentials = (Credential(secrets.token_urlsafe(32), "reader", "signed-only"),)
    elif authenticator is not None:
        raise ValueError("an authenticator cannot silently use the Bearer development profile")
    api = DurableCommandAPI(producer)
    server = _authenticated_server(api, host, port, credentials=credentials,
                                   max_workers=max_workers, request_timeout=request_timeout)
    try:
        server.auth_profile = auth_profile
        if auth_profile == "hmac":
            with server._credential_lock:
                server._credentials = ()
            server.request_authenticator = authenticator
            server.RequestHandlerClass = _SignedDurableHandler
        else:
            server.RequestHandlerClass = _DurableHandler
        if tls_context is not None:
            # Do not handshake on the accept thread: a silent TCP client would
            # otherwise block the whole listener before worker limits/deadlines.
            # The first worker read handshakes after _Handler.setup sets timeout.
            server.socket = tls_context.wrap_socket(server.socket, server_side=True, do_handshake_on_connect=False)
        return server
    except BaseException:
        server.server_close()
        raise
