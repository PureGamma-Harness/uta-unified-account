"""Local-only JSON demonstration of the reference risk calculations.

This server has no authentication, persistence, price feeds, order routing or
concurrency control. It must not be exposed to a network or used for trading.
All prices and balances are supplied by the requester; use decimal strings.
"""
from dataclasses import asdict, is_dataclass
from decimal import Decimal, InvalidOperation, DecimalException
from datetime import datetime
from http.server import BaseHTTPRequestHandler, HTTPServer
from json import JSONDecodeError
import json
from enum import Enum

from .models import Account, AssetSpec, InstrumentSpec, Position, RiskInputError
from .risk import calculate_risk, check_order

MAX_BODY = 64 * 1024

SAMPLE = {
    "balances": {"USD": "1000"},
    "positions": {"BTC-PERP": {"quantity": "0.1", "entry_price": "20000"}},
    "open_order_margin": "0",
    "assets": {"USD": {"price": "1", "collateral_factor": "1"}},
    "instruments": {"BTC-PERP": {"mark_price": "21000", "initial_margin_rate": "0.1", "maintenance_margin_rate": "0.05"}},
}


def _decimal(value, name):
    # Reject JSON numbers: float parsing can silently lose monetary precision.
    if not isinstance(value, str) or len(value) > 80:
        raise ValueError(f"{name} must be a decimal string (at most 80 characters)")
    try:
        n = Decimal(value)
    except InvalidOperation as exc:
        raise ValueError(f"invalid decimal for {name}") from exc
    if not n.is_finite() or abs(n.as_tuple().exponent) > 100 or (n and abs(n.adjusted()) > 100):
        raise ValueError(f"{name} must be finite with exponent within +/-100")
    return n


def _object(value, name):
    if not isinstance(value, dict):
        raise ValueError(f"{name} must be an object")
    return value


def parse_account(payload):
    payload = _object(payload, "request")
    balances = {k: _decimal(v, f"balance {k}") for k, v in _object(payload["balances"], "balances").items()}
    liabilities = {k: _decimal(v, f"liability {k}") for k, v in _object(payload.get("liabilities", {}), "liabilities").items()}
    positions = {}
    for symbol, p in _object(payload.get("positions", {}), "positions").items():
        p = _object(p, f"position {symbol}")
        positions[symbol] = Position(symbol, _decimal(p["quantity"], "quantity"), _decimal(p["entry_price"], "entry_price"))
    assets = {}
    for symbol, spec in _object(payload["assets"], "assets").items():
        spec = _object(spec, f"asset {symbol}")
        assets[symbol] = AssetSpec(_decimal(spec["price"], "price"), _decimal(spec["collateral_factor"], "collateral_factor"))
    instruments = {}
    for symbol, spec in _object(payload.get("instruments", {}), "instruments").items():
        spec = _object(spec, f"instrument {symbol}")
        instruments[symbol] = InstrumentSpec(_decimal(spec["mark_price"], "mark_price"), _decimal(spec["initial_margin_rate"], "initial_margin_rate"), _decimal(spec["maintenance_margin_rate"], "maintenance_margin_rate"))
    account = Account(balances, positions, _decimal(payload.get("open_order_margin", "0"), "open_order_margin"), liabilities)
    return account, assets, instruments


def json_value(value):
    if is_dataclass(value):
        return {k: json_value(v) for k, v in asdict(value).items()}
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, dict):
        return {k: json_value(v) for k, v in value.items()}
    if isinstance(value, (tuple, list)):
        return [json_value(v) for v in value]
    return value


def evaluate(path, payload):
    account, assets, instruments = parse_account(payload)
    if path == "/risk":
        return json_value(calculate_risk(account, assets, instruments))
    if path == "/order-check":
        order = _object(payload["order"], "order")
        symbol = order["symbol"]
        if not isinstance(symbol, str) or not symbol:
            raise ValueError("order symbol must be a nonempty string")
        result = check_order(account, assets, instruments, symbol=symbol,
                             quantity=_decimal(order["quantity"], "quantity"),
                             execution_price=_decimal(order["execution_price"], "execution_price"),
                             fee_rate=_decimal(order.get("fee_rate", "0"), "fee_rate"))
        return json_value(result)
    raise ValueError("unknown route")


class Handler(BaseHTTPRequestHandler):
    server_version = "UTAReference/0.1"

    def log_message(self, format, *args):
        # Avoid logging potentially sensitive request data.
        pass

    def _reply(self, status, data):
        body = json.dumps(data, ensure_ascii=False, allow_nan=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path == "/health":
            self._reply(200, {"status": "ok", "mode": "local-demo", "trading_enabled": False})
        elif self.path == "/sample":
            self._reply(200, SAMPLE)
        else:
            self._reply(404, {"error": "not found"})

    def do_POST(self):
        if self.path not in ("/risk", "/order-check"):
            self._reply(404, {"error": "not found"})
            return
        try:
            if self.headers.get_content_type() != "application/json":
                self._reply(415, {"error": "application/json required"})
                return
            length = int(self.headers.get("Content-Length", "-1"))
            if length < 0 or length > MAX_BODY:
                self._reply(413, {"error": "invalid or oversized request body"})
                return
            payload = json.loads(self.rfile.read(length))
            self._reply(200, evaluate(self.path, payload))
        except (ValueError, KeyError, TypeError, JSONDecodeError, RiskInputError, DecimalException, OverflowError) as exc:
            self._reply(400, {"error": f"invalid request: {exc}"})


def serve(port=8080):
    # Deliberately bind only to loopback. Not a production server.
    with HTTPServer(("127.0.0.1", port), Handler) as server:
        print(f"Local demo listening on http://127.0.0.1:{server.server_port} (no real orders)", flush=True)
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            pass
