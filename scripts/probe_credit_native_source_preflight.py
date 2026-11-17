#!/usr/bin/env python3
"""Independent actual old RED/new GREEN source-admission probe, bounded window."""

import argparse
from copy import deepcopy
from datetime import datetime, timezone
from decimal import Decimal as D
import hashlib
import io
import json
import os
from pathlib import Path, PurePosixPath
import subprocess
import sys
import tarfile
from tempfile import TemporaryDirectory
import time


ROOT = Path(__file__).resolve().parents[1]
OLD = "9e8d4ea0406db80ee93c94eb0bbfecd7b5058bfc"
NEW = "a4d4facc3235a324afbc0fdb19635bf0bbc86a75"
FIX = "26f7c59ec66f4553fcd135816509f02a00550de7"
FIX_NATIVE_SHA256 = "903ab01e0a7a5b4956b0bfb6ef00eac5cb4a946f376876eec70597f2d827950f"


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def make_descriptor(pool_units):
    authorities = ["independent:shard0", "independent:shard1"]
    layout = hashlib.sha256(b"independent-source-preflight-layout").hexdigest()
    policy = {"format": 1, "name": "SYNTHETIC-CREDIT-ZERO-v1", "version": 1,
              "new_interest_rate": "0", "new_borrow_fee_rate": "0", "require_managed_inbox": True,
              "borrow_batch_size": 0, "production_approved": False, "credit_assets": ["BTC"]}
    policy_id = "credit-policy:" + hashlib.sha256(canonical(policy).encode()).hexdigest()
    allocations = [{"shard": s, "authority_id": authority, "limit_units": "50000000",
                    "opening_principal_units": "0", "opening_interest_units": "0",
                    "opening_pool_units": str(pool_units if s == 0 else 100000000),
                    "funding_claims": [{"source_reference": f"synthetic:preflight:source:{s}",
                                        "command_id": f"independent-pool-{s}", "funded_units": "100000000"}]}
                   for s, authority in enumerate(authorities)]
    certificate = {"format": 1, "budget_id": "independent:preflight:budget", "version": 1,
                   "layout_hash": layout, "credit_policy_id": policy_id,
                   "authorities": [{"shard": s, "authority_id": a} for s, a in enumerate(authorities)],
                   "assets": {"BTC": {"scale": 8, "global_limit_units": "100000000", "allocations": allocations}}}
    return {"format": 1, "stage": "NATIVE_PREPARED", "synthetic": True, "authority_id": authorities[0],
            "shard": 0, "layout_hash": layout, "credit_policy": policy, "credit_policy_id": policy_id,
            "certificate": certificate, "certificate_id": "credit-budget:" + hashlib.sha256(canonical(certificate).encode()).hexdigest()}


def child(source, variant, output):
    sys.path.insert(0, str(source))
    from uta.credit import CreditService
    from uta import credit_native
    from uta.decision_audit import DecisionAudit
    from uta.durable_commands import QueueStore
    from uta.ledger import Ledger
    from uta.market import MarketSnapshot
    from uta.models import AssetSpec, InstrumentSpec
    from uta.service import ExchangeService
    from uta.storage import Database, DurableLedger
    from uta.writer_fence import WriterFence, _REGISTRY

    trace, watching, connection_ids = [], [False], []

    class ObservedDatabase(Database):
        def _connect(self):
            connection = super()._connect()
            if watching[0]:
                connection_ids.append(id(connection))
                def observer(statement):
                    upper = statement.lstrip().upper()
                    if upper.startswith(("BEGIN", "COMMIT", "ROLLBACK", "CREATE", "ALTER", "DROP")):
                        trace.append(statement)
                connection.set_trace_callback(observer)
            return connection

    def snapshot(database):
        with database.read_transaction() as connection:
            schema = [list(row) for row in connection.execute("SELECT name,type,tbl_name,sql FROM sqlite_master ORDER BY name")]
            tables = [row[0] for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name")]
            return {"schema": schema, "tables": {name: [list(row) for row in connection.execute('SELECT * FROM "' + name.replace('"', '""') + '" ORDER BY rowid')] for name in tables}}

    original_codes = {DurableLedger.verify.__code__: "DurableLedger.verify", CreditService._verify.__code__: "CreditService._verify",
                      ExchangeService.__init__.__code__: "FORBIDDEN:ExchangeService.__init__", CreditService.__init__.__code__: "FORBIDDEN:CreditService.__init__",
                      DurableLedger.__init__.__code__: "FORBIDDEN:DurableLedger.__init__", DurableLedger.post.__code__: "FORBIDDEN:DurableLedger.post",
                      CreditService.borrow.__code__: "FORBIDDEN:CreditService.borrow", CreditService.repay.__code__: "FORBIDDEN:CreditService.repay",
                      ExchangeService.deposit.__code__: "FORBIDDEN:ExchangeService.deposit", Ledger.__init__.__code__: "PURE:LedgerCodec.__init__"}
    if hasattr(credit_native, "_verify_financial_source"):
        original_codes[credit_native._verify_financial_source.__code__] = "credit_native._verify_financial_source"
    results = []
    for case in (["pool_projection", "masked_principal"] if variant == "old" else ["pool_projection", "masked_principal", "healthy"]):
        with TemporaryDirectory(prefix=f"uta-independent-source-{variant}-{case}-") as directory:
            path = Path(directory) / "authority.sqlite3"
            db = ObservedDatabase(path)
            now = datetime(2026, 11, 17, tzinfo=timezone.utc)
            service = ExchangeService(db, {"USD": 8, "BTC": 8}, fee_rate=D(0), clock=lambda: now)
            for account in ("alice", "bob"):
                service.create_account(account)
                service.deposit(account, "independent-opening-cash", "USD", D(100))
            service.publish_market(MarketSnapshot(1, now,
                {"USD": AssetSpec(D(1), D(1)), "BTC": AssetSpec(D(100), D(".8"))},
                {"BTC-PERP": InstrumentSpec(D(100), D(".1"), D(".05"))}))
            service.set_kill_switch(False)
            credit = CreditService(service)
            credit.configure_asset_limit("BTC", D(100))
            for account in ("alice", "bob"):
                credit.configure_limit(account, "BTC", D(10))
            credit.fund_pool("independent-pool-0", "BTC", D(1), source_reference="synthetic:preflight:source:0")
            QueueStore(db, initialize=True)
            audit = DecisionAudit(db)
            with db.transaction() as connection:
                audit.install(connection, policy=DecisionAudit.policy(service), recorded_at=now.isoformat())
            healthy_seed = snapshot(db)
            corruption = []
            if case != "healthy":
                with db.transaction() as connection:
                    if case == "pool_projection":
                        sql = "UPDATE ledger_balances SET units='50000000' WHERE account='system:credit-pool' AND asset='BTC'"
                        connection.execute(sql)
                        corruption.append(sql)
                    else:
                        for account, principal in (("alice", "0.1"), ("bob", "-0.1")):
                            sql = "INSERT INTO uta_liabilities(account_id,asset,principal,interest) VALUES(?,?,?,?)"
                            parameters = (account, "BTC", principal, "0")
                            connection.execute(sql, parameters)
                            corruption.append({"sql": sql, "parameters": parameters})
            corrupted_seed = snapshot(db)
            fence = WriterFence(db)
            fence.enable("independent:shard0")
            descriptor = make_descriptor(50000000 if case == "pool_projection" else 100000000)
            before = snapshot(db)
            trace.clear()
            connection_ids.clear()
            profile = []
            def observe_call(frame, event, value):
                if event not in ("call", "return") or frame.f_code not in original_codes:
                    return
                name = original_codes[frame.f_code]
                connection = frame.f_locals.get("connection")
                guard = _REGISTRY.get(id(connection)) if connection is not None else None
                profile.append({"method": name, "event": event,
                                "connection_identity": id(connection) if connection is not None else None,
                                "in_transaction": bool(connection.in_transaction) if connection is not None else None,
                                "guard_role": guard.role if guard is not None else None,
                                "guard_exact_connection": guard.connection is connection if guard is not None else None,
                                "guard_same_database": guard.database is db if guard is not None else None,
                                "return_integer": value if event == "return" and type(value) is int else None})
            accepted, result, error = False, None, None
            watching[0] = True
            sys.setprofile(observe_call)
            started = time.perf_counter()
            try:
                result = credit_native.prepare_credit_native(db, descriptor)
                accepted = True
            except Exception as exc:
                error = {"type": type(exc).__module__ + "." + type(exc).__name__, "code": getattr(exc, "code", None), "message": str(exc),
                         "cause_type": type(exc.__cause__).__module__ + "." + type(exc.__cause__).__name__ if exc.__cause__ is not None else None,
                         "cause_message": str(exc.__cause__) if exc.__cause__ is not None else None,
                         "typed_native_error": isinstance(exc, credit_native.CreditNativeError)}
            finally:
                elapsed = time.perf_counter() - started
                sys.setprofile(None)
                watching[0] = False
            # Reopen with a new actual Database object after the transaction exits.
            after = snapshot(Database(path))
            state = WriterFence(Database(path)).status()
            native_objects = [row[0] for row in after["schema"] if row[0].startswith("credit_native_") or row[0] == "writer_fence_credit_capability"]
            native_ddl = [sql for sql in trace if sql.lstrip().upper().startswith(("CREATE", "ALTER", "DROP"))]
            verifier_calls = [r for r in profile if r["event"] == "call" and r["method"] in ("credit_native._verify_financial_source", "DurableLedger.verify", "CreditService._verify")]
            same_control = (bool(verifier_calls) and len({r["connection_identity"] for r in verifier_calls}) == 1
                            and len(connection_ids) == 1 and all(r["guard_role"] == "control" and r["in_transaction"]
                                and r["guard_exact_connection"] and r["guard_same_database"] for r in verifier_calls)
                            and "BEGIN IMMEDIATE" in trace)
            forbidden = [r for r in profile if r["event"] == "call" and r["method"].startswith("FORBIDDEN:")]
            safe_bad = (not accepted and error is not None and error["typed_native_error"]
                        and error["code"] == "credit_financial_source_invalid" and before == after
                        and not native_objects and not native_ddl and state["generation"] == 0 and state["owner_nonce"] is None)
            healthy_ok = (accepted and result["stage"] == "NATIVE_PREPARED" and result["trading_enabled"] is False
                          and bool(native_objects) and state["generation"] == 0 and state["owner_nonce"] is None and not state["active"])
            required_methods = {"DurableLedger.verify"} if case == "pool_projection" else {"DurableLedger.verify", "CreditService._verify"}
            observed_methods = {r["method"] for r in verifier_calls}
            invariants = {"same_actual_control_write_snapshot": same_control, "no_service_or_durable_constructor_or_financial_mutator": not forbidden,
                          "required_full_original_verifiers_observed": required_methods <= observed_methods}
            safety_assertion = safe_bad if case != "healthy" else healthy_ok
            results.append({"id": variant + ":" + case, "case": case, "healthy_seed": healthy_seed,
                            "manual_corruption_before_fence": corruption, "corrupted_seed_before_fence": corrupted_seed,
                            "descriptor": descriptor, "before_preparation": before, "actual_accepted": accepted,
                            "actual_result": result, "actual_error": error, "after_reopen": after,
                            "actual_fence_after_reopen": state, "native_objects_after_reopen": native_objects,
                            "prepare_elapsed_seconds": round(elapsed, 6), "actual_prepare_sql_trace": list(trace),
                            "prepare_connection_count": len(connection_ids), "observed_original_methods": profile,
                            "observational_invariants": invariants, "bad_source_rejected_before_any_native_effect": safe_bad if case != "healthy" else None,
                            "safety_assertion_passed": safety_assertion})
        results[-1]["temporary_directory_cleaned"] = not Path(directory).exists()
    report = {"variant": variant, "source_root": str(source), "source_sha256": {str(p.relative_to(source)): hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted((source / "uta").rglob("*.py"))},
              "cpu_affinity": sorted(os.sched_getaffinity(0)), "cases": results,
              "status": "ACTUAL_OLD_SAFETY_RED" if variant == "old" else "ACTUAL_NEW_SOURCE_GREEN_IF_ALL_ASSERTIONS_PASS"}
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"variant": variant, "accepted": [r["id"] for r in results if r["actual_accepted"]],
                      "safety_assertions": [r["safety_assertion_passed"] for r in results]}))
    # The actual old run intentionally retains its real safety assertion RED.
    assert all(r["safety_assertion_passed"] for r in results), "corrupt financial source was admitted to irreversible native preparation"
    assert all(all(r["observational_invariants"].values()) for r in results), "source checks did not run as the promised pure views on one control W connection"


def export_source(commit, destination):
    result = subprocess.run(["git", "archive", commit, "uta"], cwd=ROOT, capture_output=True, check=True, timeout=30)
    with tarfile.open(fileobj=io.BytesIO(result.stdout)) as archive:
        for member in archive.getmembers():
            relative = PurePosixPath(member.name)
            if relative.is_absolute() or ".." in relative.parts or not relative.parts or relative.parts[0] != "uta" or not (member.isdir() or member.isfile()):
                raise AssertionError("unsafe source archive entry")
            target = destination.joinpath(*relative.parts)
            if member.isdir():
                target.mkdir(parents=True, exist_ok=True)
            else:
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(archive.extractfile(member).read())


def run_window(output):
    started = time.perf_counter()
    records = []
    output.mkdir(parents=True, exist_ok=True)
    with TemporaryDirectory(prefix="uta-independent-source-exports-") as temporary:
        sources = Path(temporary)
        for variant, commit in (("old", OLD), ("new", NEW)):
            destination = sources / variant
            export_source(commit, destination)
            if variant == "new" and hashlib.sha256((destination / "uta/credit_native.py").read_bytes()).hexdigest() != FIX_NATIVE_SHA256:
                raise AssertionError("new native source does not match reviewed 26f financial-source fix")
            remaining = 5 - (time.perf_counter() - started)
            if remaining <= 0:
                raise TimeoutError("global five-second probe budget exhausted before subprocess")
            command = [sys.executable, str(Path(__file__).resolve()), "--child", variant,
                       "--source", str(destination), "--output", str(output / (variant + ".json"))]
            child_started = time.perf_counter()
            try:
                result = subprocess.run(command, cwd=destination, text=True, capture_output=True, timeout=min(30, remaining))
                record = {"variant": variant, "source_commit": commit, "command": command, "cwd": str(destination),
                          "timeout_seconds": min(30, remaining), "returncode": result.returncode,
                          "stdout": result.stdout, "stderr": result.stderr, "timed_out": False}
            except subprocess.TimeoutExpired as exc:
                record = {"variant": variant, "source_commit": commit, "timed_out": True, "stdout": exc.stdout, "stderr": exc.stderr}
                records.append(record)
                break
            record["elapsed_seconds"] = round(time.perf_counter() - child_started, 6)
            records.append(record)
    elapsed = time.perf_counter() - started
    success = (len(records) == 2 and not any(r["timed_out"] for r in records)
               and records[0]["returncode"] == 1 and records[1]["returncode"] == 0 and elapsed <= 5)
    report = {"frozen_new_commit": NEW, "old_commit": OLD, "financial_fix_commit": FIX,
              "financial_fix_credit_native_sha256": FIX_NATIVE_SHA256,
              "probe_source_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
              "cpu_affinity": sorted(os.sched_getaffinity(0)), "window_seconds": round(elapsed, 6),
              "global_budget_seconds": 5, "subprocess_timeout_ceiling_seconds": 30,
              "records": records, "expected_old_red_new_green_observed": success,
              "source_exports_cleaned": not sources.exists(), "scope": "actual future native PREPARED source admission only; no public borrow, owner, READY, activation or funds permission"}
    (output / "window.json").write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"window_seconds": report["window_seconds"], "expected_old_red_new_green_observed": success,
                      "returncodes": [r.get("returncode") for r in records]}))
    return not success


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--child", choices=("old", "new"))
    parser.add_argument("--source", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.child:
        child(args.source, args.child, args.output)
    else:
        raise SystemExit(run_window(args.output.resolve()))
