"""Authenticated loopback gateway for the durable exchange service.

This HTTP server is an internal gateway. Put it behind a TLS-terminating proxy
with connection/rate limits before allowing remote clients. Financial state and
prices always come from the service, never from a trader's risk calculation.
"""
from __future__ import annotations

from concurrent.futures import CancelledError, wait
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation
from hmac import compare_digest
from http.server import BaseHTTPRequestHandler, HTTPServer
import ipaddress
import json
import os
import re
import socket
from socketserver import ThreadingMixIn
import stat
from threading import BoundedSemaphore, Lock
from typing import Any, Iterable
from urllib.parse import parse_qsl, urlsplit


MAX_BODY = 64 * 1024
_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}\Z", re.ASCII)
_MARKET_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:/-]{0,127}\Z", re.ASCII)
_TOKEN = re.compile(r"[A-Za-z0-9._~+/-]{32,256}={0,2}\Z", re.ASCII)
_NUMBER = re.compile(r"[+-]?(?:0|[1-9][0-9]*)(?:\.[0-9]+)?(?:[eE][+-]?[0-9]+)?\Z", re.ASCII)


@dataclass(frozen=True)
class Credential:
    """One opaque token with a role and optional account scope.

    Generate tokens with ``secrets.token_urlsafe(32)`` or a stronger source.
    Tokens are intentionally omitted from repr/log output.
    """

    token: str = field(repr=False)
    role: str
    account_id: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.token, str) or not _TOKEN.fullmatch(self.token):
            raise ValueError("bearer tokens require 32..258 ASCII token characters")
        if self.role not in ("admin", "reader", "funding", "risk", "trader"):
            raise ValueError("credential role must be admin, reader, funding, risk or trader")
        if self.role in ("reader", "funding", "trader"):
            if not isinstance(self.account_id, str) or not _ID.fullmatch(self.account_id):
                raise ValueError("account-scoped credentials require a valid account_id")
        elif self.account_id is not None:
            raise ValueError("admin and risk credentials must not have an account_id")


def _unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate JSON object key")
        result[key] = value
    return result


def _nonfinite(_: str) -> None:
    raise ValueError("nonstandard JSON number")


def _decode_json(body: bytes) -> Any:
    return json.loads(body.decode("utf-8"), object_pairs_hook=_unique_object,
                      parse_constant=_nonfinite)


def _credentials(values: Iterable[Credential]) -> tuple[Credential, ...]:
    result = tuple(values)
    if not result or len(result) > 1024 or any(not isinstance(c, Credential) for c in result):
        raise ValueError("configure 1..1024 Credential objects")
    if len({c.token for c in result}) != len(result):
        raise ValueError("duplicate bearer tokens are not allowed")
    return result


def load_credentials(path: str | os.PathLike[str]) -> tuple[Credential, ...]:
    """Load a private, service-user-owned regular JSON file without symlinks.

    Format: ``[{"token": "...", "role": "admin"}, {"token": "...",
    "role": "trader", "account_id": "alice"}]``. Group/other permissions,
    duplicate keys/tokens and unknown fields are rejected at startup.
    """
    descriptor = os.open(path, os.O_RDONLY | os.O_CLOEXEC | os.O_NOFOLLOW | os.O_NONBLOCK)
    with os.fdopen(descriptor, "rb") as source:
        info = os.fstat(source.fileno())
        if (not stat.S_ISREG(info.st_mode) or info.st_uid != os.geteuid()
                or stat.S_IMODE(info.st_mode) & 0o077):
            raise ValueError("credentials must be a private regular file owned by the service user")
        body = source.read(MAX_BODY + 1)
    if len(body) > MAX_BODY:
        raise ValueError("credentials file exceeds 64 KiB")
    try:
        data = _decode_json(body)
        if not isinstance(data, list):
            raise ValueError("credentials must be an array")
        result = []
        for item in data:
            if (not isinstance(item, dict) or not {"token", "role"} <= item.keys()
                    or item.keys() - {"token", "role", "account_id"}):
                raise ValueError("invalid credential fields")
            result.append(Credential(**item))
        return _credentials(result)
    except (UnicodeError, ValueError, TypeError, RecursionError):
        # Do not include credential contents in a startup exception.
        raise ValueError("invalid credentials configuration") from None


class _RequestError(Exception):
    def __init__(self, status: int, code: str, message: str):
        self.status, self.code, self.message = status, code, message


def _fields(data: Any, required: set[str], optional: set[str] | None = None) -> dict[str, Any]:
    if (not isinstance(data, dict) or not required <= data.keys()
            or data.keys() - required - (optional or set())):
        raise _RequestError(400, "invalid_fields", "missing or unsupported request fields")
    return data


def _identifier(value: Any, *, market: bool = False) -> str:
    pattern = _MARKET_ID if market else _ID
    if not isinstance(value, str) or not pattern.fullmatch(value):
        raise _RequestError(400, "invalid_identifier", "invalid identifier")
    return value


def _decimal(value: Any) -> Decimal:
    if not isinstance(value, str) or len(value) > 80 or not _NUMBER.fullmatch(value):
        raise _RequestError(400, "invalid_decimal", "financial values must be decimal strings")
    try:
        result = Decimal(value)
    except InvalidOperation:
        raise _RequestError(400, "invalid_decimal", "invalid decimal string") from None
    if (not result.is_finite() or abs(result.as_tuple().exponent) > 100
            or (result and abs(result.adjusted()) > 100)):
        raise _RequestError(400, "invalid_decimal", "decimal exceeds supported range")
    return result


def _event_cursor(query: str) -> tuple[int, int]:
    # CPython 3.10 strict parse_qsl rejects an empty query, while newer
    # versions return no pairs. No query means the documented defaults; keep
    # strict parsing for every nonempty query instead of relaxing validation.
    if query == "":
        return 0, 100
    try:
        pairs = parse_qsl(query, keep_blank_values=True, strict_parsing=True,
                          max_num_fields=2)
        options = dict(pairs)
        if len(options) != len(pairs) or options.keys() - {"after", "limit"}:
            raise ValueError("unsupported query")
        if any(not re.fullmatch(r"[0-9]{1,19}", v, flags=re.ASCII) for v in options.values()):
            raise ValueError("invalid integer")
        after, limit = int(options.get("after", "0")), int(options.get("limit", "100"))
        if not 0 <= after <= 2**63 - 1 or not 1 <= limit <= 1000:
            raise ValueError("invalid cursor")
    except ValueError:
        raise _RequestError(400, "invalid_query", "invalid event cursor or limit") from None
    return after, limit


class _GatewayServer(ThreadingMixIn, HTTPServer):
    # server_close() drains admitted requests during orderly shutdown. Socket
    # deadlines and the service's database busy timeout bound ordinary waits.
    daemon_threads = False
    block_on_close = True
    request_queue_size = 64
    allow_reuse_address = True

    def __init__(self, address, service, credentials, *, max_workers, request_timeout,
                 admission_timeout):
        self.service = service
        self._credential_lock = Lock()
        self._credentials = credentials
        self.request_timeout = request_timeout
        self.admission_timeout = admission_timeout
        self._slots = BoundedSemaphore(max_workers)
        self._counter_lock = Lock()
        self._counts: dict[str, int] = {"requests": 0, "rejected_connections": 0,
                                       "client_errors": 0, "server_errors": 0}
        super().__init__(address, _Handler)

    @property
    def credentials(self) -> tuple[Credential, ...]:
        with self._credential_lock:
            return self._credentials

    def replace_credentials(self, credentials: Iterable[Credential]) -> None:
        """Atomically rotate a validated credential set, preserving it on error.

        A configuration may contain overlapping old/new tokens for one account.
        Already authenticated requests finish with their captured principal;
        subsequent authentication uses the replacement set. No HTTP endpoint
        exposes this operation or the credential values.
        """
        replacement = _credentials(credentials)
        with self._credential_lock:
            self._credentials = replacement

    def _count(self, key: str) -> None:
        with self._counter_lock:
            self._counts[key] += 1

    def counters(self) -> dict[str, int]:
        with self._counter_lock:
            return dict(self._counts)

    def process_request(self, request, client_address):
        if not self._slots.acquire(blocking=False):
            self._count("rejected_connections")
            try:
                request.settimeout(self.request_timeout)
                request.sendall(b"HTTP/1.1 503 Service Unavailable\r\n"
                                b"Connection: close\r\nContent-Length: 0\r\n\r\n")
            except OSError:
                pass
            finally:
                self.shutdown_request(request)
            return
        try:
            super().process_request(request, client_address)
        except BaseException:
            self._slots.release()
            raise

    def process_request_thread(self, request, client_address):
        try:
            super().process_request_thread(request, client_address)
        finally:
            self._slots.release()

    def handle_error(self, request, client_address):
        # An unexpected handler error must not print headers, tokens or bodies.
        self._count("server_errors")


class _Handler(BaseHTTPRequestHandler):
    server: _GatewayServer
    protocol_version = "HTTP/1.1"
    server_version = "UTA"

    def setup(self):
        self.request.settimeout(self.server.request_timeout)
        super().setup()

    def version_string(self):
        return self.server_version

    def log_message(self, format, *args):
        pass

    def _reply(self, status: int, data: Any) -> None:
        body = json.dumps(data, ensure_ascii=False, allow_nan=False,
                          separators=(",", ":")).encode("utf-8")
        # One request per connection removes ambiguous trailing bodies and HTTP
        # pipelining from this small gateway's protocol surface.
        self.close_connection = True
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Connection", "close")
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        if status == 401:
            self.send_header("WWW-Authenticate", 'Bearer realm="uta"')
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(body)

    def send_error(self, code, message=None, explain=None):
        # BaseHTTPRequestHandler otherwise returns HTML containing the request
        # method or invalid header text. Never echo raw request material.
        self._reply(code, {"error": {"code": "invalid_http", "message": "invalid HTTP request"}})

    def handle_expect_100(self):
        self._reply(417, {"error": {"code": "unsupported_expectation",
                                   "message": "Expect is not supported"}})
        return False

    def _framing(self, body_required: bool) -> int:
        if sum(len(name) + len(value) + 4 for name, value in self.headers.items()) > 16 * 1024:
            raise _RequestError(431, "headers_too_large", "request headers exceed 16 KiB")
        if (self.headers.get_all("Transfer-Encoding") is not None
                or self.headers.get_all("Expect") is not None):
            raise _RequestError(400, "invalid_framing", "unsupported transfer framing")
        for name in ("Host", "Content-Type", "Authorization"):
            if len(self.headers.get_all(name, [])) > 1:
                raise _RequestError(400, "duplicate_header", "duplicate singleton HTTP header")
        if self.request_version == "HTTP/1.1" and not self.headers.get("Host"):
            raise _RequestError(400, "invalid_host", "HTTP/1.1 requires a Host header")
        lengths = self.headers.get_all("Content-Length", [])
        if len(lengths) > 1:
            raise _RequestError(400, "invalid_framing", "duplicate Content-Length")
        if not lengths:
            if body_required:
                raise _RequestError(411, "length_required", "Content-Length is required")
            return 0
        if not re.fullmatch(r"[0-9]{1,10}", lengths[0], flags=re.ASCII):
            raise _RequestError(400, "invalid_framing", "invalid Content-Length")
        length = int(lengths[0])
        if length > MAX_BODY:
            raise _RequestError(413, "body_too_large", "request body exceeds 64 KiB")
        if not body_required and length:
            raise _RequestError(400, "unexpected_body", "this method does not accept a body")
        return length

    def _principal(self) -> Credential:
        authorization = self.headers.get("Authorization", "")
        supplied = ""
        scheme, separator, candidate = authorization.partition(" ")
        if separator and scheme.lower() == "bearer":
            supplied = candidate
        if not _TOKEN.fullmatch(supplied):
            raise _RequestError(401, "unauthorized", "valid bearer authentication is required")
        selected = None
        # Check every configured credential, without short-circuiting on match.
        for credential in self.server.credentials:
            if compare_digest(supplied, credential.token):
                selected = credential
        if selected is None:
            raise _RequestError(401, "unauthorized", "valid bearer authentication is required")
        return selected

    @staticmethod
    def _permit(principal: Credential, *roles: str) -> None:
        if principal.role != "admin" and principal.role not in roles:
            raise _RequestError(403, "forbidden", "credential role does not permit this operation")

    @staticmethod
    def _account(principal: Credential, account_id: str) -> None:
        if principal.role not in ("admin", "risk") and principal.account_id != account_id:
            raise _RequestError(403, "forbidden", "account access is forbidden")

    def _payload(self, length: int) -> tuple[Any, bytes]:
        if (self.headers.get_content_type() != "application/json"
                or self.headers.get_content_charset("utf-8").lower() != "utf-8"):
            raise _RequestError(415, "unsupported_media_type", "application/json with UTF-8 is required")
        body = self.rfile.read(length)
        if len(body) != length:
            raise _RequestError(400, "truncated_body", "incomplete request body")
        try:
            return _decode_json(body), body
        except (UnicodeError, ValueError, RecursionError):
            raise _RequestError(400, "invalid_json", "invalid JSON document") from None

    def _component(self, name: str):
        component = getattr(self.server.service, name, None)
        if component is None:
            raise _RequestError(501, "feature_unavailable", "requested service component is not configured")
        return component

    def _order_command(self, operation: str, *arguments, **keywords):
        """Keep each HTTP command's result behind the grouped COMMIT boundary.

        Cancelling a waiting Future only removes a command which has not begun.
        Once running, a timeout cannot undo or reject the financial operation.
        The original command ID remains the recovery key in that case.
        """
        admission = getattr(self.server.service, "admission", None)
        if admission is None:
            return getattr(self.server.service, operation)(*arguments, **keywords)
        future = getattr(admission, operation)(*arguments, **keywords)
        completed, _ = wait((future,), timeout=self.server.admission_timeout)
        if future in completed:
            try:
                return future.result()
            except CancelledError:
                raise _RequestError(503, "admission_queue_timeout",
                                    "command was cancelled before execution; retry with its original ID") from None
        if future.cancel():
            raise _RequestError(503, "admission_queue_timeout",
                                "command did not begin before the deadline; retry with its original ID")
        raise _RequestError(503, "command_result_unknown",
                            "command may commit; query or retry its original ID and content")

    def _route(self, principal: Credential, path: str, query: str, payload: Any, body: bytes):
        service = self.server.service
        method = self.command
        parts = path.split("/")
        account_events = (len(parts) == 5 and parts[:3] == ["", "v1", "accounts"]
                          and parts[4] == "events")
        if query and not (method == "GET" and (path in ("/v1/events", "/v1/trades") or account_events)):
            raise _RequestError(400, "invalid_query", "query parameters are not supported for this route")
        if method == "GET" and path == "/readyz":
            try:
                state = service.readiness()
                if not isinstance(state, dict) or type(state.get("ready")) is not bool:
                    raise ValueError("invalid readiness response")
            except Exception:
                return 503, {"ready": False, "reason": "service_unavailable"}
            worker = getattr(service, "worker", None)
            if worker is not None:
                report = getattr(worker, "last_report", None)
                reason = None
                if not isinstance(report, dict) or report.get("reason") == "worker_failure":
                    reason = "worker_failure"
                elif report.get("state") == "not_started" or report.get("reason") == "not_started":
                    reason = "worker_not_started"
                if reason:
                    state = {**state, "ready": False, "worker_reason": reason}
                    if state.get("reason") in (None, "ready", "ok"):
                        state["reason"] = reason
            admission = getattr(service, "admission", None)
            if admission is not None:
                try:
                    health = admission.stats()
                    healthy = health.get("worker_alive") is True and health.get("accepting") is True
                except Exception:
                    healthy = False
                if not healthy:
                    state = {**state, "ready": False, "admission_reason": "admission_unavailable"}
                    if state.get("reason") in (None, "ready", "ok"):
                        state["reason"] = "admission_unavailable"
            return (200 if state["ready"] else 503), state
        if method == "GET" and path == "/metrics":
            self._permit(principal, "risk")
            result: dict[str, Any] = self.server.counters()
            worker = getattr(service, "worker", None)
            if worker is not None:
                report = getattr(worker, "last_report", None)
                result["worker"] = dict(report) if isinstance(report, dict) else {"state": "blocked", "reason": "worker_failure"}
            admission = getattr(service, "admission", None)
            if admission is not None:
                result["admission"] = admission.stats()
            caches = {}
            for name in ("reserve", "market"):
                stats = getattr(service, name + "_cache_stats", None)
                if callable(stats):
                    caches[name] = stats()
            if caches:
                result["risk_cache"] = caches
            return 200, result
        if method == "GET" and path == "/v1/events":
            self._permit(principal, "reader", "trader", "risk")
            after, limit = _event_cursor(query)
            if principal.role in ("admin", "risk"):
                return 200, service.events(after=after, limit=limit)
            return 200, service.account_events(principal.account_id, after=after, limit=limit)
        if method == "GET" and path == "/v1/trades":
            self._permit(principal, "risk")
            after, limit = _event_cursor(query)
            return 200, self._component("matcher").trades(after=after, limit=limit)
        if method == "POST" and path in ("/v1/matching", "/v1/spot-matching"):
            self._permit(principal)
            data = _fields(payload, {"symbol"}, {"max_matches"})
            symbol = _identifier(data["symbol"], market=True)
            maximum = data.get("max_matches", 100)
            if type(maximum) is not int or not 1 <= maximum <= 1000:
                raise _RequestError(400, "invalid_fields", "max_matches must be an integer in 1..1000")
            component = self._component("matcher" if path == "/v1/matching" else "spot")
            return 200, component.match_once(symbol, max_matches=maximum)
        if method == "PUT" and path == "/v1/credit/asset-limit":
            self._permit(principal, "risk")
            data = _fields(payload, {"asset", "limit"})
            asset, limit = _identifier(data["asset"], market=True), _decimal(data["limit"])
            return 200, self._component("credit").configure_asset_limit(asset, limit)
        if method == "POST" and path == "/v1/credit/pool":
            self._permit(principal)
            data = _fields(payload, {"command_id", "asset", "amount", "source_reference"})
            command_id = _identifier(data["command_id"])
            asset, amount = _identifier(data["asset"], market=True), _decimal(data["amount"])
            reference = _identifier(data["source_reference"], market=True)
            return 200, self._component("credit").fund_pool(command_id, asset, amount, source_reference=reference)
        if method == "POST" and path == "/v1/accounts":
            self._permit(principal)
            data = _fields(payload, {"account_id"})
            return 201, service.create_account(_identifier(data["account_id"]))
        if method == "PUT" and path == "/v1/market":
            self._permit(principal, "risk")
            from .market import MarketSnapshot
            try:
                snapshot = MarketSnapshot.from_json(body.decode("utf-8"))
            except (ValueError, KeyError, TypeError, RecursionError):
                raise _RequestError(400, "invalid_market", "invalid market snapshot") from None
            return 200, service.publish_market(snapshot)
        if method == "PUT" and path == "/v1/kill-switch":
            self._permit(principal, "risk")
            data = _fields(payload, {"enabled"})
            if type(data["enabled"]) is not bool:
                raise _RequestError(400, "invalid_fields", "enabled must be a boolean")
            return 200, service.set_kill_switch(data["enabled"])
        if len(parts) >= 4 and parts[:3] == ["", "v1", "accounts"]:
            account_id = _identifier(parts[3])
            self._account(principal, account_id)
            if method == "GET":
                self._permit(principal, "reader", "trader", "risk")
                if len(parts) == 4:
                    return 200, service.account(account_id)
                if len(parts) == 5 and parts[4] == "risk":
                    return 200, service.risk(account_id)
                if len(parts) == 5 and parts[4] == "orders":
                    return 200, service.orders(account_id)
                if len(parts) == 6 and parts[4] == "orders":
                    return 200, service.order(account_id, _identifier(parts[5]))
                if len(parts) == 5 and parts[4] == "spot-orders":
                    return 200, self._component("spot").orders(account_id)
                if len(parts) == 5 and parts[4] == "events":
                    after, limit = _event_cursor(query)
                    return 200, service.account_events(account_id, after=after, limit=limit)
            if method == "PUT" and len(parts) == 5 and parts[4] == "credit-limits":
                self._permit(principal, "risk")
                data = _fields(payload, {"asset", "limit"})
                asset, limit = _identifier(data["asset"], market=True), _decimal(data["limit"])
                return 200, self._component("credit").configure_limit(account_id, asset, limit)
            if method == "POST":
                if len(parts) == 5 and parts[4] in ("loans", "repayments", "interest"):
                    self._permit(principal, "funding" if parts[4] != "interest" else "admin")
                    data = _fields(payload, {"command_id", "asset", "amount"})
                    command_id = _identifier(data["command_id"])
                    asset, amount = _identifier(data["asset"], market=True), _decimal(data["amount"])
                    credit = self._component("credit")
                    operation = {"loans": credit.borrow, "repayments": credit.repay,
                                 "interest": credit.accrue_interest}[parts[4]]
                    return 200, operation(account_id, command_id, asset, amount)
                if len(parts) == 5 and parts[4] == "spot-orders":
                    self._permit(principal, "trader")
                    data = _fields(payload, {"order_id", "symbol", "quantity", "limit_price"})
                    order_id, symbol = _identifier(data["order_id"]), _identifier(data["symbol"], market=True)
                    quantity, price = _decimal(data["quantity"]), _decimal(data["limit_price"])
                    return 201, self._component("spot").submit_order(account_id, order_id, symbol, quantity, price)
                if len(parts) == 7 and parts[4] == "spot-orders" and parts[6] == "cancel":
                    self._permit(principal, "trader")
                    _fields(payload, set())
                    order_id = _identifier(parts[5])
                    return 200, self._component("spot").cancel_order(account_id, order_id)
                if len(parts) == 5 and parts[4] == "supervise":
                    self._permit(principal, "risk")
                    _fields(payload, set())
                    return 200, service.supervise_account(account_id)
                if len(parts) == 5 and parts[4] == "deposits":
                    self._permit(principal, "funding")
                    data = _fields(payload, {"event_id", "asset", "amount"})
                    return 200, service.deposit(account_id, _identifier(data["event_id"]),
                                                _identifier(data["asset"], market=True), _decimal(data["amount"]))
                if len(parts) == 5 and parts[4] == "orders":
                    self._permit(principal, "trader")
                    data = _fields(payload, {"order_id", "symbol", "quantity", "limit_price"},
                                   {"reduce_only"})
                    reduce_only = data.get("reduce_only", False)
                    if type(reduce_only) is not bool:
                        raise _RequestError(400, "invalid_fields", "reduce_only must be a boolean")
                    return 201, self._order_command("submit_order",
                        account_id, _identifier(data["order_id"]), _identifier(data["symbol"], market=True),
                        _decimal(data["quantity"]), _decimal(data["limit_price"]),
                        reduce_only=reduce_only)
                if len(parts) == 7 and parts[4] == "orders":
                    order_id = _identifier(parts[5])
                    if parts[6] == "cancel":
                        self._permit(principal, "trader")
                        _fields(payload, set())
                        return 200, self._order_command("cancel_order", account_id, order_id)
                    if parts[6] == "fills":
                        self._permit(principal)
                        if getattr(service, "product_catalog", None) is not None:
                            raise _RequestError(409, "paired_execution_required", "configured products require paired execution through the matcher")
                        data = _fields(payload, {"fill_id", "quantity", "price"})
                        return 200, service.apply_fill(
                            account_id, order_id, _identifier(data["fill_id"]),
                            _decimal(data["quantity"]), _decimal(data["price"]))
        raise _RequestError(404, "not_found", "route not found")

    def _dispatch(self):
        self.server._count("requests")
        try:
            length = self._framing(self.command in ("POST", "PUT"))
            parsed = urlsplit(self.path)
            if (parsed.scheme or parsed.netloc or parsed.fragment or "%" in parsed.path
                    or not parsed.path.startswith("/") or "//" in parsed.path):
                raise _RequestError(400, "invalid_path", "invalid request path")
            if self.command == "GET" and parsed.path == "/healthz" and not parsed.query:
                status, result = 200, {"status": "ok"}
            else:
                principal = self._principal()
                payload, body = (None, b"")
                if self.command in ("POST", "PUT"):
                    payload, body = self._payload(length)
                status, result = self._route(principal, parsed.path, parsed.query, payload, body)
            self._reply(status, result)
        except _RequestError as exc:
            self.server._count("server_errors" if exc.status >= 500 else "client_errors")
            self._reply(exc.status, {"error": {"code": exc.code, "message": exc.message}})
        except (TimeoutError, socket.timeout):
            self.server._count("client_errors")
            self._reply(408, {"error": {"code": "request_timeout", "message": "request timed out"}})
        except (BrokenPipeError, ConnectionResetError):
            # Client disconnected; all service mutations have their own durable
            # idempotency keys, so reconnecting clients can safely retry them.
            pass
        except Exception as exc:
            # Import lazily so this transport can be tested in isolation. Only
            # the service's explicit error type may expose business messages.
            try:
                from .service import ServiceError
                business_error = isinstance(exc, ServiceError)
            except ImportError:
                business_error = False
            if business_error:
                status = exc.status if type(exc.status) is int and 400 <= exc.status <= 599 else 400
                code = exc.code if isinstance(exc.code, str) and re.fullmatch(r"[A-Za-z_]{1,64}", exc.code) else "service_error"
                message = str(exc)[:256]
                self.server._count("server_errors" if status >= 500 else "client_errors")
                self._reply(status, {"error": {"code": code, "message": message}})
            else:
                self.server._count("server_errors")
                self._reply(500, {"error": {"code": "internal_error", "message": "internal service error"}})

    do_GET = _dispatch
    do_POST = _dispatch
    do_PUT = _dispatch


def make_server(service, host: str = "127.0.0.1", port: int = 8080, *,
                credentials: Iterable[Credential], max_workers: int = 16,
                request_timeout: float = 5.0, admission_timeout: float = 2.0) -> HTTPServer:
    """Construct a bounded internal server; the caller owns its lifecycle.

    Bind only to an IPv4 loopback address. Remote access requires a separate
    TLS proxy. Socket read deadlines and a worker cap bound stalled requests.
    """
    try:
        address = ipaddress.ip_address(host)
    except ValueError:
        raise ValueError("gateway host must be an IPv4 loopback address") from None
    if address.version != 4 or not address.is_loopback:
        raise ValueError("gateway host must be an IPv4 loopback address")
    if type(port) is not int or not 0 <= port <= 65535:
        raise ValueError("port must be an integer in 0..65535")
    if type(max_workers) is not int or not 1 <= max_workers <= 256:
        raise ValueError("max_workers must be an integer in 1..256")
    if (type(request_timeout) not in (int, float) or not 0.1 <= request_timeout <= 60):
        raise ValueError("request_timeout must be in 0.1..60 seconds")
    if (type(admission_timeout) not in (int, float) or not .001 <= admission_timeout <= 60):
        raise ValueError("admission_timeout must be finite and in .001..60 seconds")
    return _GatewayServer((str(address), port), service, _credentials(credentials),
                          max_workers=max_workers, request_timeout=request_timeout,
                          admission_timeout=admission_timeout)
