"""Two real disposable processes, original CIDs and real bootclock lease expiry."""
from hashlib import sha256
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import unittest

from tests.credit_v2_runtime_fixture import SyntheticCreditAuthority


class ActualCreditProcessRecoveryTests(unittest.TestCase):
    def test_crash_after_actual_commits_loses_replies_then_new_process_replays_once(self):
        fixture = SyntheticCreditAuthority()
        self.addCleanup(fixture.close)
        directory = fixture.path.parent
        envelope, checkpoint = directory/"canonical-envelope.json", directory/"committed-before-reply.json"
        envelope.write_text(fixture.envelope)
        envelope.chmod(0o600)
        command = [sys.executable, "-W", "error::ResourceWarning", "-m", "tests.credit_v2_process_worker"]
        crashed = subprocess.run([*command, "commit_then_crash", str(fixture.path), str(envelope), str(checkpoint)],
            cwd=Path(__file__).resolve().parents[1], stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=25)
        self.assertEqual(crashed.returncode, 73, crashed.stderr.decode())
        self.assertEqual(crashed.stdout, b"", "the crashed worker delivered no application receipt")
        marker = json.loads(checkpoint.read_text())
        self.assertEqual(marker["phase"], "after_actual_borrow_and_repay_COMMIT_before_client_reply")
        with fixture.db.read_transaction() as connection:
            before = {table: [tuple(row) for row in connection.execute("SELECT * FROM "+table+" ORDER BY rowid")]
                for table in ("credit_v2_sources", "credit_v2_intents", "uta_credit_decisions", "credit_commands", "uta_command_inbox",
                              "uta_accounts", "uta_liabilities", "ledger_events", "ledger_postings", "ledger_balances", "uta_events")}
            expires = connection.execute("SELECT expires_ns FROM writer_fence_lease WHERE singleton=1").fetchone()[0]
            self.assertEqual(connection.execute("SELECT generation FROM writer_fence_lease WHERE singleton=1").fetchone()[0], 1)
        remaining = max(0, (expires-time.clock_gettime_ns(time.CLOCK_BOOTTIME))/1_000_000_000+0.03)
        self.assertLessEqual(remaining, 15.1)
        if remaining:
            time.sleep(remaining)  # Real bootclock lease expiry; no fake time/token.
        recovered = subprocess.run([*command, "recover", str(fixture.path), str(envelope), str(checkpoint)],
            cwd=Path(__file__).resolve().parents[1], stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=20)
        self.assertEqual(recovered.returncode, 0, recovered.stderr.decode())
        record = json.loads(recovered.stdout)
        self.assertNotEqual(record["pid"], marker["pid"])
        self.assertNotIn(os.getpid(), (record["pid"], marker["pid"]))
        self.assertEqual(record["generation"], 2)
        self.assertEqual(record["actual"], {"counts": {"credit_v2_sources": 2, "credit_v2_intents": 2,
            "uta_credit_decisions": 1, "ledger_events": 4}, "debt": ["0.3", "0"],
            "customer_btc_units": "30000000", "pool_btc_units": "70000000", "foreign_key_check": []})
        with fixture.db.read_transaction() as connection:
            after = {table: [tuple(row) for row in connection.execute("SELECT * FROM "+table+" ORDER BY rowid")] for table in before}
            self.assertEqual(after, before)
            self.assertIsNone(connection.execute("SELECT owner_nonce FROM writer_fence_lease WHERE singleton=1").fetchone()[0])
        output = os.environ.get("UTA_CREDIT_V2_CAPTURE_DIRECTORY")
        if output:
            path = Path(output)
            path.mkdir(parents=True, exist_ok=True)
            (path/"actual-crash-checkpoint.json").write_text(json.dumps(marker, indent=2)+"\n")
            (path/"actual-recovery-process.json").write_bytes(recovered.stdout)
        print(json.dumps({"crashed_process_exit": 73, "actual_distinct_worker_pids": [marker["pid"], record["pid"]],
            "native_generation": record["generation"], "actual_lease_wait_seconds": remaining,
            "financial_rows_unchanged_on_recovery": True, "actual": record["actual"],
            "scope": "actual process exit after financial COMMIT/reply loss; real lease expiry/new process recovery, not mid-COMMIT power loss or replication"}, sort_keys=True))


if __name__ == "__main__":
    unittest.main()
