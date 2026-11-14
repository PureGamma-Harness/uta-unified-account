"""HTTP transport for the loopback-only UTA simulator."""
from __future__ import annotations

from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import re
from threading import BoundedSemaphore

from .simulator import Simulator, SimulatorError
from .store import AccountNotFound, StoreConflict, StoreError

MAX_BODY = 64 * 1024
MAX_BATCH_ITEMS = 100
SOCKET_TIMEOUT = 5
MAX_ACTIVE_REQUESTS = 64
ACCOUNT_PATH = re.compile(r"/v1/accounts/([A-Za-z0-9][A-Za-z0-9_.-]{0,63})(/events|/commands|/replay)?")
DASHBOARD = Path(__file__).with_name("dashboard.html")
BUSY_BODY = b'{"error":"too many concurrent requests"}'
BUSY_RESPONSE = (
    b"HTTP/1.0 503 Service Unavailable\r\n"
    b"Retry-After: 1\r\nConnection: close\r\nCache-Control: no-store\r\n"
    b"X-Content-Type-Options: nosniff\r\nContent-Type: application/json; charset=utf-8\r\n"
    + f"Content-Length: {len(BUSY_BODY)}\r\n\r\n".encode("ascii")
    + BUSY_BODY
)


class RequestError(ValueError):
    def __init__(self, status, message):
        super().__init__(message)
        self.status = status


def _unique_object(pairs):
    obj = {}
    for key, value in pairs:
        if key in obj:
            raise ValueError("duplicate JSON field")
        obj[key] = value
    return obj


def _reject_nonfinite(_):
    raise ValueError("non-finite JSON number")


def _shape(payload, field_names):
    if not isinstance(payload, dict) or set(payload) != set(field_names):
        raise RequestError(400, "expected fields: " + ", ".join(field_names))
    return payload


class SimulatorServer(ThreadingHTTPServer):
    daemon_threads = True
    request_queue_size = 128

    def __init__(self, simulator, port, *, max_active=MAX_ACTIVE_REQUESTS):
        if type(max_active) is not int or max_active < 1:
            raise ValueError("max_active must be a positive integer")
        self.simulator = simulator
        self._slots = BoundedSemaphore(max_active)
        super().__init__(("127.0.0.1", port), Handler)

    def get_request(self):
        connection, address = super().get_request()
        connection.settimeout(SOCKET_TIMEOUT)
        return connection, address

    def process_request(self, request, client_address):
        if not self._slots.acquire(blocking=False):
            # Keep the accept loop available even if a rejected peer stops reading.
            try:
                request.setblocking(False)
                request.sendall(BUSY_RESPONSE)
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


class Handler(BaseHTTPRequestHandler):
    server_version = "UTA-Simulator"
    sys_version = ""

    def log_message(self, format, *args):
        pass

    def _response(self, status, data, content_type="application/json; charset=utf-8"):
        body = (data if isinstance(data, bytes) else
                json.dumps(data, ensure_ascii=True, allow_nan=False, separators=(",", ":")).encode("utf-8"))
        self.close_connection = True
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("Connection", "close")
        self.send_header("Content-Security-Policy",
                         "default-src 'self'; script-src 'unsafe-inline'; style-src 'unsafe-inline'; "
                         "connect-src 'self'; img-src 'self' data:; object-src 'none'; "
                         "base-uri 'none'; form-action 'self'; frame-ancestors 'none'")
        self.end_headers()
        self.wfile.write(body)

    def send_error(self, code, message=None, explain=None):
        # Do not echo malformed HTTP lines or unsupported methods.
        self._response(code, {"error": self.responses.get(code, ("HTTP error",))[0]})

    def _guard(self):
        port = self.server.server_port
        allowed = {f"127.0.0.1:{port}", f"localhost:{port}"}
        if port == 80:
            allowed.update(("localhost", "127.0.0.1"))
        hosts = self.headers.get_all("Host", [])
        if len(hosts) != 1 or hosts[0].lower() not in allowed:
            raise RequestError(403, "localhost Host header required")

        origins = self.headers.get_all("Origin", [])
        if origins and origins != [f"http://{hosts[0].lower()}"]:
            raise RequestError(403, "cross-origin request denied")
        fetch_sites = self.headers.get_all("Sec-Fetch-Site", [])
        if fetch_sites and fetch_sites not in (["same-origin"], ["none"]):
            raise RequestError(403, "cross-origin request denied")

    def _body(self):
        content_types = self.headers.get_all("Content-Type", [])
        if len(content_types) != 1 or self.headers.get_content_type() != "application/json":
            raise RequestError(415, "application/json required")
        if self.headers.get_all("Transfer-Encoding"):
            raise RequestError(400, "transfer encoding is unsupported")
        lengths = self.headers.get_all("Content-Length", [])
        if len(lengths) != 1 or not re.fullmatch(r"[0-9]{1,10}", lengths[0]):
            raise RequestError(400, "one valid Content-Length header is required")
        size = int(lengths[0])
        if size > MAX_BODY:
            raise RequestError(413, "request body exceeds 64 KiB")
        try:
            data = self.rfile.read(size)
        except TimeoutError as exc:
            raise RequestError(408, "request body timed out") from exc
        if len(data) != size:
            raise RequestError(400, "incomplete request body")
        try:
            return json.loads(data.decode("utf-8"), object_pairs_hook=_unique_object,
                              parse_constant=_reject_nonfinite)
        except (ValueError, RecursionError) as exc:
            raise RequestError(400, "valid UTF-8 JSON with unique fields required") from exc

    def _get(self):
        if self.path == "/":
            return 200, DASHBOARD.read_bytes(), "text/html; charset=utf-8"
        route = ACCOUNT_PATH.fullmatch(self.path)
        if route:
            account_id, suffix = route.groups()
            if suffix is None:
                return 200, self.server.simulator.view(account_id)
            if suffix == "/events":
                return 200, {"events": self.server.simulator.events(account_id)}
            if suffix == "/replay":
                return 200, self.server.simulator.verify_replay(account_id)
        raise RequestError(404, "not found")

    def _post(self):
        simulator = self.server.simulator
        if self.path == "/v1/bootstrap":
            payload = _shape(self._body(), ("account_id",))
            return 200, simulator.bootstrap(payload["account_id"])
        if self.path == "/v1/import-classic":
            payload = _shape(self._body(), ("account_id", "snapshot"))
            return 201, simulator.import_classic(payload["account_id"], payload["snapshot"])
        if self.path == "/v1/commands/batch":
            items = _shape(self._body(), ("items",))["items"]
            if not isinstance(items, list) or not 1 <= len(items) <= MAX_BATCH_ITEMS:
                raise RequestError(400, f"items must contain 1–{MAX_BATCH_ITEMS} commands")
            return 200, {"results": simulator.execute_batch(items)}
        route = ACCOUNT_PATH.fullmatch(self.path)
        if route and route[2] == "/commands":
            payload = _shape(self._body(), ("command_id", "expected_version", "command"))
            return 200, simulator.execute(route[1], **payload)
        raise RequestError(404, "not found")

    def _handle(self, route_handler):
        try:
            self._guard()
            response = route_handler()
            self._response(*response)
        except RequestError as exc:
            self._response(exc.status, {"error": str(exc)})
        except AccountNotFound:
            self._response(404, {"error": "account not found"})
        except StoreConflict as exc:
            self._response(409, {"error": str(exc)})
        except StoreError:
            self._response(503, {"error": "account store unavailable"})
        except SimulatorError as exc:
            self._response(400, {"error": str(exc)})
        except (BrokenPipeError, ConnectionResetError, TimeoutError):
            # Client may retry a submitted command with the same command ID.
            self.close_connection = True
        except Exception:
            self._response(500, {"error": "internal simulator error"})

    def do_GET(self):
        self._handle(self._get)

    def do_POST(self):
        self._handle(self._post)


def make_server(simulator, port=0, *, max_active=MAX_ACTIVE_REQUESTS):
    return SimulatorServer(simulator, port, max_active=max_active)


def serve(path, port=8765, *, shards=1):
    with make_server(Simulator(path, shards=shards), port) as server:
        url = f"http://127.0.0.1:{server.server_port}"
        print(f"UTA simulator available at {url}", flush=True)
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            pass
