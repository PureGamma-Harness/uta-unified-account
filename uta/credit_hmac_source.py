"""Unwired, default-disabled HMAC source candidates; no financial permission.

Only the real durable HMAC verifier can issue an opaque local handle. Exported
candidate data cannot be imported as a handle. No SQL source/inbox/native or
HTTP/CLI integration exists here. See docs/credit-hmac-source-contract.md.
"""
from __future__ import annotations

from datetime import datetime, timezone
from email.message import Message
import hashlib
import json
import os
import re
import secrets
from threading import RLock, current_thread
from types import MappingProxyType

from .request_signing import (NonceStore, RequestAuthenticator, SigningError,
                              canonical_request, load_profile)


_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}\Z", re.ASCII)
_PATH = re.compile(r"/v2/accounts/([A-Za-z0-9][A-Za-z0-9_.:-]{0,127})/borrow\Z", re.ASCII)
_AMOUNT = re.compile(r"(0|[1-9][0-9]{0,29})(?:\.([0-9]{1,8}))?\Z", re.ASCII)
_HEADERS = ("Authorization", "X-UTA-Version", "X-UTA-Tenant", "X-UTA-Audience",
            "X-UTA-Key-Id", "X-UTA-Timestamp-Ms", "X-UTA-Nonce", "X-UTA-Signature")


class CreditSourceError(ValueError):
    def __init__(self, code, message, status=403):
        super().__init__(message)
        self.code, self.status = code, status


class _Receipt:
    """No public fields or constructor; identity in the issuer is the seal."""
    __slots__ = ()

    def __new__(cls):
        raise TypeError("credit source receipts are issued only after authentication")

    def __reduce_ex__(self, protocol):
        raise TypeError("credit source receipts cannot be copied or serialized")


def _hash(value):
    return hashlib.sha256(value).hexdigest()


def _json(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False)


def _pairs(values):
    result = {}
    for key, value in values:
        if key in result:
            raise ValueError("duplicate field")
        result[key] = value
    return result


def _no_number(value):
    raise ValueError("JSON numbers are not supported")


def _business(method, target, body):
    try:
        path = _PATH.fullmatch(target) if type(target) is str else None
        if method != "POST" or path is None:
            raise ValueError("unsupported component path")
        account = path[1]
        data = json.loads(body.decode("utf-8"), object_pairs_hook=_pairs,
                          parse_int=_no_number, parse_float=_no_number, parse_constant=_no_number)
        if (type(data) is not dict or set(data) != {"command_id", "asset", "amount"}
                or type(data["command_id"]) is not str or not _ID.fullmatch(data["command_id"])
                or data["asset"] != "BTC" or type(data["amount"]) is not str):
            raise ValueError("invalid body fields")
        amount = _AMOUNT.fullmatch(data["amount"])
        if amount is None:
            raise ValueError("invalid amount")
        units = int(amount[1]) * 100_000_000 + int((amount[2] or "").ljust(8, "0"))
        if not 0 < units < 10**38:
            raise ValueError("amount out of range")
        whole, fraction = divmod(units, 100_000_000)
        normalized = str(whole) + (("." + f"{fraction:08d}".rstrip("0")) if fraction else "")
        payload = _json({"account_id": account, "asset": "BTC", "amount": normalized})
        return account, data["command_id"], payload
    except (TypeError, ValueError, UnicodeError, RecursionError, AttributeError):
        raise CreditSourceError("credit_source_input_invalid", "invalid signed credit source candidate", 400) from None


def _headers(headers):
    """Freeze request headers before verification and metadata extraction."""
    frozen = Message()
    try:
        for name in _HEADERS:
            values = headers.get_all(name, []) if hasattr(headers, "get_all") else ([headers[name]] if name in headers else [])
            for value in values:
                if type(value) is not str:
                    raise ValueError("invalid header")
                frozen[name] = value
    except (TypeError, ValueError, KeyError):
        raise SigningError("signature_required", "valid HMAC request authentication is required") from None
    return frozen


class CreditHmacSource:
    """Trusted local source-capture policy, never a financial authorization.

    ``grants`` is a local iterable of exact (key_id, account_id) pairs. No role,
    including funding/admin, grants capture without that explicit allowlist.
    No arbitrary authenticator/principal or reconstructed receipt is accepted.
    """

    def __init__(self, auth_database, profile_path, *, tenant_id, producer_binding,
                 grants=(), enabled=False, max_commands=256, max_receipts=1024):
        if enabled is not True:
            raise CreditSourceError("credit_source_disabled", "HMAC source capture is disabled", 501)
        if (type(tenant_id) is not str or not _ID.fullmatch(tenant_id)
                or type(producer_binding) is not str or not re.fullmatch(r"[0-9a-f]{64}", producer_binding)):
            raise ValueError("trusted tenant and producer binding are required")
        for value in (max_commands, max_receipts):
            if type(value) is not int or not 1 <= value <= 10000:
                raise ValueError("candidate registry capacity must be 1..10000")
        policy = frozenset(grants)
        if not policy or any(type(pair) is not tuple or len(pair) != 2
                or any(type(item) is not str or not _ID.fullmatch(item) for item in pair) for pair in policy):
            raise ValueError("explicit local key/account grants are required")
        store = NonceStore(auth_database)  # Existing authority only; never initialize.
        if (store.tenant_id, store.producer_binding) != (tenant_id, producer_binding):
            raise ValueError("authentication authority does not match trusted local scope")
        authenticator = RequestAuthenticator(store, load_profile(profile_path))
        self._authenticator = authenticator
        self._grants = policy
        self._pid = os.getpid()
        self._boot = secrets.token_hex(32)
        self._lock = RLock()
        self._commands = {}
        self._receipts = {}
        self._max_commands, self._max_receipts = max_commands, max_receipts

    def _process(self):
        # Check before acquiring a possibly inherited locked RLock after fork.
        if os.getpid() != self._pid:
            raise CreditSourceError("credit_source_process_mismatch", "source issuer belongs to another process")

    def replace_profile(self, profile_path):
        """Use the real private loader and durable monotonic rotation API."""
        self._process()
        with self._lock:
            self._authenticator.replace_profile(load_profile(profile_path))

    def issue(self, headers, *, method, request_target, body):
        self._process()
        frozen = _headers(headers)
        with self._lock:
            if len(self._receipts) >= self._max_receipts:
                raise CreditSourceError("credit_source_capacity", "opaque receipt capacity exhausted", 503)
            principal = self._authenticator.authenticate(frozen, method=method,
                request_target=request_target, body=body)
            account, command_id, payload = _business(method, request_target, body)
            key_id = frozen["X-UTA-Key-Id"]
            if (principal.role != "funding" or principal.account_id != account
                    or (key_id, account) not in self._grants):
                raise CreditSourceError("credit_source_forbidden", "source-capture role or account grant is absent")
            previous = self._commands.get(command_id)
            if previous is not None:
                if (previous["account_id"], previous["command_payload"]) != (account, payload):
                    raise CreditSourceError("idempotency_conflict", "candidate command identity has different business content", 409)
                candidate = previous
            else:
                if len(self._commands) >= self._max_commands:
                    raise CreditSourceError("credit_source_capacity", "first candidate identity capacity exhausted", 503)
                canonical = canonical_request(tenant_id=frozen["X-UTA-Tenant"], audience=frozen["X-UTA-Audience"],
                    key_id=key_id, timestamp_ms=int(frozen["X-UTA-Timestamp-Ms"]), nonce=frozen["X-UTA-Nonce"],
                    method=method, request_target=request_target, body=body)
                candidate = {"format": "credit-hmac-source-candidate-v1", "tenant_id": frozen["X-UTA-Tenant"],
                    "audience": frozen["X-UTA-Audience"], "producer_binding": self._authenticator.store.producer_binding,
                    "key_id": key_id, "role": principal.role, "key_account_id": principal.account_id,
                    "account_id": account, "command_id": command_id, "kind": "BORROW",
                    "command_payload": payload, "payload_hash": _hash(payload.encode("utf-8")),
                    "method": method, "request_target": request_target, "body_hash": _hash(body),
                    "request_hash": _hash(canonical), "nonce_hash": _hash(frozen["X-UTA-Nonce"].encode("ascii")),
                    "signed_timestamp_ms": int(frozen["X-UTA-Timestamp-Ms"]),
                    "captured_at": datetime.now(timezone.utc).isoformat(timespec="microseconds"),
                    "issuer_boot": self._boot, "issuer_pid": self._pid,
                    "auth_audit_sequence": None, "accepted_profile_revision": None, "credential_epoch": None,
                    "financial_authorized": False, "revocation_barrier": "NO_GO"}
                candidate["source_reference"] = "credit-hmac-candidate:" + _hash(_json(candidate).encode("utf-8"))
                candidate = MappingProxyType(candidate)
                self._commands[command_id] = candidate
            receipt = object.__new__(_Receipt)
            self._receipts[receipt] = (current_thread(), candidate)
            return receipt

    def _registered(self, receipt):
        if type(receipt) is not _Receipt or receipt not in self._receipts:
            raise CreditSourceError("credit_source_receipt_invalid", "receipt is not registered with this issuer")
        thread, candidate = self._receipts[receipt]
        if thread is not current_thread():
            raise CreditSourceError("credit_source_thread_mismatch", "receipt belongs to another thread")
        return candidate

    def inspect(self, receipt, *, account_id, command_id, command_payload):
        """Export immutable evidence after identity/scope checks; no permission."""
        self._process()
        with self._lock:
            candidate = self._registered(receipt)
            if (type(account_id) is not str or type(command_id) is not str or type(command_payload) is not str
                    or (account_id, command_id, command_payload) !=
                       (candidate["account_id"], candidate["command_id"], candidate["command_payload"])):
                raise CreditSourceError("credit_source_receipt_mismatch", "receipt differs from requested business identity")
            return candidate

    def release(self, receipt):
        """Forget a local handle; immutable first candidate identities remain."""
        self._process()
        with self._lock:
            self._registered(receipt)
            del self._receipts[receipt]
