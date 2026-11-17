"""Actual loaded credit-engine identity, without executing archived code.

An artifact is evidence, not an activation capability. Missing native code or
unsupported loaded state fails closed. The retained format is separate from the
base linear audit format and never authorizes a NATIVE_PREPARED authority.
"""
from __future__ import annotations

import dataclasses
from datetime import timedelta, timezone
from decimal import Decimal
from enum import Enum
from hashlib import sha256
import importlib
import inspect
import json
from pathlib import Path
import platform
import re
import sqlite3
import ssl
import sys
from types import CodeType, MappingProxyType

from . import __version__
from .decision_audit import _code_value
from .storage import StorageError


CREDIT_ARTIFACT_FORMAT = 1
_MODULES = ("service", "credit", "credit_policy", "credit_native", "credit_artifact",
            "decision_audit", "writer_fence", "durable_commands", "durable_batches",
            "reserve_kernel", "portfolio", "products", "models", "market", "ledger", "storage",
            "startup", "sharding", "durable_process", "gateway", "durable_gateway", "request_signing")
_REQUIRED_FUNCTIONS = frozenset({"uta.credit.CreditService._borrow", "uta.credit.CreditService._repay",
    "uta.credit_policy.validate_native_descriptor", "uta.credit_native.prepare_credit_native",
    "uta.writer_fence._TransactionGuard.before_commit", "uta.durable_commands.QueueStore._execute"})
# These are live process/connection registries and ContextVars, not financial
# constants. Their account, connection or nonce contents must never be archived.
_LIVE_GLOBALS = frozenset({"_REGISTRY", "_REGISTRY_LOCK", "_CONTROL_DDL_OVERRIDE",
    "_ACTIVE", "_ACTIVE_LOCK", "_EXISTING_ONLY_OPEN"})
_ARTIFACT_FIELDS = frozenset({"format", "audit_kind", "signed", "activation_permission", "app_version",
    "python_implementation", "python_version", "python_optimize", "sqlite_version", "openssl_version",
    "source_files", "source_digest", "loaded_credit_engine", "loaded_credit_constants", "loaded_engine_digest",
    "runtime_state_excluded", "closure_exclusion", "deployment_assumption"})


class CreditArtifactError(StorageError):
    def __init__(self, code, message):
        super().__init__(message)
        self.code = code


def _json(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def _hash(value):
    return sha256(_json(value).encode("utf-8")).hexdigest()


def _static(value, *, depth=0):
    """Describe known constant types without repr, custom hooks or live state."""
    if depth > 16:
        raise CreditArtifactError("credit_artifact_unavailable", "loaded constant nesting exceeds bounds")
    if value is None or type(value) in (bool, int, str):
        return value
    if type(value) is bytes:
        return {"bytes": value.hex()}
    if type(value) is float:
        return {"float": value.hex()}
    if type(value) is complex:
        return {"complex": [value.real.hex(), value.imag.hex()]}
    if type(value) is Decimal:
        if not value.is_finite():
            raise CreditArtifactError("credit_artifact_unavailable", "nonfinite loaded financial constant")
        sign, digits, exponent = value.as_tuple()
        return {"decimal": [sign, list(digits), exponent]}
    if type(value) is timedelta:
        return {"timedelta": [value.days, value.seconds, value.microseconds]}
    if type(value) is timezone:
        offset = value.utcoffset(None)
        return {"timezone": _static(offset, depth=depth + 1)}
    if value is Ellipsis:
        return {"ellipsis": True}
    if value is dataclasses.MISSING:
        return {"dataclass": "MISSING"}
    if value is getattr(dataclasses, "_HAS_DEFAULT_FACTORY", None):
        return {"dataclass": "DEFAULT_FACTORY"}
    if isinstance(value, Enum):
        return {"enum": type(value).__module__ + "." + type(value).__qualname__,
                "name": value.name, "value": _static(value.value, depth=depth + 1)}
    if type(value) is re.Pattern:
        return {"regex": value.pattern, "flags": value.flags}
    if type(value) in (tuple, list):
        return {"sequence_type": type(value).__name__,
                "values": [_static(item, depth=depth + 1) for item in value]}
    if type(value) in (set, frozenset):
        return {"set_type": type(value).__name__,
                "values": sorted((_static(item, depth=depth + 1) for item in value), key=_json)}
    if type(value) in (dict, MappingProxyType):
        return {"mapping": sorted([[_static(key, depth=depth + 1), _static(item, depth=depth + 1)]
                                   for key, item in value.items()], key=_json)}
    if inspect.isclass(value):
        return {"class": value.__module__ + "." + value.__qualname__}
    if inspect.isbuiltin(value):
        return {"builtin": (value.__module__ or "builtins") + "." + value.__qualname__}
    if inspect.isfunction(value):
        return {"function": value.__module__ + "." + value.__qualname__,
                "code": _code_value(value.__code__),
                "defaults": _static(value.__defaults__, depth=depth + 1),
                "kwdefaults": _static(value.__kwdefaults__, depth=depth + 1),
                "closure": _closure(value, depth=depth + 1)}
    raise CreditArtifactError("credit_artifact_unavailable", "unsupported loaded financial constant type")


def _closure(function, *, depth=0):
    if depth > 16:
        raise CreditArtifactError("credit_artifact_unavailable", "loaded function closure exceeds bounds")
    result = {}
    cells = function.__closure__ or ()
    for name, cell in zip(function.__code__.co_freevars, cells):
        try:
            value = cell.cell_contents
        except ValueError:
            result[name] = {"empty_cell": True}
            continue
        # dataclasses' standard repr recursion memo contains transient object/
        # thread IDs. It is not used for financial execution. Its user_function
        # and wrapper bytecode are still fingerprinted; no other closure skips.
        if (name == "repr_running" and function.__name__ == "__repr__"
                and function.__code__.co_freevars == ("repr_running", "user_function")
                and inspect.unwrap(function).__name__ == "__repr__"):
            result[name] = {"nonfinancial_repr_recursion_memo": "excluded"}
        else:
            result[name] = _static(value, depth=depth + 1)
    return result


def _module_functions(module):
    functions = {}
    for name, value in vars(module).items():
        if inspect.isfunction(value):
            functions[name] = value
        elif inspect.isclass(value) and value.__module__ == module.__name__:
            for member_name, member in vars(value).items():
                if isinstance(member, (staticmethod, classmethod)):
                    member = member.__func__
                if isinstance(member, property):
                    for accessor in ("fget", "fset", "fdel"):
                        function = getattr(member, accessor)
                        if function is not None:
                            functions[f"{name}.{member_name}.{accessor}"] = function
                elif inspect.isfunction(member):
                    functions[f"{name}.{member_name}"] = member
    return functions


def _loaded_modules(names):
    functions, constants = {}, {}
    try:
        for name in names:
            module = importlib.import_module("uta." + name)
            for attribute, function in _module_functions(module).items():
                unwrapped = inspect.unwrap(function)
                functions[module.__name__ + "." + attribute] = _hash({
                    "function": _code_value(function.__code__),
                    "unwrapped": _code_value(unwrapped.__code__),
                    "defaults": _static(function.__defaults__),
                    "kwdefaults": _static(function.__kwdefaults__),
                    "closure": _closure(function),
                    "unwrapped_defaults": _static(unwrapped.__defaults__),
                    "unwrapped_kwdefaults": _static(unwrapped.__kwdefaults__),
                    "unwrapped_closure": _closure(unwrapped)})
            for attribute, value in vars(module).items():
                if attribute.lstrip("_").isupper() and attribute not in _LIVE_GLOBALS:
                    # Uppercase scalar/container bindings are compiled financial
                    # constants (including SQL definitions), not inferred state.
                    constants[module.__name__ + "." + attribute] = _hash(_static(value))
    except CreditArtifactError:
        raise
    except (ImportError, OSError, ValueError, TypeError, AttributeError, RecursionError) as exc:
        raise CreditArtifactError("credit_artifact_unavailable", "actual credit engine cannot be fingerprinted") from exc
    return functions, constants


def credit_code_artifact():
    """Fingerprint current source, loaded code/defaults/constants and runtime.

    Imports use only the fixed compiled module list, never names/code retained
    in an untrusted historical artifact. No lease or DB permission is granted.
    """
    directory = Path(__file__).resolve().parent
    try:
        sources = {path.relative_to(directory).as_posix(): sha256(path.read_bytes()).hexdigest()
                   for path in sorted(directory.rglob("*.py"))}
        for name in _MODULES:
            if name + ".py" not in sources:
                raise CreditArtifactError("credit_artifact_unavailable", "required deployed credit source is absent")
        functions, constants = _loaded_modules(_MODULES)
        if not _REQUIRED_FUNCTIONS <= set(functions):
            raise CreditArtifactError("credit_artifact_unavailable", "required actual credit functions are absent")
    except CreditArtifactError:
        raise
    except (OSError, UnicodeError) as exc:
        raise CreditArtifactError("credit_artifact_unavailable", "deployed credit source cannot be read") from exc
    return {"format": CREDIT_ARTIFACT_FORMAT, "audit_kind": "CREDIT_BORROWED", "signed": False,
        "activation_permission": False, "app_version": __version__,
        "python_implementation": platform.python_implementation(), "python_version": sys.version,
        "python_optimize": sys.flags.optimize, "sqlite_version": sqlite3.sqlite_version,
        "openssl_version": ssl.OPENSSL_VERSION, "source_files": sources, "source_digest": _hash(sources),
        "loaded_credit_engine": functions, "loaded_credit_constants": constants,
        "loaded_engine_digest": _hash({"functions": functions, "constants": constants}),
        "runtime_state_excluded": sorted(_LIVE_GLOBALS),
        "closure_exclusion": "only standard dataclass nonfinancial repr recursion memo",
        "deployment_assumption": "immutable source and trusted OS process; artifact is not permission"}


def credit_artifact_id(manifest):
    if (type(manifest) is not dict or set(manifest) != _ARTIFACT_FIELDS
            or type(manifest.get("format")) is not int
            or manifest["format"] != CREDIT_ARTIFACT_FORMAT
            or manifest.get("audit_kind") != "CREDIT_BORROWED"
            or manifest.get("activation_permission") is not False or manifest.get("signed") is not False):
        raise CreditArtifactError("credit_artifact_invalid", "unsupported credit artifact format")
    try:
        for field in ("app_version", "python_implementation", "python_version", "sqlite_version",
                      "openssl_version", "closure_exclusion", "deployment_assumption"):
            if type(manifest[field]) is not str or not 1 <= len(manifest[field]) <= 4096:
                raise ValueError("invalid artifact metadata")
        if type(manifest["python_optimize"]) is not int or not 0 <= manifest["python_optimize"] <= 2:
            raise ValueError("invalid optimize flag")
        if manifest["runtime_state_excluded"] != sorted(_LIVE_GLOBALS):
            raise ValueError("unknown live-state exclusion contract")
        for field in ("source_files", "loaded_credit_engine", "loaded_credit_constants"):
            mapping = manifest[field]
            if type(mapping) is not dict or not 1 <= len(mapping) <= 16384:
                raise ValueError("invalid artifact map")
            if any(type(key) is not str or not 1 <= len(key) <= 512
                   or type(value) is not str or re.fullmatch("[0-9a-f]{64}", value) is None
                   for key, value in mapping.items()):
                raise ValueError("invalid artifact fingerprint")
        for path in manifest["source_files"]:
            if (not path.endswith(".py") or path.startswith("/") or "\\" in path
                    or any(part in ("", ".", "..") for part in path.split("/"))):
                raise ValueError("unsafe source identity")
        if not {name + ".py" for name in _MODULES} <= set(manifest["source_files"]):
            raise ValueError("incomplete credit source")
        if not _REQUIRED_FUNCTIONS <= set(manifest["loaded_credit_engine"]):
            raise ValueError("incomplete loaded credit engine")
        if manifest["source_digest"] != _hash(manifest["source_files"]):
            raise ValueError("source digest mismatch")
        if manifest["loaded_engine_digest"] != _hash({"functions": manifest["loaded_credit_engine"],
                                                     "constants": manifest["loaded_credit_constants"]}):
            raise ValueError("loaded engine digest mismatch")
        if len(_json(manifest).encode("utf-8")) > 8 * 1024 * 1024:
            raise ValueError("artifact exceeds size bound")
        return "credit-artifact:" + _hash(manifest)
    except (TypeError, ValueError, RecursionError, UnicodeError) as exc:
        raise CreditArtifactError("credit_artifact_invalid", "invalid credit artifact content") from exc


def assert_current_credit_artifact(manifest):
    """Only compare retained data; never import, compile or run archive code."""
    current = credit_code_artifact()
    if credit_artifact_id(manifest) != credit_artifact_id(current):
        raise CreditArtifactError("credit_replay_engine_mismatch",
            "matching retained credit source, loaded engine and runtime are required")
    return current


def parse_credit_artifact(raw, *, expected_id):
    """Strict retained-data reader. No retained symbol or filename is executed."""
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise CreditArtifactError("credit_artifact_invalid", "duplicate retained artifact key")
            result[key] = value
        return result
    def integer(value):
        if len(value) > 20:
            raise CreditArtifactError("credit_artifact_invalid", "retained metadata integer exceeds bounds")
        return int(value)
    def no_number(value):
        raise CreditArtifactError("credit_artifact_invalid", "non-integer retained metadata")
    try:
        if type(raw) is not str or len(raw.encode("utf-8")) > 8 * 1024 * 1024:
            raise CreditArtifactError("credit_artifact_invalid", "retained artifact text exceeds bounds")
        manifest = json.loads(raw, object_pairs_hook=pairs, parse_int=integer,
                              parse_float=no_number, parse_constant=no_number)
        identity = credit_artifact_id(manifest)
        if type(expected_id) is not str or identity != expected_id or _json(manifest) != raw:
            raise CreditArtifactError("credit_artifact_content_conflict", "retained artifact content identity differs")
        return manifest
    except CreditArtifactError:
        raise
    except (TypeError, ValueError, UnicodeError, RecursionError) as exc:
        raise CreditArtifactError("credit_artifact_invalid", "invalid retained artifact data") from exc
