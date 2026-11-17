"""Bounded internal exception metadata; never format an exception or read locals."""
import builtins
import re
import sqlite3
from itertools import islice
from types import MappingProxyType

from .admission import _BUSINESS_CODES, _EXPECTED_UNAVAILABLE, _FATAL_CODES


MAX_CAUSES = 8
MAX_FRAMES = 8
MAX_ATTRIBUTES = 16
_BUILTIN_EXCEPTIONS = tuple(value for value in vars(builtins).values()
                            if isinstance(value, type) and issubclass(value, BaseException))
_IDENTIFIER = re.compile(r"[A-Za-z_<>][A-Za-z0-9_.<>-]{0,127}\Z", re.ASCII)
# Only reviewed public literals may leave an exception's data dictionary. New
# unlisted codes remain null until explicitly reviewed; arbitrary keys/messages
# must never become diagnostics merely because they resemble an identifier.
_PUBLIC_CODES = frozenset(_BUSINESS_CODES | _EXPECTED_UNAVAILABLE | _FATAL_CODES | {
    "audit_artifact_unavailable", "audit_content_conflict", "audit_market_mismatch",
    "audit_market_missing", "audit_not_found", "audit_partial_schema", "audit_replay_precision",
    "audit_schema_corrupt", "audit_schema_version", "replay_artifact_unavailable", "replay_engine_mismatch",
    "authority_conflict", "authority_path_conflict", "fence_clock_invalid", "fence_clock_regressed",
    "fence_clock_unavailable", "fence_control_corrupt", "fence_corrupt", "fence_exhausted",
    "fence_guard_corrupt", "fence_guard_failed", "fence_not_managed", "fence_upgrade_required",
    "lease_busy", "lease_expired", "read_only_transaction", "transaction_control_forbidden",
    "unguarded_connection", "writer_fenced", "control_corruption", "control_superseded",
    "funding_registry_conflict", "funding_source_conflict", "invalid_layout", "invalid_market",
    "invalid_shard", "layout_conflict", "layout_corruption", "layout_missing", "market_barrier_mismatch",
    "market_conflict", "market_regression", "publication_incomplete", "router_busy", "router_halted",
    "shard_identity_conflict", "shard_unavailable", "unsafe_control", "unsafe_directory", "unsafe_lock",
    "credit_corrupt", "credit_disabled", "credit_integration_missing", "credit_limit",
    "credit_policy_unavailable", "credit_pool_empty", "credit_schema_version", "insufficient_cash",
    "repayment_exceeds_debt", "unknown_asset", "unsupported_durable_command",
})


def _identifier(value):
    return value if type(value) is str and _IDENTIFIER.fullmatch(value) else None


def _exception_slot(exception, name):
    # Read BaseException's native slots/dictionary directly: subclass properties,
    # __getattribute__, __str__, __repr__ and exception notes are never invoked.
    return BaseException.__dict__[name].__get__(exception, BaseException)


def _native_fields(data, names):
    # Neither overridden dict.get nor malicious non-string keys' __eq__ should
    # run. A fixed native items scan also bounds metadata traversal work.
    items = MappingProxyType.items(data) if type(data) is MappingProxyType else dict.items(data)
    return {key: value for key, value in islice(items, MAX_ATTRIBUTES)
            if type(key) is str and key in names}


def capture_failure(cause):
    """Keep at most eight causes and eight frames per cause, without messages.

    Follow explicit __cause__, otherwise __context__, including suppressed
    context. Links label that distinction; cycles and truncation are explicit.
    Missing Python 3.10 sqlite metadata stays null and is never message-parsed.
    """
    if cause is None:
        return {"status": "cause_not_supplied", "chain": [], "chain_truncated": False, "chain_cycle": False}
    if not isinstance(cause, BaseException):
        raise ValueError("cause must be an exception or None")
    chain, seen, relation = [], set(), "root"
    while cause is not None and id(cause) not in seen and len(chain) < MAX_CAUSES:
        seen.add(id(cause))
        cls = type(cause)
        namespace = type.__dict__["__dict__"].__get__(cls, type)
        module = _identifier(_native_fields(namespace, frozenset({"__module__"})).get("__module__"))
        if module is None and any(cls is builtin for builtin in _BUILTIN_EXCEPTIONS):
            module = "builtins"
        name = _identifier(type.__dict__["__name__"].__get__(cls, type))
        data = _exception_slot(cause, "__dict__")
        fields = _native_fields(data, frozenset({"code", "sqlite_errorcode", "sqlite_errorname"}))
        code = fields.get("code")
        code = code if type(code) is str and len(code) <= 128 and code in _PUBLIC_CODES else None
        sqlite_code, sqlite_name = fields.get("sqlite_errorcode"), fields.get("sqlite_errorname")
        mro = type.__dict__["__mro__"].__get__(cls, type)
        if not any(base is sqlite3.Error for base in mro) or type(sqlite_code) is not int or not 0 <= sqlite_code <= 2**31 - 1:
            sqlite_code, sqlite_name = None, None
        if (type(sqlite_name) is not str or not sqlite_name.startswith("SQLITE_")
                or len(sqlite_name) > 128 or vars(sqlite3).get(sqlite_name) != sqlite_code):
            sqlite_name = None
        frames, traceback = [], _exception_slot(cause, "__traceback__")
        while traceback is not None and len(frames) < MAX_FRAMES:
            frame = traceback.tb_frame
            globals_name = _native_fields(frame.f_globals, frozenset({"__name__"})).get("__name__")
            frames.append({"module": _identifier(globals_name),
                           "function": _identifier(frame.f_code.co_name), "lineno": traceback.tb_lineno})
            traceback = traceback.tb_next
        chain.append({"type": (module + "." + name) if module and name else None,
                      "relation": relation, "public_code": code,
                      "sqlite_errorcode": sqlite_code, "sqlite_errorname": sqlite_name,
                      "attributes_truncated": dict.__len__(data) > MAX_ATTRIBUTES,
                      "frames": frames, "frames_truncated": traceback is not None})
        next_cause = _exception_slot(cause, "__cause__")
        relation = "cause" if next_cause is not None else "context"
        cause = next_cause if next_cause is not None else _exception_slot(cause, "__context__")
    return {"status": "captured", "chain": chain,
            "chain_truncated": cause is not None and id(cause) not in seen,
            "chain_cycle": cause is not None and id(cause) in seen}
