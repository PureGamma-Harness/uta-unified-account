"""Independent pure parser/owner-composition boundaries; never runs workloads."""
import ast
from copy import deepcopy
from datetime import datetime, timezone
import gzip
from hashlib import sha256
import json
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory
import time
from types import ModuleType, SimpleNamespace
from unittest.mock import patch

C = "b2175525fa90595c530999f44140e9411421528d"
REPO = Path(__file__).resolve().parents[3]


def main():
    began = time.monotonic_ns()
    started = datetime.now(timezone.utc).isoformat()
    raw = subprocess.check_output(["git", "show", C + ":tools/independent_m0_controller.py"], cwd=REPO)
    tests = subprocess.check_output(["git", "show", "e44493f67846adbdee0ff1064743cd1444c5cb4e:tests/test_independent_m0_controller.py"], cwd=REPO)
    assert sha256(raw).hexdigest() == "df7e8d3dfc9d22a65b197eda5cf1a0469c7e231eb1ee5ab02b03dca2869723db"
    fixture = next(node for cls in ast.parse(tests).body if isinstance(cls, ast.ClassDef)
                   for node in cls.body if isinstance(node, ast.FunctionDef) and node.name == "summary")
    m = ModuleType("fixed_deb3_pure_boundaries")
    m.__file__ = "/synthetic/fixed-control/tools/independent_m0_controller.py"
    forbidden = []
    observations = []

    def prohibited(*args, **kwargs):
        forbidden.append("controller process entry")
        raise AssertionError("native/SQL/workload/Actions prohibited")

    with patch.object(subprocess, "Popen", prohibited), patch.object(subprocess, "run", prohibited), \
            patch.object(subprocess, "check_output", prohibited), patch.object(subprocess, "call", prohibited):
        exec(compile(raw, m.__file__, "exec"), m.__dict__)
        namespace = {"m": m}
        exec(compile(ast.Module(body=[fixture], type_ignores=[]), "original-e444-literal-fixture", "exec"), namespace)
        summary = namespace["summary"](None)
        summary["latency_ms"]["enqueue_ack"] = {key: .003 for key in ("p50", "p95", "p99", "p99_9")}
        rows = []
        for sequence in range(200):
            planned = 1_000_000_000 + sequence * 50_000_000
            outcome = "business_rejected" if sequence % 10 == 0 else "control_or_market_rejected" if sequence % 10 == 1 else "financial_succeeded"
            error = None if outcome == "financial_succeeded" else {"status": 400 if outcome == "business_rejected" else 503, "code": "synthetic-only", "message": "synthetic source-shaped receipt"}
            rows.append(dict(sequence=sequence, command_id=f"bench:{sequence}", order_id=f"order:{sequence}", outcome=outcome,
                             planned_ns=planned, offered_ns=planned + 1000, enqueue_started_ns=planned + 2000,
                             enqueue_ack_ns=planned + 3000, enqueue_call_finished_ns=planned + 4000,
                             observed_completion_ns=planned + 1_000_000, latency_ns=1_000_000,
                             deadline_exceeded=False, intended_product_rejection=sequence % 10 == 0,
                             receipt=dict(command_id=f"bench:{sequence}", attempts=0,
                                          state="SUCCEEDED" if outcome == "financial_succeeded" else "REJECTED",
                                          last_error=None, error=error)))
        with TemporaryDirectory(prefix="m0-independent-pure-boundaries-") as directory:
            root = Path(directory)
            path = root / "rows.jsonl.gz"

            def parse(candidate):
                path.write_bytes(gzip.compress(b"".join((json.dumps(row) + "\n").encode() for row in candidate), mtime=0))
                projected = m.project_arrivals(path)
                m.verify_population(m.project_summary(deepcopy(summary), False), projected)
                return projected

            safe_rows = parse(rows)
            observations.append(dict(case="coherent_error_status_population", status="PASS", red=False))
            for name, value in [("business_label_with503_receipt", {"status": 503, "code": "synthetic-only", "message": "synthetic source-shaped receipt"}),
                                ("control_label_with400_receipt", {"status": 400, "code": "synthetic-only", "message": "synthetic source-shaped receipt"}),
                                ("rejected_receipt_unparseable_error", "SYNTHETIC-NOT-JSON"),
                                ("rejected_receipt_missing_status", {"code": "synthetic-only", "message": "synthetic source-shaped receipt"})]:
                candidate = deepcopy(rows)
                index = 1 if name.startswith("control") else 0
                candidate[index]["receipt"]["error"] = value
                try:
                    parse(candidate)
                    observations.append(dict(case=name, expected="REJECT", observed="ACCEPT", red=True,
                                             original_sequence=index, original_outcome=candidate[index]["outcome"], receipt_error=value))
                except (m.GateError, ValueError, KeyError, TypeError) as error:
                    observations.append(dict(case=name, expected="REJECT", observed="REJECT", red=False,
                                             error_type=type(error).__name__, error_code=str(error)))

            for status, index in [(100, 0), (499, 0), (500, 1), (599, 1)]:
                candidate = deepcopy(rows)
                candidate[index]["receipt"]["error"]["status"] = status
                projected = parse(candidate)
                assert projected[index]["receipt_error_status"] == status
                observations.append(dict(case="legal_status_boundary_" + str(status), status="PASS", red=False))
            candidate = deepcopy(rows)
            for row in candidate:
                if row["receipt"]["error"] is not None:
                    row["receipt"]["error"] = json.dumps(row["receipt"]["error"])
            projected = parse(candidate)
            assert "synthetic-only" not in json.dumps(projected)
            assert "synthetic source-shaped receipt" not in json.dumps(projected)
            observations.append(dict(case="legal_strict_JSON_error_projection_no_code_or_message", status="PASS", red=False))
            for value in [True, 400.0, 99, 600, float("nan"), float("inf")]:
                candidate = deepcopy(rows)
                candidate[0]["receipt"]["error"]["status"] = value
                try:
                    parse(candidate)
                    raise AssertionError("invalid status type/range accepted")
                except m.GateError:
                    observations.append(dict(case="invalid_status_" + repr(value), status="PASS", red=False))
            for value in [{}, {"code": "extra", "message": "extra", "status": 400}]:
                candidate = deepcopy(rows)
                candidate[2]["receipt"]["error"] = value
                try:
                    parse(candidate)
                    raise AssertionError("SUCCEEDED error accepted")
                except m.GateError:
                    observations.append(dict(case="success_error_must_be_None_" + str(len(value)), status="PASS", red=False))
            with patch.object(m.gzip, "decompress", side_effect=AssertionError("bulk decompressor forbidden")):
                parse(rows)
            observations.append(dict(case="no_bulk_gzip_decompress", status="PASS", red=False))
            path.write_bytes(gzip.compress(b"x" * 65537, mtime=0))
            with patch.object(m, "strict_json", side_effect=AssertionError("decoded before line cap")):
                try:
                    m.project_arrivals(path)
                    raise AssertionError("long line accepted")
                except m.GateError as error:
                    assert str(error) == "arrival_count_or_line_cap"
            observations.append(dict(case="line_cap_before_JSON_decode", status="PASS", red=False))
            with gzip.open(path, "wb") as stream:
                for row in rows:
                    stream.write((json.dumps(dict(row, synthetic_padding="x" * 45000)) + "\n").encode())
            try:
                m.project_arrivals(path)
                raise AssertionError("over8MiB accepted")
            except m.GateError as error:
                assert str(error) == "arrival_unpacked_cap"
            observations.append(dict(case="incremental_total8MiB_limit", status="PASS", red=False))

            def exercise_owner(tag, fail_phase=None, too_late=False):
                private = root / (tag + "-private")
                public = root / (tag + "-public")
                private.mkdir(); public.mkdir()
                case = private / "B"; staged = case / "safe-staged"
                active = False; events = []
                actual_write, actual_read, actual_digest = m.public_write, m.read_json, m.digest

                def snapshot(source):
                    assert active; events.append("source-hash")
                    if fail_phase == "hash": raise m.GateError("synthetic_owner_deadline_in_hash")
                    return {}

                def driver(command, source, folder):
                    assert active; events.append("driver-inherited-session")
                    (folder / "workload/profiles").mkdir(parents=True)
                    (folder / "driver.stdout").write_bytes(b"{}\n")
                    (folder / "driver.stderr").write_bytes(b"")
                    return dict(pid=98765, birth_ticks=55, session=98764)

                def arrivals(unused):
                    assert active; events.append("complete-parser")
                    if fail_phase == "parser": raise m.GateError("synthetic_owner_deadline_in_parser")
                    return deepcopy(safe_rows)

                def write(folder, name, value):
                    if active:
                        events.append("fsync:" + name)
                        if fail_phase == "fsync" and name == "arrivals-B.json": raise m.GateError("synthetic_owner_deadline_in_fsync")
                    else:
                        assert name == "context-B.json"
                    return actual_write(folder, name, value)

                def read(file, limit=4 * 1024**2):
                    if Path(file).name == "summary.json": return deepcopy(summary)
                    if Path(file).name == "measurement-footer.json":
                        return dict(timing_contract_version=1, started_monotonic_ns=1_000_000_000,
                                    terminal_observation_finished_monotonic_ns=10_960_000_000,
                                    planned_duration_ns=10_000_000_000, setup_and_close_excluded=True)
                    return actual_read(file, limit)

                def owner(argv, cwd, logs, **kwargs):
                    nonlocal active
                    assert kwargs["wall_seconds"] == 56 and kwargs["grace_seconds"] == kwargs["kill_wait_seconds"] == 2
                    assert "--case-worker" in argv
                    events.append("owner-start"); active = True
                    case.mkdir(); (case / "tmp").mkdir(); staged.mkdir()
                    outcome, code = "EXITED", 0
                    try:
                        result = m.case_pipeline(Path("/synthetic/source"), case, staged, "B", False, {}, [3])
                        staged.rename(public / "case-B-safe"); write(case, "completed.json", result)
                    except m.GateError:
                        outcome, code = "UNKNOWN", -15
                    finally:
                        active = False; events.append("owner-return-cleaned-stub")
                    (private / "case-owner-B.stderr").write_bytes(b"")
                    return dict(outcome=outcome, returncode=code, watchdog_reason=None if code == 0 else "wall_deadline_unknown",
                                leader_reaped=True, stdout_stderr_complete=True, identity=dict(pid=98764, birth_ticks=54))

                owned = SimpleNamespace(owned_run=owner, process_identity=lambda pid: dict(birth_ticks=53))
                with patch.dict(m.os.environ, {"RUNNER_TEMP": str(root)}), patch.object(m, "source_snapshot", snapshot), \
                        patch.object(m, "case_driver", driver), patch.object(m, "project_arrivals", arrivals), \
                        patch.object(m, "public_write", write), patch.object(m, "read_json", read), \
                        patch.object(m, "digest", side_effect=lambda p: "b" * 64 if str(p) == m.__file__ else actual_digest(p)):
                    if too_late:
                        with patch.object(m.time, "monotonic_ns", side_effect=[0, 61_000_000_000, 61_000_000_001]):
                            result = m.supervised_case(owned, Path("/synthetic/source"), private, public, "B", False, {},
                                                       dict(control_commit=C), dict(boot_id="synthetic", hostname_sha256="b" * 64), [3], lambda _: None)
                    else:
                        result = m.supervised_case(owned, Path("/synthetic/source"), private, public, "B", False, {},
                                                   dict(control_commit=C), dict(boot_id="synthetic", hostname_sha256="b" * 64), [3], lambda _: None)
                assert result["status"] == ("PASS" if fail_phase is None and not too_late else "UNKNOWN")
                assert not list(public.iterdir()) if result["status"] == "UNKNOWN" else (public / "case-B-safe/case-B.json").is_file()
                if fail_phase == "fsync": assert (private / "B/safe-staged/case-B.json").is_file()
                if too_late: assert (private / "B/safe-quarantined/case-B.json").is_file()
                observations.append(dict(case=tag, status="PASS", red=False, control_result=result["status"], events=events,
                                         real_PID_cleanup_proven=False, real_processes_started=0))

            exercise_owner("owner_includes_hash_parser_fsync")
            exercise_owner("owner_unknown_hash", "hash")
            exercise_owner("owner_unknown_parser", "parser")
            exercise_owner("owner_unknown_fsync_preserves_first_bytes", "fsync")
            exercise_owner("parent_collection_over60_quarantined", too_late=True)
        assert not forbidden
        assert not any(name == "uta" or name.startswith("uta.") or name == "sqlite3" for name in sys.modules)
    result = dict(control_commit=C, controller_sha256=sha256(raw).hexdigest(), started_at_utc=started,
                  finished_at_utc=datetime.now(timezone.utc).isoformat(), elapsed_monotonic_ns=time.monotonic_ns() - began,
                  cases=observations, red_count=sum(row["red"] for row in observations),
                  controller_process_entry_calls=forbidden, actual_SQL_native_profile_workload_Actions=False,
                  execution_authorized=False, production_approved=False)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 1 if result["red_count"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
