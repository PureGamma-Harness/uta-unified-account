"""Opt-in full-input pipe framing and post-consumer compact publication.

No application/SQL import. Real adapters are CODE only until separate approval.
"""
import json
import os
from pathlib import Path
import stat

try:
    from tools import managed_observer_report as reports
except ModuleNotFoundError:
    import managed_observer_report as reports

WIRE_SCHEMA = "uta.managed_observer.full-input.v2"
LINE_CAP = 64 * 1024**2
QUEUE_FRAMES = 2


def report_format(plan):
    value = plan["observer"].get("report_format", "legacy")
    if value not in {"legacy", "compact-v2"}:
        raise ValueError("unsupported_observer_report_format")
    if value == "compact-v2" and "output_budget_bytes" not in plan["observer"]:
        raise ValueError("compact_v2_requires_same_scope_explicit_output_budget")
    return value


def input_frame(report, sequence):
    if type(sequence) is not int or not 1 <= sequence <= reports.MAX_COUNTER:
        raise ValueError("input_frame_sequence_required")
    value = {"wire_schema": WIRE_SCHEMA, "sequence": sequence, "report": report,
             "reference_sha256": reports.fingerprint(report)["sha256"]}
    raw = reports.canonical(value) + b"\n"
    if len(raw) > LINE_CAP:
        raise ValueError("full_input_frame_over_budget")
    return raw


class LineBuffer:
    """At most one partial64MiB frame; the caller queues only raw frame bytes."""
    def __init__(self, limit=LINE_CAP):
        if type(limit) is not int or not 1 <= limit <= LINE_CAP:
            raise ValueError("bounded_frame_limit_required")
        self.limit, self.pending = limit, bytearray()

    def feed(self, raw):
        if not isinstance(raw, bytes):
            raise ValueError("wire_bytes_required")
        self.pending.extend(raw)
        while True:
            end = self.pending.find(b"\n")
            if end < 0:
                if len(self.pending) >= self.limit:
                    raise ValueError("full_input_frame_over_budget")
                return
            if end + 1 > self.limit:
                raise ValueError("full_input_frame_over_budget")
            line = bytes(self.pending[:end + 1])
            del self.pending[:end + 1]
            yield line

    def finish(self):
        if self.pending:
            raise ValueError("incomplete_full_input_frame_at_EOF")


class FrameDecoder:
    def __init__(self):
        self.next_sequence = 1

    def decode(self, raw):
        if not isinstance(raw, bytes) or len(raw) > LINE_CAP or not raw.endswith(b"\n"):
            raise ValueError("complete_bounded_input_frame_required")
        value = reports.strict_json(raw)
        if (not isinstance(value, dict) or set(value) != {"wire_schema", "sequence", "report", "reference_sha256"}
                or value["wire_schema"] != WIRE_SCHEMA or type(value["sequence"]) is not int
                or not 1 <= value["sequence"] <= reports.MAX_COUNTER
                or value["sequence"] != self.next_sequence):
            raise ValueError("input_frame_schema_or_sequence_mismatch")
        report = value["report"]
        if not isinstance(report, dict) or "report_schema" in report:
            raise ValueError("full_legacy_input_required")
        if reports.fingerprint(report)["sha256"] != value["reference_sha256"]:
            raise ValueError("full_input_fingerprint_mismatch")
        self.next_sequence += 1
        return report


class DirectoryReceipts:
    """Immutable attempt receipts under the same measured observer output root."""
    def __init__(self, observer_output):
        self.root = Path(observer_output) / "report-v2-publications"
        self.root.mkdir(mode=0o700, exist_ok=True)
        details = self.root.lstat()
        if not stat.S_ISDIR(details.st_mode) or details.st_uid != os.geteuid() or stat.S_IMODE(details.st_mode) != 0o700:
            raise ValueError("private_publication_receipt_directory_required")

    def _path(self, attempt):
        if type(attempt) is not int or not 1 <= attempt <= reports.MAX_COUNTER:
            raise ValueError("publication_attempt_required")
        return self.root / (str(attempt) + ".json")

    def get(self, attempt):
        try:
            descriptor = os.open(self._path(attempt), os.O_RDONLY | os.O_NOFOLLOW)
        except FileNotFoundError:
            return None
        with os.fdopen(descriptor, "rb") as stream:
            details = os.fstat(stream.fileno())
            if (not stat.S_ISREG(details.st_mode) or details.st_uid != os.geteuid()
                    or stat.S_IMODE(details.st_mode) != 0o600 or details.st_size > reports.MAX_REPORT_BYTES):
                raise ValueError("invalid_publication_receipt_file")
            raw = stream.read(reports.MAX_REPORT_BYTES + 1)
            value = reports.strict_json(raw)
            if reports.canonical(value) != raw:
                raise ValueError("noncanonical_publication_receipt")
            return value

    def create(self, attempt, compact):
        raw = reports.canonical(compact)
        if len(raw) > reports.MAX_REPORT_BYTES:
            raise ValueError("publication_receipt_over_budget")
        descriptor = os.open(self._path(attempt), os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(raw)
            stream.flush()
            os.fsync(stream.fileno())
        descriptor = os.open(self.root, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        try:
            os.fsync(descriptor)
        finally:
            os.close(descriptor)


class DirectoryReader:
    """Read an existing private CAS without mkdir, put, cleanup or migration."""
    def __init__(self, observer_output):
        self.directory = Path(observer_output) / "report-v2-nodes"
        details = self.directory.lstat()
        if not stat.S_ISDIR(details.st_mode) or details.st_uid != os.geteuid() or stat.S_IMODE(details.st_mode) != 0o700:
            raise ValueError("existing_private_dependency_directory_required")

    get = reports.DirectoryStore.get


def commit_publication(compact, attempt, receipts, append_timeline, write_latest):
    """Repeated receipt query never reconsumes Coverage or blindly reappends.

    A receipt is durable before derived timeline/latest. Failure after receipt
    commits leaves an index UNKNOWN; replay does not pretend to repair it.
    """
    previous = receipts.get(attempt)
    if previous is not None:
        if reports.canonical(previous) != reports.canonical(compact):
            raise ValueError("publication_attempt_content_conflict")
        return {"receipt_committed": True, "already_existed": True,
                "derived_index_status": "UNKNOWN_NOT_RECHECKED"}
    receipts.create(attempt, compact)
    append_timeline(compact)
    write_latest(compact)
    return {"receipt_committed": True, "already_existed": False,
            "derived_index_status": "COMMITTED_BY_THIS_CALL"}
