"""Authenticated v2 command ingress: durable queue ACKs are not risk acceptance.

The parent holds only an existing producer/query surface. It never initializes
an ExchangeService, runs financial mutations, or falls back to the v1 routes.
Only a separately fenced writer can commit a financial terminal receipt.
"""
from __future__ import annotations

import json
import sqlite3
from typing import Iterable

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
        state = report["state"]
        workers = [{key: worker.get(key) for key in ("shard", "pid", "owner_pid", "lease_active", "generation")}
                   for worker in report["workers"]]
        return {"mode": "process_router", "managed": report["managed"],
                "control": {key: state.get(key) for key in ("halted", "publishing", "epoch", "market_version", "error")},
                "workers": workers, "dispatch_available": bool(report["ready"]),
                "qualification": "process and control observation; not a risk acceptance or trading readiness result"}


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
            or record["state"] == "SUCCEEDED" and (record.get("result") is None or record.get("error") is not None)
            or record["state"] in ("REJECTED", "QUARANTINED") and (record.get("result") is not None or not isinstance(record.get("error"), dict))):
        raise ServiceError("invalid_command_receipt", "durable command receipt is inconsistent", 503)
    return (202 if pending else 200), {**record, "ack": "durably_queued" if pending else "terminal_receipt",
                                      "status_url": status_url}


class _DurableHandler(_Handler):
    """Reuse v1 authentication/framing, with no route delegation to v1."""

    def _route(self, principal, path, query, payload, body):
        if query:
            raise _RequestError(400, "invalid_query", "durable routes do not accept query parameters")
        api = self.server.service
        method = self.command
        if method == "GET" and path in ("/v2/worker-health", "/v2/metrics"):
            self._permit(principal, "risk")
            observed = api.call("diagnostics")
            return 200, observed if path.endswith("worker-health") else {**self.server.counters(), "durable": observed}

        parts = path.split("/")
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


def make_server(producer, host: str = "127.0.0.1", port: int = 8081, *,
                credentials: Iterable[Credential], max_workers: int = 16,
                request_timeout: float = 5.0):
    """Construct an authenticated, bounded loopback server for v2 only.

    This reuses the established HTTP server, credential rotation, constant-time
    authentication, size/framing limits, socket deadlines and graceful draining.
    No server thread starts until the caller invokes ``serve_forever``.
    """
    api = DurableCommandAPI(producer)
    server = _authenticated_server(api, host, port, credentials=credentials,
                                   max_workers=max_workers, request_timeout=request_timeout)
    server.RequestHandlerClass = _DurableHandler
    return server
