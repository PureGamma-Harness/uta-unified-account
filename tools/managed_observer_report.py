"""Post-coverage report transport; no SQL, observer, process or signing code.

Legacy is the compatibility default. Compact-v2 preserves a reconstructable
complete report and the exact already-consumed coverage observation.
"""
from collections import Counter
from hashlib import sha256
import json
import math
import os
from pathlib import Path
import re
import stat

SCHEMA = "uta.managed_observer.compact.v2"
ARRAY_REF = "$managed_observer_array_v2"
MAX_TREE_DEPTH = 64
MAX_ITEM_BYTES = 2048
MAX_ARRAY_NODE_BYTES = 4096
MAX_NODE_BYTES = 65536
MAX_REPORT_BYTES = 16384
MAX_COUNTER = 2**63 - 1
NODE_DOMAIN = b"uta-managed-observer-report-node-v2\0"
FLAGS = {"continuous_6h_stability_passed": False, "continuous_24h_stability_passed": False,
         "production_approved": False, "capacity_10000_per_s_passed": False}


def _json_domain(value):
    if type(value) in (type(None), bool, int, str):
        return
    if type(value) is float:
        if not math.isfinite(value):
            raise ValueError("finite_json_number_required")
        return
    if type(value) is list:
        for item in value:
            _json_domain(item)
        return
    if type(value) is dict and all(type(key) is str for key in value):
        for item in value.values():
            _json_domain(item)
        return
    raise ValueError("strict_json_types_required")


def canonical(value):
    _json_domain(value)
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()


def strict_json(raw):
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ValueError("duplicate_dependency_json_key")
            result[key] = value
        return result
    def nonfinite(_):
        raise ValueError("finite_json_number_required")
    return json.loads(raw, object_pairs_hook=pairs, parse_constant=nonfinite)


def fingerprint(value):
    """Same canonical bytes as legacy JSON, streamed without a second full copy."""
    _json_domain(value)
    result, size = sha256(), 0
    encoder = json.JSONEncoder(sort_keys=True, separators=(",", ":"), allow_nan=False)
    for part in encoder.iterencode(value):
        raw = part.encode()
        result.update(raw)
        size += len(raw)
    return {"sha256": result.hexdigest(), "canonical_bytes": size}


def node_hash(raw):
    return sha256(NODE_DOMAIN + raw).hexdigest()


def _counter(value):
    if value is None:
        return None
    if type(value) is not int or not 0 <= value <= MAX_COUNTER:
        raise ValueError("bounded_nonnegative_counter_required")
    return value


def _bounded(value, limit):
    if len(canonical(value)) > limit:
        raise ValueError("fixed_schema_field_budget_exceeded")
    return value


class DirectoryStore:
    """Single-writer private immutable nodes; actual filesystem use NOT_RUN.

    An explicit separate directory is required. Existing pending files are
    retained and counted, never silently removed as recovery. No GC is implied.
    """
    def __init__(self, observer_output, *, max_bytes=256 * 1024**2):
        output = Path(observer_output)
        details = output.lstat()
        if not stat.S_ISDIR(details.st_mode) or details.st_uid != os.geteuid() or stat.S_IMODE(details.st_mode) != 0o700:
            raise ValueError("existing_private_observer_output_required")
        # Always under aggregate observer output; never an excluded clone path.
        self.directory = output / "report-v2-nodes"
        self.directory.mkdir(mode=0o700, exist_ok=True)
        details = self.directory.lstat()
        if not stat.S_ISDIR(details.st_mode) or details.st_uid != os.geteuid() or stat.S_IMODE(details.st_mode) != 0o700:
            raise ValueError("private_owned_node_directory_required")
        self.max_bytes, self.used_bytes = _counter(max_bytes), 0
        for entry in self.directory.iterdir():
            details = entry.lstat()
            if (not re.fullmatch(r"[0-9a-f]{64}\.(json|pending)", entry.name)
                    or not stat.S_ISREG(details.st_mode) or details.st_uid != os.geteuid()
                    or stat.S_IMODE(details.st_mode) != 0o600):
                raise ValueError("unexpected_private_store_entry")
            self.used_bytes += details.st_size
        if self.max_bytes is None or self.used_bytes > self.max_bytes:
            raise ValueError("dependency_store_budget_exceeded")

    def get(self, identity):
        if not isinstance(identity, str) or not re.fullmatch(r"[0-9a-f]{64}", identity):
            raise ValueError("node_identity_required")
        descriptor = os.open(self.directory / (identity + ".json"), os.O_RDONLY | os.O_NOFOLLOW)
        with os.fdopen(descriptor, "rb") as stream:
            details = os.fstat(stream.fileno())
            if (not stat.S_ISREG(details.st_mode) or details.st_uid != os.geteuid()
                    or stat.S_IMODE(details.st_mode) != 0o600 or details.st_size > MAX_NODE_BYTES):
                raise ValueError("invalid_private_dependency_file")
            return stream.read(MAX_NODE_BYTES + 1)

    def put(self, identity, raw):
        if not isinstance(raw, bytes) or len(raw) > MAX_NODE_BYTES or node_hash(raw) != identity:
            raise ValueError("invalid_dependency_node")
        try:
            existing = self.get(identity)
        except FileNotFoundError:
            existing = None
        if existing is not None:
            if existing != raw:
                raise ValueError("existing_dependency_changed")
            return
        if self.used_bytes + len(raw) > self.max_bytes:
            raise ValueError("dependency_store_budget_exceeded")
        pending = self.directory / (identity + ".pending")
        descriptor = os.open(pending, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
        with os.fdopen(descriptor, "wb") as stream:
            self.used_bytes += len(raw)  # Conservatively charged even if write fails.
            stream.write(raw)
            stream.flush()
            os.fsync(stream.fileno())
        os.link(pending, self.directory / (identity + ".json"), follow_symlinks=False)
        pending.unlink()
        descriptor = os.open(self.directory, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        try:
            os.fsync(descriptor)
        finally:
            os.close(descriptor)


def _put(store, value):
    raw = canonical(value)
    limit = MAX_ARRAY_NODE_BYTES if isinstance(value, dict) and value.get("kind") == "array_item" else MAX_NODE_BYTES
    if len(raw) > limit:
        raise ValueError("dependency_node_budget_exceeded")
    identity = node_hash(raw)
    store.put(identity, raw)
    return identity


def _read(store, identity):
    if not isinstance(identity, str) or not re.fullmatch(r"[0-9a-f]{64}", identity):
        raise ValueError("node_identity_required")
    raw = store.get(identity)
    if not isinstance(raw, bytes) or len(raw) > MAX_NODE_BYTES or node_hash(raw) != identity:
        raise ValueError("dependency_hash_or_size_mismatch")
    value = strict_json(raw)
    if canonical(value) != raw:
        raise ValueError("noncanonical_dependency")
    return value


def _anchor(value):
    if isinstance(value, dict):
        for keys in (("shard", "sequence", "command_id"), ("sequence", "command_id"),
                     ("round", "kind"), ("owner", "asset"), ("account", "asset"), ("account", "symbol")):
            if all(key in value for key in keys):
                return [list(keys), [value[key] for key in keys]]
    return ["canonical_value", value]


def _encode(value, store):
    if isinstance(value, list):
        # Cartesian tree: input order is in-order; anchor-derived priority is
        # independent of position and mutable state. Prefix insertion cannot
        # shift every later record's grouping as positional chunks would.
        stack, occurrences = [], Counter()
        for item in value:
            if len(canonical(item)) > MAX_ITEM_BYTES:
                raise ValueError("array_record_budget_exceeded")
            anchor = canonical(_anchor(item))
            occurrence = occurrences[anchor]
            occurrences[anchor] += 1
            priority = sha256(b"observer-array-anchor-v2\0" + anchor + b"\0" + str(occurrence).encode()).hexdigest()
            node = {"value": item, "anchor": priority, "left": None, "right": None}
            last = None
            while stack and priority < stack[-1]["anchor"]:
                last = stack.pop()
            node["left"] = last
            if stack:
                stack[-1]["right"] = node
            stack.append(node)

        def persist(node, depth):
            if node is None:
                return None, 0
            if depth > MAX_TREE_DEPTH:
                raise ValueError("array_tree_depth_budget_exceeded")
            left, left_count = persist(node["left"], depth + 1)
            right, right_count = persist(node["right"], depth + 1)
            count = left_count + 1 + right_count
            identity = _put(store, {"kind": "array_item", "version": 2,
                "anchor": node["anchor"], "value": node["value"],
                "left": left, "right": right, "count": count})
            return identity, count

        identity, count = persist(stack[0] if stack else None, 1)
        return {ARRAY_REF: {"root": identity, "count": _counter(count)}}
    if isinstance(value, dict):
        if ARRAY_REF in value:
            raise ValueError("reserved_dependency_marker_in_reference")
        return {key: _encode(item, store) for key, item in value.items()}
    return value


def _decode(value, store, budget):
    if isinstance(value, dict) and ARRAY_REF in value:
        if set(value) != {ARRAY_REF} or set(value[ARRAY_REF]) != {"root", "count"}:
            raise ValueError("invalid_array_reference")
        reference = value[ARRAY_REF]
        result = _array(reference["root"], store, budget, 1)
        if _counter(reference["count"]) != len(result):
            raise ValueError("array_reference_count_mismatch")
        return result
    if isinstance(value, dict):
        return {key: _decode(item, store, budget) for key, item in value.items()}
    return value


def _array(identity, store, budget, depth):
    if identity is None:
        return []
    if depth > MAX_TREE_DEPTH:
        raise ValueError("array_tree_depth_budget_exceeded")
    budget[0] -= 1
    if budget[0] < 0:
        raise ValueError("reconstruction_node_budget_exceeded")
    node = _read(store, identity)
    if type(node.get("version")) is not int or node["version"] != 2:
        raise ValueError("dependency_version_mismatch")
    if (node.get("kind") == "array_item"
            and set(node) == {"kind", "version", "anchor", "value", "left", "right", "count"}
            and isinstance(node["anchor"], str) and re.fullmatch(r"[0-9a-f]{64}", node["anchor"])):
        if len(canonical(node)) > MAX_ARRAY_NODE_BYTES or len(canonical(node["value"])) > MAX_ITEM_BYTES:
            raise ValueError("array_record_or_node_budget_exceeded")
        left = _array(node["left"], store, budget, depth + 1)
        left.append(node["value"])
        left.extend(_array(node["right"], store, budget, depth + 1))
        if _counter(node["count"]) != len(left):
            raise ValueError("array_branch_count_mismatch")
        return left
    raise ValueError("invalid_array_node")


def _inventory(rows, categories):
    if rows is None:
        return None
    if not isinstance(rows, list):
        raise ValueError("complete_list_required")
    result = {"total": _counter(len(rows))}
    for field, permitted in categories.items():
        counts = Counter(row.get(field) if row.get(field) in permitted else "OTHER" for row in rows)
        result[field + "_counts"] = {key: _counter(counts[key]) for key in (*permitted, "OTHER")}
    return result


def _summary(report):
    finance = report.get("finance")
    if finance is not None and (not isinstance(finance, dict) or not isinstance(finance.get("command_inbox"), list)):
        raise ValueError("full_finance_command_list_required")
    commands = None if finance is None else finance["command_inbox"]
    command_summary = _inventory(commands, {"state": ("PENDING", "SUCCEEDED", "REJECTED", "QUARANTINED"),
        "kind": ("SUBMIT_ORDER", "CANCEL_ORDER", "REPAY", "PUBLISH_MARKET", "SET_HALT")})
    if commands is not None:
        command_summary.update(control_commands=sum(item.get("control_lane") is True for item in commands),
            account_commands=sum(item.get("control_lane") is False for item in commands))
    return {"logical_point": _bounded(report.get("logical_point"), 80),
        "completed_rounds": _counter(report.get("completed_rounds")),
        "active_round_count": None if "active_rounds" not in report else _counter(len(report["active_rounds"])),
        "unresolved_steps": _counter(report.get("unresolved_steps")),
        "unresolved_faults": _counter(report.get("unresolved_faults")),
        "commands": command_summary,
        "faults": _inventory(report.get("planned_faults"), {"state": ("PLANNED", "DONE"), "kind": ("worker", "parent")}),
        "financial_counts": None if finance is None else _bounded(finance.get("counts"), 2048),
        "financial_watermark": None if finance is None else _bounded(finance.get("watermark"), 512),
        "golden": None if finance is None else _bounded(finance.get("golden"), 4096),
        "retry_alert_count": None if finance is None else _counter(len(finance.get("retry_alerts", []))),
        "alerts": _bounded(report.get("alerts", []), 2048),
        "final_evidence_eligible": report.get("final_evidence_eligible") is True,
        "final_reconciliation": _bounded({key: report.get("final_reconciliation", {}).get(key)
            for key in ("eligible", "errors")}, 2048)}


def consume_and_format(report, consume_full, *, job_elapsed_seconds, sample_attempt_id,
                       report_format="legacy", store=None):
    """Consume complete legacy proof first; format only after that exact call.

    The callback must finish all full-report consumers, including known-fatal
    safety actions before output writes. It preserves classify_safely policy;
    this formatter must not replace it with a new classification algorithm.
    A failed export must not be retried through coverage with the same attempt.
    Persist/query its deterministic dependency identity; do not double count.
    """
    if report_format not in {"legacy", "compact-v2"}:
        raise ValueError("unsupported_report_format")
    if not isinstance(report, dict) or "report_schema" in report:
        raise ValueError("complete_legacy_reference_required")
    if not callable(consume_full):
        raise ValueError("explicit_complete_consumer_callback_required")
    if report_format == "compact-v2" and store is None:
        raise ValueError("bounded_dependency_store_required")
    # All original coverage predicates receive all rows. No projection above.
    observed = consume_full(report, job_elapsed_seconds=job_elapsed_seconds,
                            sample_attempt_id=sample_attempt_id)
    if report_format == "legacy":
        return report
    summary = _summary(report)
    full = fingerprint(report)
    reference = _put(store, {"kind": "full_reference", "version": 2,
                             "value": _encode(report, store)})
    publication = {"report_schema": SCHEMA, "report_version": 2,
        "synthetic": True, "redacted": True, "observation_only": True,
        "observer_is_formal_signoff": False, "requires_full_report_for_verification": True,
        "financial_ready": "unknown_independent_observer_has_no_readiness_authority",
        "full_reference": {"root": reference, **full}, "summary": summary,
        "coverage_observation": _bounded(observed, 2048), **FLAGS}
    identity = _put(store, publication)
    compact = {**publication, "publication_sha256": identity}
    if len(canonical(compact)) > MAX_REPORT_BYTES:
        raise ValueError("compact_report_budget_exceeded")
    return compact


def restore(compact, store, *, max_nodes=100000, max_reference_bytes=256 * 1024**2):
    """Query complete original proof; verify every dependency and visible field."""
    if (not isinstance(compact, dict) or compact.get("report_schema") != SCHEMA
            or type(compact.get("report_version")) is not int or compact["report_version"] != 2):
        raise ValueError("unsupported_report_schema")
    if len(canonical(compact)) > MAX_REPORT_BYTES:
        raise ValueError("compact_report_budget_exceeded")
    publication = _read(store, compact["publication_sha256"])
    if canonical(publication) != canonical({key: value for key, value in compact.items() if key != "publication_sha256"}):
        raise ValueError("published_summary_or_receipt_changed")
    reference = publication["full_reference"]
    if type(reference["canonical_bytes"]) is not int or not 0 <= reference["canonical_bytes"] <= max_reference_bytes:
        raise ValueError("reference_reconstruction_byte_budget_exceeded")
    root = _read(store, reference["root"])
    if (set(root) != {"kind", "version", "value"} or root["kind"] != "full_reference"
            or type(root["version"]) is not int or root["version"] != 2):
        raise ValueError("invalid_full_reference")
    full = _decode(root["value"], store, [_counter(max_nodes)])
    if fingerprint(full) != {key: reference[key] for key in ("sha256", "canonical_bytes")}:
        raise ValueError("complete_reference_fingerprint_mismatch")
    if canonical(_summary(full)) != canonical(publication["summary"]):
        raise ValueError("reference_summary_mismatch")
    return full
