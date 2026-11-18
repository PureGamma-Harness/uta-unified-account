"""Read-only JSON aggregation after two separately authorized target processes.

This file imports neither UTA nor SQLite. It never opens a database. The target
reports remain in their original directories; only a new derived report is made.
"""
import os
import sys
from time import monotonic

STARTED = monotonic()
DEADLINE = STARTED + 10
RAW_CAP = 16 * 1024
RAW_RESERVE = 512
RAW_RESERVED = 0
RAW_FAILED = False


def abort_raw():
    global RAW_FAILED
    RAW_FAILED = True
    try:
        os.write(2, b'{"event":"AGGREGATE_RAW_ABORT","exit_status":125}\n')
    except BaseException:
        pass
    os._exit(125)


class Raw:
    encoding, errors = "utf-8", "backslashreplace"

    def __init__(self, descriptor):
        self.descriptor = descriptor

    def write(self, text):
        global RAW_RESERVED
        if type(text) is not str:
            raise TypeError("raw output requires text")
        data = text.encode(self.encoding, self.errors)
        if RAW_FAILED or len(data) > RAW_CAP - RAW_RESERVE - RAW_RESERVED:
            abort_raw()
        RAW_RESERVED += len(data)
        try:
            remaining = memoryview(data)
            while remaining:
                count = os.write(self.descriptor, remaining)
                if type(count) is not int or not 0 < count <= len(remaining):
                    abort_raw()
                remaining = remaining[count:]
        except BaseException:
            abort_raw()
        return len(text)

    def flush(self):
        if RAW_FAILED:
            os._exit(125)


def deadline(frame, event, argument):
    if monotonic() >= DEADLINE:
        os._exit(124)
    return deadline


import argparse
from hashlib import sha256
import json
from pathlib import Path
import stat
import traceback


def require(value, message):
    if not value:
        raise ValueError(message)


def unique(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate report key")
        result[key] = value
    return result


def reject_constant(value):
    raise ValueError("nonfinite JSON report")


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False).encode()


def stable_bytes(path):
    require(path.is_absolute() and path.resolve() == path, "noncanonical report path")
    before = path.lstat()
    require(stat.S_ISREG(before.st_mode) and before.st_size <= 4 * 1024 * 1024, "report is not bounded regular data")
    descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | getattr(os, "O_NOATIME", 0))
    try:
        opened = os.fstat(descriptor)
        require((opened.st_dev, opened.st_ino, opened.st_size) == (before.st_dev, before.st_ino, before.st_size),
                "report changed before opening")
        data = bytearray()
        while True:
            piece = os.read(descriptor, 131072)
            if not piece:
                break
            data.extend(piece)
            require(len(data) <= 4 * 1024 * 1024, "report grew beyond cap")
        after = os.fstat(descriptor)
    finally:
        os.close(descriptor)
    keys = ("st_dev", "st_ino", "st_size", "st_mtime_ns", "st_ctime_ns")
    require(tuple(getattr(before, key) for key in keys) == tuple(getattr(after, key) for key in keys)
            and len(data) == before.st_size, "report changed while reading")
    return bytes(data)


def load(path):
    raw = stable_bytes(path)
    value = json.loads(raw, object_pairs_hook=unique, parse_constant=reject_constant)
    require(type(value) is dict, "report root is not an object")
    return raw, value


def outside(path, root):
    try:
        path.relative_to(root)
        return False
    except ValueError:
        return True


def target(root, host_receipt, other_root, expected_set, expected_control):
    require(root.is_absolute() and root.parent == Path("/workspace") and root.resolve() == root,
            "target must be the declared direct fresh run namespace")
    inventory_raw, inventory = load(root / "reports/inventory.json")
    result_raw, result = load(root / "reports/result.json")
    pin = inventory["files"]["reports/result.json"]
    require(pin["bytes"] == len(result_raw) and pin["sha256"] == sha256(result_raw).hexdigest(), "result digest mismatch")
    require(result["source_commit"] == expected_control and result["profile_set"] == expected_set
            and result["source_unchanged"] is True and result["all_functional_checks_passed"] is True
            and result["production_approved"] is False and result["forbidden_imports"] == []
            and result["status"] == "LOCAL_MATCHING_COMPONENT_PROFILE_PASS_PENDING_INDEPENDENT_REVIEW",
            "incomplete or mismatched target result")
    require(host_receipt.is_absolute() and outside(host_receipt, root) and outside(host_receipt, other_root),
            "host receipt must be outside both target-write namespaces")
    host_raw, host = load(host_receipt)
    require(host.get("kind") == "ROOT_HOST_COMPLETION_RECEIPT"
            and host.get("source_commit") == expected_control and host.get("profile_set") == expected_set
            and host.get("actual_exit_status") == 0 and type(host.get("actual_exit_status")) is int
            and host.get("process_completion_observed") is True and host.get("raw_capture_complete") is True,
            "missing actual host exit/completion; inner status cannot replace it")
    require(host.get("result") == {"bytes": len(result_raw), "sha256": sha256(result_raw).hexdigest()}
            and host.get("manifest_sha256") == result["manifest_sha256"], "host result/manifest binding differs")
    expected_argv = [result["runtime_descriptor"]["python_executable"]["resolved_path"], "-I", "-S", "-B",
        str(Path(__file__).resolve().with_name("matching_profile_once.py")), "--profile-set", expected_set,
        "--run-root", str(root), "--source-commit", expected_control,
        "--approved-manifest-sha256", result["manifest_sha256"]]
    require(host.get("argv") == expected_argv and all(type(value) is str for value in host["argv"]),
            "host argv differs from the frozen control/runtime invocation")
    raw_total, stdout = 0, None
    for channel in ("stdout", "stderr"):
        pin = host.get(channel)
        require(type(pin) is dict and type(pin.get("path")) is str, "host raw descriptor missing")
        path = Path(pin["path"])
        require(outside(path, root) and outside(path, other_root), "raw capture must be a separate host artifact")
        raw = stable_bytes(path)
        require(type(pin.get("bytes")) is int and pin["bytes"] == len(raw)
                and pin.get("sha256") == sha256(raw).hexdigest(), "host raw capture digest differs")
        raw_total += len(raw)
        if channel == "stdout":
            stdout = raw
    require(raw_total <= (320 if expected_set == "current" else 176) * 1024, "target raw capture cap exceeded")
    frames = [json.loads(line, object_pairs_hook=unique, parse_constant=reject_constant)
              for line in stdout.decode("utf-8").splitlines() if line.strip()]
    require(frames and all(type(value) is dict for value in frames)
            and frames[0].get("event") == "BEGIN_MATCHING_PROFILE_ONCE"
            and frames[0].get("source_commit") == expected_control
            and frames[0].get("manifest_sha256") == result["manifest_sha256"]
            and frames[-1].get("event") == "END_MATCHING_PROFILE_ONCE"
            and frames[-1].get("profile_set") == expected_set
            and frames[-1].get("source_unchanged") is True
            and frames[-1].get("exit_status") == 0 and type(frames[-1].get("exit_status")) is int,
            "missing complete target BEGIN/END evidence")
    events = [value.get("event") for value in frames]
    require(events.count("BEGIN_MATCHING_PROFILE_ONCE") == events.count("END_MATCHING_PROFILE_ONCE") == 1
            and all(value in {"BEGIN_MATCHING_PROFILE_ONCE", "MATCHING_PROFILE_CHECKPOINT", "END_MATCHING_PROFILE_ONCE"}
                    for value in events)
            and type(result.get("checkpoints")) is int
            and events.count("MATCHING_PROFILE_CHECKPOINT") == result["checkpoints"],
            "duplicate/truncated/unknown target stream frame")
    require(type(result["driver_elapsed_seconds"]) in (int, float)
            and result["driver_elapsed_seconds"] <= (60 if expected_set == "current" else 45), "target late")
    loaded = {}
    for size in (32, 128):
        modes = ("scan", "snapshot") if expected_set == "current" else ("original-scan",)
        for mode in modes:
            name = "reports/profile-" + str(size) + "-" + mode + ".json"
            raw, report = load(root / name)
            pin = inventory["files"][name]
            require(pin["bytes"] == len(raw) and pin["sha256"] == sha256(raw).hexdigest(), "sample digest mismatch")
            require(report["book_size"] == size and report["mode"] == mode
                    and report["matching"]["confirmed_matches"] == 8
                    and report["matching"]["paired_fills"] == 16
                    and report["production_approved"] is False, "sample shape mismatch")
            loaded[(size, mode)] = (raw, report)
    return result, loaded, {"host_completion": {"bytes": len(host_raw), "sha256": sha256(host_raw).hexdigest()},
                            "result": {"bytes": len(result_raw), "sha256": sha256(result_raw).hexdigest()},
                            "inventory": {"bytes": len(inventory_raw), "sha256": sha256(inventory_raw).hexdigest()}}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--control-source-commit", required=True)
    parser.add_argument("--current-root", type=Path, required=True)
    parser.add_argument("--original-root", type=Path, required=True)
    parser.add_argument("--current-host-receipt", type=Path, required=True)
    parser.add_argument("--original-host-receipt", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    args = parser.parse_args()
    require(len(args.control_source_commit) == 40 and all(c in "0123456789abcdef" for c in args.control_source_commit),
            "invalid control source label")
    os.umask(0o077)
    os.sched_setaffinity(0, {min(os.sched_getaffinity(0))})
    current, new_reports, current_pins = target(args.current_root, args.current_host_receipt, args.original_root,
                                              "current", args.control_source_commit)
    original, old_reports, old_pins = target(args.original_root, args.original_host_receipt, args.current_root,
                                           "original-scan", args.control_source_commit)
    require(current["runtime_descriptor"] == original["runtime_descriptor"], "target runtimes differ")
    require(current["target_runtime_commit"] == "a2434bdfe711ead1d202f6c1527e527f73e2dfa2"
            and original["target_runtime_commit"] == "9b61e5f35dd2196ef2fdddfa03559eca3f1322ec", "runtime source target differs")
    comparisons, report_pins = [], {}
    for size in (32, 128):
        new_scan = new_reports[(size, "scan")][1]
        snapshot = new_reports[(size, "snapshot")][1]
        old_scan = old_reports[(size, "original-scan")][1]
        for value in (snapshot, old_scan):
            require(canonical(new_scan["verification"]["after_reopen"]["economic_projection"])
                    == canonical(value["verification"]["after_reopen"]["economic_projection"]), "financial difference in paired source comparison")
            require(canonical(new_scan["verification"]["after_reopen"]["risks"])
                    == canonical(value["verification"]["after_reopen"]["risks"]), "risk difference in paired source comparison")
        times = {"current_scan": new_scan["matching"]["wall_ns_including_commit_and_observer"],
                 "snapshot": snapshot["matching"]["wall_ns_including_commit_and_observer"],
                 "original_scan": old_scan["matching"]["wall_ns_including_commit_and_observer"]}
        require(all(type(value) is int and value > 0 for value in times.values()), "timing is not measured positive ns")
        comparisons.append({"book_size": size, "financial_and_risk_exact": True, "matching_wall_ns": times,
            "observed_snapshot_over_current_scan_ratio": times["snapshot"] / times["current_scan"],
            "observed_current_scan_over_original_scan_ratio": times["current_scan"] / times["original_scan"],
            "single_profiled_observation_not_significance_or_acceptance": True})
    for group in (new_reports, old_reports):
        for (size, mode), (raw, report) in group.items():
            report_pins[str(size) + "-" + mode] = {"bytes": len(raw), "sha256": sha256(raw).hexdigest()}
    output = args.output_root
    require(output.is_absolute() and output.parent == Path("/workspace") and not output.exists()
            and not output.is_symlink(), "output must be a new direct namespace")
    result = {"kind": "DERIVED_MATCHING_COMPONENT_PROFILE_SOURCE_COMPARISON", "source_commit": args.control_source_commit,
        "current_target_pins": current_pins, "original_target_pins": old_pins, "source_report_pins": report_pins,
        "comparisons": comparisons, "runtime_descriptor": current["runtime_descriptor"],
        "actual_affinity": sorted(os.sched_getaffinity(0)), "aggregate_elapsed_seconds": monotonic() - STARTED,
        "sum_target_driver_seconds": current["driver_elapsed_seconds"] + original["driver_elapsed_seconds"],
        "overall_outer_lifecycle_seconds": None, "outer_lifecycle_status": "ROOT_HOST_RECORD_REQUIRED_NOT_DERIVED_FROM_TARGETS",
        "component_only": True, "no_SQL_or_database_open": True, "no_new_target_execution": True,
        "default_scan_regression_accepted": False, "throughput_capacity_accepted": False,
        "statistical_significance_claimed": False, "production_approved": False}
    raw = json.dumps(result, sort_keys=True, ensure_ascii=True, indent=2, allow_nan=False).encode() + b"\n"
    require(len(raw) <= 8 * 1024 * 1024 and monotonic() < DEADLINE, "aggregate budget exhausted")
    output.mkdir(mode=0o700)
    descriptor = os.open(output / "comparison.json", os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    try:
        remaining = memoryview(raw)
        while remaining:
            count = os.write(descriptor, remaining)
            require(type(count) is int and 0 < count <= len(remaining), "short aggregate report write")
            remaining = remaining[count:]
        os.fsync(descriptor)
    finally:
        os.close(descriptor)
    require(monotonic() < DEADLINE, "aggregate completed late; not a valid sample")
    print(json.dumps({"event": "END_MATCHING_PROFILE_AGGREGATE", "bytes": len(raw),
          "sha256": sha256(raw).hexdigest(), "exit_status": 0, "profile_does_not_grant_production": True}), flush=True)
    return 0


def script_entry():
    sys.stdout = sys.__stdout__ = Raw(1)
    sys.stderr = sys.__stderr__ = Raw(2)
    sys.settrace(deadline)
    try:
        return main()
    except SystemExit as error:
        return error.code if type(error.code) is int else 1
    except BaseException:
        traceback.print_exc()
        return 1
    finally:
        sys.settrace(None)


if __name__ == "__main__":
    raise SystemExit(script_entry())
