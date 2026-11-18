"""Prepare a fresh scope, or run it only after separate reviewed final GO.

This file has not been executed. Neither a CLI flag nor a self-written
preflight record supplies authorization to start the native case.
"""
import argparse
import ctypes
import json
import os
from pathlib import Path
import resource
import selectors
import shutil
import signal
import stat
import subprocess
import sys
from time import monotonic, sleep

sys.path.insert(0, str(Path(__file__).resolve().parent))
from native_once_common import (BIRTH_FIELDS, BoundChild, CONTROL_JOURNAL_CAP, DATA_CAP, Journal,
    LOG_CAP, PROTECTED_PIDS, SELECTOR, STDIO_CAP, ScopeUnknown, binary_info,
    children_of, digest, identity, require_before, require_unprotected_pid,
    same_birth, tree_bytes, verify_sources, write_new_json)

HERE = Path(__file__).resolve().parent
SOURCE = HERE.parents[2]
MANIFEST_RELATIVE = "evidence/reviews/process-readiness-engineering/native-source-manifest.json"


def reconcile_owned_roles(case_result, leader_birth, observed_births):
    """Compare roles with bound descendants; never grants new PID access."""
    if (not isinstance(case_result, dict) or not isinstance(case_result.get("owned_processes"), list)
            or case_result.get("remaining_direct_children") != []
            or case_result.get("helper_cleanup_proven") is not True):
        return False
    declared, workers, helpers = {}, 0, 0
    for item in case_result["owned_processes"]:
        if not isinstance(item, dict) or not isinstance(item.get("birth"), dict):
            return False
        birth = item["birth"]
        if (any(key not in birth for key in BIRTH_FIELDS)
                or any(type(birth[key]) is not int for key in ("pid", "start_ticks", "uid", "session"))
                or birth["pid"] <= 0 or birth["pid"] in PROTECTED_PIDS
                or not isinstance(birth["boot_id"], str) or not birth["boot_id"]
                or birth["session"] != leader_birth["session"] or birth["uid"] != leader_birth["uid"]
                or birth.get("ppid") != leader_birth["pid"]
                or item.get("terminal") is not True or item.get("reaped") is not True):
            return False
        key = tuple(birth[field] for field in BIRTH_FIELDS)
        if key in declared:
            return False
        declared[key] = item
        if item.get("role") == "financial_worker" and item.get("name") in {"uta-shard-0", "uta-shard-1"}:
            workers += 1
        elif item.get("role") == "multiprocessing.resource_tracker" and type(item.get("wait_status")) is int and item["wait_status"] == 0:
            helpers += 1
        else:
            return False
    if helpers != (1 if workers else 0):
        return False
    for birth in observed_births:
        if not same_birth(birth, leader_birth) and tuple(birth[field] for field in BIRTH_FIELDS) not in declared:
            return False
    # A short-lived child may have been joined by its original parent between
    # controller samples. Its own bound terminal + kernel no-child evidence is
    # independently checked against the full native journal by export_safe.
    return True


def private_directory(path):
    details = path.stat(follow_symlinks=False)
    if (not stat.S_ISDIR(details.st_mode) or details.st_uid != os.geteuid()
            or stat.S_IMODE(details.st_mode) != 0o700):
        raise ScopeUnknown("run_root_is_not_owned_private_directory")


def available_resources(path):
    result = {"disk_free_bytes": shutil.disk_usage(path).free,
              "physical_available_bytes": os.sysconf("SC_AVPHYS_PAGES") * os.sysconf("SC_PAGE_SIZE"),
              "rlimit_nofile": list(resource.getrlimit(resource.RLIMIT_NOFILE)),
              "cpu_affinity": sorted(os.sched_getaffinity(0))}
    for name in ("memory.current", "memory.max", "pids.current", "pids.max"):
        candidate = Path("/sys/fs/cgroup") / name
        result[name] = candidate.read_text().strip() if candidate.is_file() else None
    if result["disk_free_bytes"] < 128 * 1024 * 1024:
        raise ScopeUnknown("disk_headroom_below_128MiB")
    if result["physical_available_bytes"] < 384 * 1024 * 1024:
        raise ScopeUnknown("memory_headroom_below_384MiB")
    if result["memory.max"] not in (None, "max") and result["memory.current"] is not None:
        if int(result["memory.max"]) - int(result["memory.current"]) < 384 * 1024 * 1024:
            raise ScopeUnknown("cgroup_memory_headroom_below_384MiB")
    if result["pids.max"] not in (None, "max") and result["pids.current"] is not None:
        if int(result["pids.max"]) - int(result["pids.current"]) < 12:
            raise ScopeUnknown("cgroup_pid_headroom_below_12")
    return result


def preflight(args):
    # This mode is separately scoped metadata/file preparation, never a test.
    os.umask(0o077)
    allowed_affinity = os.sched_getaffinity(0)
    os.sched_setaffinity(0, {min(allowed_affinity)})
    if sys.platform != "linux" or not hasattr(os, "pidfd_open") or not hasattr(signal, "pidfd_send_signal"):
        raise ScopeUnknown("required_linux_pidfd_capability_missing")
    if children_of(os.getpid()):
        raise ScopeUnknown("preflight_interpreter_already_has_children")
    own = identity(os.getpid())
    require_unprotected_pid(os.getpid())
    own_pidfd = os.pidfd_open(os.getpid())
    os.close(own_pidfd)  # Exercise only this metadata interpreter's pidfd capability.
    root = Path(args.run_root)
    if not root.is_absolute() or root.exists():
        raise ScopeUnknown("preflight_requires_new_absolute_directory")
    resources = available_resources(root.parent)
    manifest = json.loads((SOURCE / MANIFEST_RELATIVE).read_text())
    pins = verify_sources(SOURCE, manifest)
    source_bytes = sum((SOURCE / relative).stat().st_size for relative in pins)
    if source_bytes > 8 * 1024 * 1024:
        raise ScopeUnknown("source_snapshot_exceeds_8MiB")
    root.mkdir(mode=0o700)
    for name in ("source", "raw", "safe", "business", "empty-pycache"):
        (root / name).mkdir(mode=0o700)
    for relative in [*pins, MANIFEST_RELATIVE]:
        target = root / "source" / relative
        target.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        fd = os.open(target, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o400)
        try:
            data = (SOURCE / relative).read_bytes()
            while data:
                written = os.write(fd, data)
                if written <= 0:
                    raise ScopeUnknown("snapshot_short_write")
                data = data[written:]
            os.fsync(fd)
        finally:
            os.close(fd)
    snapshot = root / "source"
    verify_sources(snapshot, manifest)
    for directory in sorted((path for path in snapshot.rglob("*") if path.is_dir()),
                            key=lambda path: len(path.parts), reverse=True):
        directory.chmod(0o500)
    snapshot.chmod(0o500)
    binary = binary_info()
    value = {"status": "PREFLIGHT_ONLY_NO_NATIVE_GO", "source_commit": args.source_commit,
        "manifest_sha256": digest(SOURCE / MANIFEST_RELATIVE), "sources_sha256": pins,
        "binary": binary, "preflight_birth": own, "resources": resources,
        "selected_cpu": min(resources["cpu_affinity"]), "source_snapshot_bytes": source_bytes,
        "affinity_before_pinning": sorted(allowed_affinity),
        "selector": SELECTOR, "protected_pids": sorted(PROTECTED_PIDS),
        "original_ci_python": "3.12.16", "local_runtime_is_new_diagnostic_not_cause_reproduction": True,
        "native_case_started": False, "sql_connections_or_statements": 0,
        "data_cap_bytes": DATA_CAP, "log_cap_bytes": LOG_CAP,
        "outer_wall_seconds": 45, "case_window_seconds": 30,
        "term_deadline_seconds": 35, "kill_reap_deadline_seconds": 40}
    write_new_json(root / "preflight.json", value)
    print(json.dumps({"status": value["status"], "run_root": str(root),
        "preflight_sha256": digest(root / "preflight.json"), "binary": binary,
        "selected_cpu": value["selected_cpu"]}, sort_keys=True), flush=True)
    return 0


def native_run(args):
    started = monotonic()
    native_deadline, signal_deadline = started + 30, started + 40
    os.umask(0o077)
    root = Path(args.run_root).resolve()
    private_directory(root)
    if SOURCE != root / "source":
        raise ScopeUnknown("run_must_use_source_snapshot_controller")
    if digest(root / "preflight.json") != args.approved_preflight_sha256:
        raise ScopeUnknown("approved_preflight_hash_mismatch")
    approved = json.loads((root / "preflight.json").read_text())
    manifest = json.loads((SOURCE / MANIFEST_RELATIVE).read_text())
    if (approved["source_commit"] != args.source_commit
            or approved["manifest_sha256"] != digest(SOURCE / MANIFEST_RELATIVE)
            or approved["selector"] != SELECTOR or approved["protected_pids"] != sorted(PROTECTED_PIDS)):
        raise ScopeUnknown("approved_scope_mismatch")
    pins = verify_sources(SOURCE, manifest)
    if pins != approved["sources_sha256"] or binary_info() != approved["binary"]:
        raise ScopeUnknown("approved_source_or_binary_changed")
    resources = available_resources(root)
    if approved["selected_cpu"] not in os.sched_getaffinity(0):
        raise ScopeUnknown("approved_cpu_is_no_longer_available")
    os.sched_setaffinity(0, {approved["selected_cpu"]})
    own = identity(os.getpid())
    if children_of(os.getpid()):
        raise ScopeUnknown("controller_has_preexisting_children")
    libc = ctypes.CDLL(None, use_errno=True)
    if libc.prctl(36, 1, 0, 0, 0) != 0:  # PR_SET_CHILD_SUBREAPER: this future subtree only.
        raise ScopeUnknown("cannot_enable_owned_descendant_reaping")
    gate_read, gate_write = os.pipe2(os.O_CLOEXEC)
    command = [approved["binary"]["executable"], "-I", "-B", "-X",
        "pycache_prefix=" + str(root / "empty-pycache"), str(HERE / "native_case_once.py"),
        str(root), str(gate_read), repr(native_deadline), repr(signal_deadline)]
    write_new_json(root / "invocation.json", {"source_commit": args.source_commit,
        "approved_preflight_sha256": args.approved_preflight_sha256, "command": command,
        "controller_birth": own, "actual_affinity": sorted(os.sched_getaffinity(0)),
        "resources": resources, "attempt": 1, "selector": SELECTOR})
    context = {"case_id": args.approved_preflight_sha256, "source_commit": args.source_commit,
               "selector": SELECTOR}
    journal = Journal(root / "raw/controller.jsonl", CONTROL_JOURNAL_CAP, context=context)
    journal.append("controller_begin", actual_affinity=sorted(os.sched_getaffinity(0)),
                   controller_birth=own, outer_wall_seconds=45, case_window_seconds=30)
    output_fds = {name: os.open(root / "raw" / (name + ".txt"),
                    os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_APPEND | os.O_NOFOLLOW, 0o600)
                  for name in ("stdout", "stderr")}
    selector, tracked, unknowns, denied = selectors.DefaultSelector(), {}, [], set()
    process, stdio_bytes, stdio_failed, stdio_eof, peaks = None, 0, False, set(), {"business": 0, "logs": 0}
    session, term_sent, kill_sent = None, set(), set()

    def unknown(code, **values):
        if code not in unknowns:
            unknowns.append(code)
            try:
                journal.append("scope_unknown", code=code, **values)
            except BaseException:
                # A full/broken journal cannot bypass owned-child cleanup.
                if "controller_journal_unavailable" not in unknowns:
                    unknowns.append("controller_journal_unavailable")

    def discover():
        parents = [os.getpid(), *tracked]
        for parent in parents:
            try:
                if parent != os.getpid() and not tracked[parent].verify():
                    continue
                child_pids = children_of(parent)
            except (FileNotFoundError, ProcessLookupError):
                continue
            except ScopeUnknown:
                unknown("bound_parent_identity_unproven", pid=parent)
                continue
            for pid in child_pids:
                if pid in denied:
                    continue
                if pid in tracked:
                    if not tracked[pid].terminal():
                        continue
                    try:
                        if same_birth(identity(pid), tracked[pid].birth):
                            continue  # The same original zombie is not PID reuse.
                    except (FileNotFoundError, ProcessLookupError):
                        continue
                    # A terminal pidfd plus a new owned child at this number is
                    # a new birth, never permission to signal the old identity.
                    old = tracked.pop(pid)
                    old.close()
                    unknown("owned_child_pid_number_reused", pid=pid)
                if pid in PROTECTED_PIDS:
                    denied.add(pid)
                    unknown("protected_pid_in_owned_tree", pid=pid)
                    continue
                try:
                    bound = BoundChild(pid, session=session, parent=parent, signal_deadline=signal_deadline)
                except (FileNotFoundError, ProcessLookupError):
                    unknown("child_exited_before_birth_binding", pid=pid)
                    denied.add(pid)
                    continue
                except ScopeUnknown:
                    unknown("child_ownership_binding_failed", pid=pid)
                    denied.add(pid)
                    continue
                tracked[pid] = bound
                journal.append("owned_descendant_bound", birth=bound.birth)

    def drain():
        nonlocal stdio_bytes, stdio_failed
        if stdio_failed:
            raise ScopeUnknown("stdio_writer_failed_latched")
        try:
            ready = selector.select(timeout=.02)
        except BaseException:
            stdio_failed = True
            raise
        for key, _ in ready:
            try:
                chunk = os.read(key.fileobj.fileno(), 65536)
            except BaseException:
                stdio_failed = True
                raise
            if not chunk:
                try:
                    selector.unregister(key.fileobj)
                    key.fileobj.close()
                except BaseException:
                    stdio_failed = True
                    raise
                stdio_eof.add(key.data)
                continue
            if stdio_bytes + len(chunk) > STDIO_CAP:
                stdio_failed = True
                unknown("stdio_cap_reached_first_raw_prefix_retained")
                raise ScopeUnknown("stdio_output_cap")
            # Reserve the full chunk before the first write. On partial write,
            # fsync or later EOF uncertainty this writer is permanently sealed.
            stdio_bytes += len(chunk)
            try:
                remaining = chunk
                while remaining:
                    written = os.write(output_fds[key.data], remaining)
                    if written <= 0:
                        raise ScopeUnknown("stdio_short_write")
                    remaining = remaining[written:]
                os.fsync(output_fds[key.data])
            except BaseException:
                stdio_failed = True
                raise

    def reap_adopted():
        for pid, bound in list(tracked.items()):
            if process is not None and pid == process.pid:
                continue  # Popen alone reaps its direct leader.
            if not bound.terminal():
                continue
            try:
                current = identity(pid)
            except (FileNotFoundError, ProcessLookupError):
                continue
            if not same_birth(current, bound.birth):
                unknown("adopted_reap_birth_changed", pid=pid)
                continue
            if current["ppid"] != os.getpid():
                continue
            try:
                result = os.waitpid(pid, os.WNOHANG)
            except ChildProcessError:
                continue  # Reaped by its original owned parent, not this controller.
            if result[0]:
                journal.append("adopted_owned_child_reaped", birth=bound.birth, wait_status=result[1])

    try:
        require_before(native_deadline, "native_start_absolute_deadline_expired")
        process = subprocess.Popen(command, stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, start_new_session=True,
            close_fds=True, pass_fds=(gate_read,), cwd=SOURCE)
        os.close(gate_read)
        gate_read = None
        session = process.pid
        leader = BoundChild(process.pid, session=session, parent=os.getpid(), signal_deadline=signal_deadline)
        tracked[process.pid] = leader
        journal.append("case_session_bound", birth=leader.birth)
        require_before(native_deadline, "case_gate_absolute_deadline_expired_after_journal")
        os.write(gate_write, b"G")
        os.close(gate_write)
        gate_write = None
        for name, stream in (("stdout", process.stdout), ("stderr", process.stderr)):
            os.set_blocking(stream.fileno(), False)
            selector.register(stream, selectors.EVENT_READ, name)
        exited_at = None
        while monotonic() < signal_deadline:
            try:
                discover()
                drain()
                reap_adopted()
            except BaseException as error:
                unknown("controller_observation_failed", error_type=type(error).__name__)
            elapsed = monotonic() - started
            try:
                data_size = tree_bytes(root / "business")
                log_size = tree_bytes(root / "raw") + tree_bytes(root / "safe")
            except BaseException as error:
                unknown("owned_tree_resource_observation_failed", error_type=type(error).__name__)
                data_size, log_size = peaks["business"], peaks["logs"]
            peaks["business"], peaks["logs"] = max(peaks["business"], data_size), max(peaks["logs"], log_size)
            if data_size > DATA_CAP:
                unknown("business_data_cap_exceeded")
            if log_size > LOG_CAP:
                unknown("log_cap_exceeded")
            code = process.poll()
            if code is not None and exited_at is None:
                exited_at = monotonic()
                journal.append("case_leader_reaped", birth=leader.birth, returncode=code)
            live = [pid for pid, bound in tracked.items() if not bound.terminal()]
            if code is not None and not live and not selector.get_map() and not children_of(os.getpid()):
                break
            stop = bool(unknowns) or elapsed >= 30 or (exited_at is not None and monotonic() - exited_at >= 1)
            if exited_at is not None and live and monotonic() - exited_at >= 1:
                unknown("owned_descendant_survived_case_exit")
            if elapsed >= 30 and code is None:
                unknown("native_case_window_exhausted")
            for pid in live:
                bound = tracked[pid]
                try:
                    if stop and pid not in term_sent:
                        term_sent.add(pid)
                        require_before(signal_deadline, "outer_signal_absolute_deadline_expired")
                        bound.send(signal.SIGTERM, journal, reason="scoped_stop_or_owned_leftover")
                    if elapsed >= 35 and pid not in kill_sent:
                        kill_sent.add(pid)
                        require_before(signal_deadline, "outer_signal_absolute_deadline_expired")
                        bound.send(signal.SIGKILL, journal, reason="scoped_term_grace_exhausted")
                except (ScopeUnknown, FileNotFoundError, ProcessLookupError):
                    unknown("owned_signal_identity_or_exit_unproven", pid=pid)
            sleep(.01)
        # No new signals are sent after40s; up to5s is reserved for final drain,
        # owned-child reaping, source checks and result/export records.
        while monotonic() - started < 42 and (selector.get_map() or children_of(os.getpid())):
            drain()
            process.poll()
            reap_adopted()
            sleep(.01)
        if process.poll() is None or any(not item.terminal() for item in tracked.values()) or children_of(os.getpid()):
            unknown("cleanup_or_reap_unproven")
        if selector.get_map() or stdio_eof != {"stdout", "stderr"} or stdio_failed:
            unknown("stdio_eof_unproven")
        try:
            after = verify_sources(SOURCE, manifest)
        except BaseException:
            after = None
            unknown("post_source_verification_failed")
        result_path = root / "raw/case-result.json"
        try:
            case_result = json.loads(result_path.read_text()) if result_path.is_file() else None
        except (ValueError, OSError):
            case_result = None
            unknown("case_result_incomplete_or_unreadable")
        if case_result is None:
            unknown("no_complete_case_result")
        elif (case_result.get("errors") or case_result.get("technical_unknowns")
              or case_result.get("source_after_sha256") != pins):
            unknown("case_error_or_source_mismatch")
        from native_safe_export import export_safe
        expected_trace = {**context, "sources_sha256": pins, "birth": leader.birth,
                          "binary": approved["binary"]}
        safe_state = export_safe(root, expected_trace)
        if not safe_state["journal_complete"]:
            unknown("native_journal_incomplete")
        if safe_state["before_quote_unknown"]:
            unknown("first_before_quote_observation_unknown")
        if not safe_state["case_result_matches_trace"]:
            unknown("case_result_trace_binding_incomplete")
        if not reconcile_owned_roles(case_result, leader.birth, [bound.birth for bound in tracked.values()]):
            unknown("actual_owned_descendants_do_not_match_closed_case_roles")
        if case_result is not None and case_result.get("test_result") == "PASS":
            if not safe_state["pass_evidence_complete"] or process.returncode != 0:
                unknown("case_pass_claim_not_closed_by_first_raw_and_exit")
        elif case_result is not None and case_result.get("test_result") == "FAIL":
            if not safe_state["failure_evidence_complete"] or process.returncode != 1:
                unknown("case_failure_claim_not_closed_by_first_raw_and_exit")
        elif case_result is not None:
            unknown("case_result_has_no_known_test_conclusion")
        if monotonic() - started >= 45:
            unknown("outer_wall_budget_exceeded")
        passed = (not unknowns and process.returncode == 0 and case_result is not None
                  and case_result.get("test_result") == "PASS"
                  and safe_state["pass_evidence_complete"])
        conclusion = "UNKNOWN" if unknowns else "PASS" if passed else "FAIL"
        final = {"conclusion": conclusion, "source_commit": args.source_commit,
            "selector": SELECTOR, "attempt": 1, "returncode": process.returncode,
            "unknown_codes": unknowns, "actual_affinity": sorted(os.sched_getaffinity(0)),
            "elapsed_seconds": monotonic() - started, "observed_peak_bytes": peaks,
            "source_after_sha256": after, "case_result": case_result,
            "local_diagnostic_not_original_ci_reproduction": True,
            "original_ci_two_failures_unresolved": True}
        journal.append("controller_end", conclusion=conclusion, unknown_codes=unknowns,
                       elapsed_seconds=final["elapsed_seconds"], observed_peak_bytes=peaks)
        write_new_json(root / "result.json", final)
        return 0 if conclusion == "PASS" else 1 if conclusion == "FAIL" else 75
    except BaseException as error:
        # No exception after releasing the gate may bypass the cleanup window.
        unknown("controller_exception", error_type=type(error).__name__)
        if gate_write is not None:
            os.close(gate_write)
            gate_write = None
        if process is not None:
            for name, stream in (("stdout", process.stdout), ("stderr", process.stderr)):
                if not stream.closed and stream not in [item.fileobj for item in selector.get_map().values()]:
                    os.set_blocking(stream.fileno(), False)
                    selector.register(stream, selectors.EVENT_READ, name)
            while monotonic() < signal_deadline:
                try:
                    discover()
                    drain()
                    reap_adopted()
                except BaseException:
                    unknown("emergency_observation_incomplete")
                live = [pid for pid, bound in tracked.items() if not bound.terminal()]
                if process.poll() is not None and not live and not children_of(os.getpid()) and not selector.get_map():
                    break
                for pid in live:
                    try:
                        bound = tracked[pid]
                        if pid not in term_sent:
                            term_sent.add(pid)
                            require_before(signal_deadline, "emergency_signal_absolute_deadline_expired")
                            bound.send(signal.SIGTERM, journal, reason="controller_exception_cleanup")
                        if monotonic() - started >= 35 and pid not in kill_sent:
                            kill_sent.add(pid)
                            require_before(signal_deadline, "emergency_signal_absolute_deadline_expired")
                            bound.send(signal.SIGKILL, journal, reason="controller_exception_grace_exhausted")
                    except BaseException:
                        unknown("emergency_signal_or_journal_unproven", pid=pid)
                sleep(.02)
            process.poll()
        residual = children_of(os.getpid())
        write_new_json(root / "emergency-result.json", {"conclusion": "UNKNOWN", "attempt": 1,
            "source_commit": args.source_commit, "unknown_codes": unknowns,
            "elapsed_seconds": monotonic() - started, "residual_direct_children": residual,
            "cleanup_proven": (not residual and (process is None or process.returncode is not None)
                               and all(bound.terminal() for bound in tracked.values())),
            "original_ci_two_failures_unresolved": True})
        return 75
    finally:
        for gate in (gate_read, gate_write):
            if gate is not None:
                os.close(gate)
        for stream in list(selector.get_map().values()):
            stream.fileobj.close()
        selector.close()
        for fd in output_fds.values():
            os.fsync(fd)
            os.close(fd)
        for bound in tracked.values():
            bound.close()
        journal.close()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=("preflight", "run"))
    parser.add_argument("--run-root", required=True)
    parser.add_argument("--source-commit", required=True)
    parser.add_argument("--approved-preflight-sha256")
    args = parser.parse_args()
    if len(args.source_commit) != 40 or any(character not in "0123456789abcdef" for character in args.source_commit):
        raise ScopeUnknown("source_commit_must_be_exact_hex40")
    if args.mode == "run" and not args.approved_preflight_sha256:
        raise ScopeUnknown("final_run_requires_exact_reviewed_preflight_hash")
    if args.mode == "preflight":
        deadline = monotonic() + 10
        def preflight_budget(frame, event, arg):
            if monotonic() >= deadline:
                print('{"status":"PREFLIGHT_UNKNOWN_WALL_BUDGET"}', flush=True)
                os._exit(124)
            return preflight_budget
        sys.settrace(preflight_budget)
        try:
            return preflight(args)
        finally:
            sys.settrace(None)
    if (len(args.approved_preflight_sha256) != 64
            or any(character not in "0123456789abcdef" for character in args.approved_preflight_sha256)):
        raise ScopeUnknown("preflight_hash_must_be_exact_hex64")
    started = monotonic()
    status = native_run(args)  # Returns only after its fd/pidfd/journal finalizers.
    elapsed = monotonic() - started
    if elapsed >= 45:
        status = 75
    write_new_json(Path(args.run_root) / "completion.json", {"outer_status": status,
        "elapsed_after_finalizers_seconds": elapsed, "wall_budget_seconds": 45,
        "terminal_status_requires_matching_process_exit": True,
        "original_ci_two_failures_unresolved": True})
    # Completion fsync can also consume the budget. The caller must retain the
    # actual exit code; a completion/exit mismatch is UNKNOWN, never PASS.
    return 75 if monotonic() - started >= 45 else status


if __name__ == "__main__":
    raise SystemExit(main())
