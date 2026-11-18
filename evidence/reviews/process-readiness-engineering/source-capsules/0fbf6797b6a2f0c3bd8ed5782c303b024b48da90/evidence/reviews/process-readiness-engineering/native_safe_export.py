"""Allowlist-only export from private first raw; never edits a raw record."""
from datetime import datetime
import json

from native_once_common import SAFE_EXPORT_CAP, write_new_json


def code(value):
    return (value if isinstance(value, str) and value.isascii() and len(value) <= 80
            and value.replace("_", "").isalnum() else "redacted")


def number(value):
    return value if type(value) is int and 0 <= value < 2**63 else None


def sha(value):
    return (value if isinstance(value, str) and len(value) == 64
            and all(character in "0123456789abcdef" for character in value) else None)


def timestamp(value):
    try:
        parsed = datetime.fromisoformat(value)
        return parsed.isoformat() if parsed.tzinfo is not None else None
    except (ValueError, TypeError):
        return None


def safe_report(report):
    exported = {}
    for name in ("state_observed", "ready", "financial_ready", "supervisor_alive", "workers_alive",
                 "managed", "decision_audit_required"):
        exported[name] = report.get(name) if type(report.get(name)) is bool else None
    exported["reason"] = code(report.get("reason"))
    exported["profile"] = code(report.get("profile"))
    state = report.get("state")
    if isinstance(state, dict):
        exported["state"] = {name: state.get(name) if type(state.get(name)) is bool else None
                             for name in ("halted", "publishing")}
        exported["state"].update(epoch=number(state.get("epoch")), market_version=number(state.get("market_version")),
            market_digest=sha(state.get("market_digest")),
            watermarks={name: number(value) for name, value in state.get("watermarks", {}).items()
                        if name in {"0", "1"}},
            error=None if state.get("error") is None else code(state["error"]))
    else:
        exported["state"] = None
    exported["workers"] = []
    for row in report.get("workers", [])[:2]:
        worker = {name: number(row.get(name)) for name in ("shard", "pid", "owner_pid", "generation", "market_version")}
        worker.update({name: row.get(name) if type(row.get(name)) is bool else None
                       for name in ("alive", "lease_active", "owner_ready", "locally_active",
                                    "market_ready", "funding_registry_ready")})
        worker.update(reason=code(row.get("reason")), market_digest=sha(row.get("market_digest")),
                      market_observed_at=timestamp(row.get("market_observed_at")))
        frame = row.get("report", {})
        worker["report"] = {name: number(frame.get(name)) for name in ("shard", "pid", "generation")}
        worker["report"]["state"] = code(frame.get("state"))
        if "code" in frame:
            worker["report"]["code"] = code(frame["code"])
        if isinstance(row.get("observation_error"), dict):
            detail = row["observation_error"]
            worker["observation_error"] = {"type": code(detail.get("type")),
                "sqlite_errorcode": number(detail.get("sqlite_errorcode"))}
        exported["workers"].append(worker)
    return exported


def export_safe(root):
    path = root / "raw/native.jsonl"
    records, complete, before_quote, before_quote_unknown = [], True, False, False
    calls, completed = set(), set()
    if not path.is_file():
        complete = False
        lines = []
    else:
        lines = path.read_bytes().splitlines(keepends=True)
    for raw in lines:
        if not raw.endswith(b"\n"):
            complete = False
            break
        try:
            record = json.loads(raw)
        except (ValueError, UnicodeError):
            complete = False
            break
        event = record.get("event")
        if event == "activate_before":
            before_quote = record.get("default_quote") is True
        elif event == "original_quote_created":
            before_quote = False
        elif event == "diagnostic_before":
            calls.add(record["call"])
        elif event == "diagnostic_raised":
            completed.add(record["call"])
            complete = False
        elif event == "diagnostic_after":
            completed.add(record["call"])
            report = record["report"]
            unknown = (report.get("reason") == "diagnostic_timeout" or "observation_error" in report
                or any(row.get("reason") in {"diagnostic_timeout", "shard_unavailable", "not_observed"}
                       for row in report.get("workers", [])))
            before_quote_unknown = before_quote_unknown or before_quote and unknown
            records.append({"sequence": number(record.get("sequence")), "call": number(record.get("call")),
                "phase": "before_quote" if before_quote else "later_independent_observation",
                "report": safe_report(report)})
    complete = complete and calls == completed and bool(calls)
    value = {"schema": 1, "journal_complete": complete, "before_quote_unknown": bool(before_quote_unknown),
        "diagnostics": records, "candidate_local_diagnostic_only": True,
        "original_ci_two_failures_unresolved": True}
    write_new_json(root / "safe/diagnostics.json", value, cap=SAFE_EXPORT_CAP)
    return {"journal_complete": complete, "before_quote_unknown": bool(before_quote_unknown)}
