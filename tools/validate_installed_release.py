"""Independent wheel acceptance, run with the fresh venv's ``python -I``.

The source tree is only read for hashes and for an unchanged CLI test helper.
Only that helper's subprocess cwd (ROOT) is redirected to installed site-packages.
All financial imports, spawned workers and CLI commands use the installed wheel.
No service, risk, accounting, matching or authentication function is patched.
"""
from __future__ import annotations

import argparse
from contextlib import closing
from datetime import datetime, timedelta, timezone
from decimal import Decimal as D
from hashlib import sha256
from http.client import HTTPSConnection
import importlib.metadata
import importlib.util
import json
import os
from pathlib import Path
import secrets
import shutil
import signal
import sqlite3
import ssl
import subprocess
import sys
import unittest

import uta
from uta.durable_process import DurableProcessRouter
from uta.market import MarketSnapshot
from uta.models import AssetSpec, InstrumentSpec
from uta.request_signing import sign_headers


def installed_modules(site):
    result = {}
    for name, module in sorted(sys.modules.items()):
        if name == "uta" or name.startswith("uta."):
            path = Path(module.__file__).resolve()
            if not path.is_relative_to(site):
                raise AssertionError(f"noninstalled financial import: {name}: {path}")
            result[name] = str(path)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--artifact-manifest", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--identity-only", action="store_true",
                        help="verify installed bytes only; never claim functional tests were executed")
    args = parser.parse_args()
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    source = args.source.resolve()
    site = Path(uta.__file__).resolve().parent.parent
    if not sys.flags.isolated:
        raise AssertionError("invoke the installed verifier with python -I")
    if site.is_relative_to(source) or source in map(Path, sys.path):
        raise AssertionError("source checkout must not be an import location")
    if os.environ.get("PYTHONPATH"):
        raise AssertionError("unset PYTHONPATH before installed acceptance")
    if importlib.metadata.version("uta-reference-exchange") != "0.4.0a1":
        raise AssertionError("unexpected installed distribution version")
    entries = {entry.name: entry.value for entry in importlib.metadata.distribution("uta-reference-exchange").entry_points
               if entry.group == "console_scripts"}
    if entries != {"uta": "uta.__main__:main", "uta-ops": "uta.ops:main", "uta-durable": "uta.durable_cli:main"}:
        raise AssertionError("installed console-script targets differ from frozen contract")
    manifest = json.loads(args.artifact_manifest.read_text())
    installed_runtime = {str(path.relative_to(site)): sha256(path.read_bytes()).hexdigest()
                         for path in (site / "uta").rglob("*")
                         if path.is_file() and path.suffix in (".py", ".html")}
    runtime_digest = sha256(json.dumps(installed_runtime, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    if installed_runtime != manifest["runtime_files"] or runtime_digest != manifest["runtime_tree_sha256"]:
        raise AssertionError("installed runtime differs from frozen artifact manifest")
    identity = {"source_commit": manifest["source_commit"], "runtime_tree_sha256": runtime_digest,
                "artifacts": manifest["artifacts"], "version": uta.__version__,
                "installed_site": str(site), "isolated": bool(sys.flags.isolated),
                "sys_path": sys.path, "modules": installed_modules(site), "production_approved": False}
    if args.identity_only:
        identity.update(scope="installed runtime identity only", functional_tests_executed=0, passed=True)
        (output / "installed-identity.json").write_text(json.dumps(identity, indent=2, sort_keys=True) + "\n")
        print(json.dumps({key: identity[key] for key in ("source_commit", "runtime_tree_sha256", "functional_tests_executed", "passed")}))
        return 0
    original = source / "tests/test_durable_cli.py"
    if sha256(original.read_bytes()).hexdigest() != manifest["cli_helper_sha256"]:
        raise AssertionError("CLI acceptance helper differs from frozen artifact manifest")
    copied = output / "frozen_test_durable_cli.py"
    shutil.copyfile(original, copied)
    spec = importlib.util.spec_from_file_location("frozen_test_durable_cli", copied)
    helper = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = helper
    spec.loader.exec_module(helper)
    # ROOT controls subprocess cwd only. Every financial function and assertion
    # in the frozen test module remains byte-for-byte unchanged.
    helper.ROOT = site

    class FinancialProtocolCase(helper.DurableCLITests):
        def test_success_unknown_reply_and_offline_pending_survive_new_parent(self):
            def bootstrap(router):
                router.create_account("alice")
                router.deposit("alice", "synthetic-release-funding", "USD", D(1000))
            router = DurableProcessRouter.initialize(self.directory, 1, {"USD": 2}, managed=True,
                bootstrap=bootstrap, max_price_age=timedelta(seconds=60), decision_audit=True)
            self.addCleanup(router.close)
            self.tls_and_auth()
            first, port = self.start()
            first_health, _ = self.eventually(lambda: helper.health_after(self, port))
            snapshot = MarketSnapshot(1, datetime.now(timezone.utc),
                {"USD": AssetSpec(D(1), D(1))}, {"X": InstrumentSpec(D(100), D(".1"), D(".05"))})
            quote = self.root / "quote.json"
            quote.write_text(snapshot.to_json())
            self.command("publish", "--snapshot-file", quote)
            self.assertFalse(self.command("activate")["halted"])
            payload = {"command_id": "lost-order-reply", "order_id": "release-order", "symbol": "X",
                       "quantity": "1", "limit_price": "100"}
            body = json.dumps(payload, separators=(",", ":")).encode()
            headers = sign_headers(self.profile, "trader", timestamp_ms=__import__("time").time_ns() // 1000000,
                nonce=secrets.token_urlsafe(24), method="POST", request_target="/v2/accounts/alice/orders", body=body)
            wire = HTTPSConnection("127.0.0.1", port,
                context=ssl.create_default_context(cafile=self.cert), timeout=4)
            try:
                wire.request("POST", "/v2/accounts/alice/orders", body=body,
                             headers={"Content-Type": "application/json", **headers})
                # Observe the command independently, then discard the actual
                # business response without reading its status or body.
                accepted = self.eventually(lambda: router.status("lost-order-reply", account_id="alice"))
                self.assertEqual(accepted["ack"], "durably_queued")
            finally:
                wire.close()
            def success():
                record = router.status("lost-order-reply", account_id="alice")
                return record if record["state"] == "SUCCEEDED" else None
            completed_order = self.eventually(success)
            self.assertEqual(D(completed_order["result"]["reserved_margin"]), D("10.04"))
            with closing(sqlite3.connect(f"file:{router._database(0).path}?mode=ro", uri=True)) as connection, connection:
                rows = connection.execute("SELECT quantity,filled_quantity,status FROM uta_orders WHERE account_id='alice'").fetchall()
            self.assertEqual(rows, [("1", "0", "OPEN")])  # One reserve: 100*.1 + ceil_cents(100*.0004)
            first.send_signal(signal.SIGTERM)
            _, errors = first.communicate(timeout=12)
            self.assertEqual(first.returncode, 0, errors)
            pending = router._queue(0).enqueue_cancel("alice", "offline-cancel", "release-order")
            self.assertEqual((pending["ack"], pending["state"]), ("durably_queued", "PENDING"))
            second, second_port = self.start()
            self.assertNotEqual(first.pid, second.pid)
            self.eventually(lambda: helper.health_after(self, second_port))
            code, repeated, _ = self.request(second_port, "POST", "/v2/accounts/alice/orders", payload, key="trader")
            self.assertEqual((code, repeated["state"]), (200, "SUCCEEDED"))
            self.assertEqual(repeated["result"], completed_order["result"])
            def canceled():
                code, record, _ = self.request(second_port, "GET", "/v2/accounts/alice/commands/offline-cancel", key="trader")
                return record if code == 200 else None
            self.assertEqual(self.eventually(canceled)["state"], "SUCCEEDED")
            health, _ = self.eventually(lambda: helper.health_after(self, second_port))
            self.assertGreater(health["workers"][0]["generation"], first_health["workers"][0]["generation"])
            with closing(sqlite3.connect(f"file:{router._database(0).path}?mode=ro", uri=True)) as connection, connection:
                rows = connection.execute("SELECT quantity,filled_quantity,status FROM uta_orders WHERE account_id='alice'").fetchall()
                decisions = connection.execute("SELECT COUNT(*) FROM uta_risk_decisions").fetchone()[0]
                balances = connection.execute("SELECT units FROM ledger_balances WHERE account='customer:alice' AND asset='USD'").fetchall()
            self.assertEqual(rows, [("1", "0", "CANCELLED")])
            self.assertEqual(decisions, 1)
            self.assertEqual(balances, [("100000",)])
            second.send_signal(signal.SIGTERM)
            _, errors = second.communicate(timeout=12)
            self.assertEqual(second.returncode, 0, errors)

    installed_modules(site)
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(helper.DurableCLITests)
    suite.addTest(FinancialProtocolCase("test_success_unknown_reply_and_offline_pending_survive_new_parent"))
    with (output / "installed-cli-tests.txt").open("w") as log:
        result = unittest.TextTestRunner(stream=log, verbosity=2).run(suite)
    commands = []
    environment = dict(os.environ)
    environment.pop("PYTHONPATH", None)
    for command in (("uta-durable", "--help"), ("uta-ops", "--help"), ("uta", "demo"), ("uta", "acceptance"), ("uta", "scenario")):
        executable = Path(sys.executable).parent / command[0]
        completed = subprocess.run([str(executable), *command[1:]], cwd=output, env=environment,
            capture_output=True, text=True, timeout=45)
        name = "-".join(command)
        (output / (name + ".stdout.txt")).write_text(completed.stdout)
        (output / (name + ".stderr.txt")).write_text(completed.stderr)
        commands.append({"argv": [str(executable), *command[1:]], "returncode": completed.returncode})
        if completed.returncode:
            raise AssertionError(f"installed entrypoint failed: {command}: {completed.stderr}")
        if command[0] == "uta" and command[1] == "acceptance":
            accepted = json.loads(completed.stdout)
            if accepted["status"] != "passed" or accepted["production_approved"] is not False:
                raise AssertionError("acceptance scope/status mismatch")
    directory = output / "empty-cli-authority"
    for operation in ("init", "inspect", "status"):
        argv = [str(Path(sys.executable).parent / "uta-durable"), operation, "--directory", str(directory)]
        completed = subprocess.run(argv, cwd=output, env=environment, capture_output=True, text=True, timeout=20)
        (output / f"uta-durable-{operation}.stdout.txt").write_text(completed.stdout)
        (output / f"uta-durable-{operation}.stderr.txt").write_text(completed.stderr)
        commands.append({"argv": argv, "returncode": completed.returncode})
        if completed.returncode:
            raise AssertionError(f"installed entrypoint failed: {operation}: {completed.stderr}")
    qualified = result.wasSuccessful() and result.testsRun == 8 and not result.skipped
    report = {**identity, "version": uta.__version__, "interpreter": sys.version, "sqlite": sqlite3.sqlite_version,
        "installed_site": str(site), "sys_path": sys.path, "isolated": bool(sys.flags.isolated),
        "pythonpath": os.environ.get("PYTHONPATH"), "helper_sha256": sha256(original.read_bytes()).hexdigest(),
        "copied_helper_sha256": sha256(copied.read_bytes()).hexdigest(), "helper_root_override": str(helper.ROOT),
        "modules": installed_modules(site), "tests": {"run": result.testsRun,
        "failures": len(result.failures), "errors": len(result.errors), "skipped": len(result.skipped)},
        "commands": commands, "console_script_targets": entries, "expected_tests": 8,
        "passed": qualified, "production_approved": False}
    (output / "installed-report.json").write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    print(json.dumps({k: report[k] for k in ("version", "tests", "passed", "production_approved")}))
    return 0 if qualified else 1


if __name__ == "__main__":
    raise SystemExit(main())
