"""Independent single-host router fault/recovery checks; not HA certification."""
from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal as D
import json
from pathlib import Path
import shutil
import sqlite3
import subprocess
import sys
from tempfile import TemporaryDirectory
from time import monotonic, sleep
import unittest

from uta.market import MarketSnapshot
from uta.models import AssetSpec, InstrumentSpec
from uta.ops import backup_database
from uta.service import ServiceError
from uta.sharding import ShardRouter


NOW = datetime(2026, 11, 14, tzinfo=timezone.utc)


class ShardingFaultTests(unittest.TestCase):
    def setUp(self):
        self.temporary = TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.path = Path(self.temporary.name) / "router"
        self.router = self.reopen()

    def reopen(self):
        return ShardRouter(self.path, 2, {"USD": 8}, clock=lambda: NOW)

    def market(self, version=1):
        return MarketSnapshot(version, NOW, {"USD": AssetSpec(D(1), D(1))},
                              {"BTC-PERP": InstrumentSpec(D(100), D(".1"), D(".05"))})

    def activate(self):
        self.router.publish_market(self.market())
        self.router.set_kill_switch(False)

    def name_on(self, shard, prefix="account"):
        return next(f"{prefix}{index}" for index in range(1000)
                    if self.router.shard_for(f"{prefix}{index}") == shard)

    def fund(self, shard):
        name = self.name_on(shard)
        self.router.create_account(name)
        self.router.deposit(name, "seed", "USD", D(1000))
        return name

    def child(self, code, *arguments, path=None):
        import uta.sharding
        repository = Path(uta.sharding.__file__).resolve().parent.parent
        return subprocess.run([sys.executable, "-c", code, str(path or self.path), NOW.isoformat(),
                               *arguments], cwd=repository, capture_output=True,
                              text=True, timeout=20)

    def assert_rejected(self, code, function, *args, **kwargs):
        with self.assertRaises(ServiceError) as failure:
            function(*args, **kwargs)
        self.assertEqual(failure.exception.code, code)
        return failure.exception

    def test_runtime_shard_exchange_is_rejected_before_any_account_mutation(self):
        self.activate()
        target = self.name_on(1)
        # Simulate an operator placing the wrong valid database at this index.
        # It has valid local journal hashes and still must not become shard 1.
        shutil.copyfile(self.router._path(0), self.router._path(1))
        rejected = self.assert_rejected("shard_identity_conflict", self.router.create_account, target)
        self.assertEqual(rejected.status, 503)
        self.assertTrue(self.router._state()["halted"])
        with sqlite3.connect(self.router._path(1)) as connection:
            self.assertEqual(connection.execute("SELECT COUNT(*) FROM uta_accounts WHERE account_id=?",
                                                (target,)).fetchone()[0], 0)

    def test_runtime_missing_shard_is_not_recreated_as_an_empty_database(self):
        self.activate()
        account = self.fund(1)
        self.router._path(1).unlink()
        rejected = self.assert_rejected("shard_unavailable", self.router.account, account)
        self.assertEqual(rejected.status, 503)
        self.assertTrue(self.router._state()["halted"])
        self.assertFalse(self.router._path(1).exists(), "a running router must not recreate missing financial state")

    def test_restored_older_control_cannot_reuse_an_already_booked_funding_proof(self):
        self.activate()
        old_control = Path(self.temporary.name) / "control-before-funding.sqlite3"
        backup_database(self.router.control.path, old_control)
        self.router.fund_credit_pool(0, "first", "USD", D(10), source_reference="custody:tx:line-1")
        self.assertEqual(self.router._services[0].ledger.balance("system:credit-pool", "USD"), D(10))
        # Deliberately inconsistent offline restore. This is forbidden by the
        # runbook; startup must detect it rather than silently permit double cash.
        self.assertEqual(list(self.path.glob("router.sqlite3-*")), [])
        shutil.copyfile(old_control, self.router.control.path)
        rejected = self.assert_rejected("funding_registry_conflict", self.reopen)
        self.assertEqual(rejected.status, 503)
        with sqlite3.connect(self.router.control.path) as connection:
            state = json.loads(connection.execute("SELECT payload FROM router_state WHERE singleton=1").fetchone()[0])
            self.assertTrue(state["halted"])
        with sqlite3.connect(self.router._path(1)) as connection:
            self.assertEqual(connection.execute("SELECT COUNT(*) FROM ledger_events").fetchone()[0], 0)

    def test_detected_market_barrier_mismatch_persists_halt_before_returning_error(self):
        self.activate()
        account = self.fund(0)
        # This writer bypass is explicitly outside the router's protocol. It
        # emulates a bad shard restore; after detecting it, the control plane
        # must not retain an earlier global active flag.
        self.router._services[0].publish_market(self.market(2))
        self.assert_rejected("market_barrier_mismatch", self.router.set_kill_switch, False)
        self.assertTrue(self.router._state()["halted"])
        self.assert_rejected("router_halted", self.router.submit_order,
                             account, "after-detected-mismatch", "BTC-PERP", D(1), D(100))
        self.assertEqual(self.router.orders(account), [])

    def test_crash_after_global_proof_claim_preserves_exact_ownership_on_restart(self):
        code = r'''
import os, sys
from datetime import datetime
from decimal import Decimal as D
from uta.credit import CreditService
from uta.sharding import ShardRouter
router = ShardRouter(sys.argv[1], 2, {"USD":8}, clock=lambda:datetime.fromisoformat(sys.argv[2]))
def exit_before_local_book(*args, **kwargs):
    os._exit(81)
CreditService.fund_pool = exit_before_local_book
router.fund_credit_pool(0, "pending", "USD", D(10), source_reference="custody:claim:line-1")
'''
        result = self.child(code)
        self.assertEqual(result.returncode, 81, result.stderr)
        restarted = self.reopen()
        self.assert_rejected("funding_source_conflict", restarted.fund_credit_pool,
                             1, "other", "USD", D(10), source_reference="custody:claim:line-1")
        once = restarted.fund_credit_pool(0, "pending", "USD", D(10), source_reference="custody:claim:line-1")
        self.assertEqual(restarted.fund_credit_pool(0, "pending", "USD", D("10.0"),
                                                   source_reference="custody:claim:line-1"), once)
        self.assertEqual(restarted._services[0].ledger.balance("system:credit-pool", "USD"), D(10))
        self.assertEqual(restarted._services[1].ledger.balance("system:credit-pool", "USD"), D(0))

    def test_crash_after_local_funding_commit_does_not_reassign_its_global_proof(self):
        code = r'''
import os, sys
from datetime import datetime
from decimal import Decimal as D
from uta.credit import CreditService
from uta.sharding import ShardRouter
router = ShardRouter(sys.argv[1], 2, {"USD":8}, clock=lambda:datetime.fromisoformat(sys.argv[2]))
original = CreditService.fund_pool
def exit_after_local_book(self, *args, **kwargs):
    original(self, *args, **kwargs)
    os._exit(82)
CreditService.fund_pool = exit_after_local_book
router.fund_credit_pool(0, "funded", "USD", D(10), source_reference="custody:committed:line-1")
'''
        result = self.child(code)
        self.assertEqual(result.returncode, 82, result.stderr)
        restarted = self.reopen()
        self.assert_rejected("funding_source_conflict", restarted.fund_credit_pool,
                             1, "other", "USD", D(10), source_reference="custody:committed:line-1")
        result = restarted.fund_credit_pool(0, "funded", "USD", D(10), source_reference="custody:committed:line-1")
        self.assertEqual(result["amount"], "10")
        self.assertEqual(restarted._services[0].ledger.balance("system:credit-pool", "USD"), D(10))

    def test_process_exit_during_market_fanout_keeps_all_router_instances_closed(self):
        self.activate()
        account = self.fund(0)
        code = r'''
import os, sys
from datetime import datetime
from decimal import Decimal as D
from uta.market import MarketSnapshot
from uta.models import AssetSpec, InstrumentSpec
from uta.sharding import ShardRouter
now = datetime.fromisoformat(sys.argv[2])
router = ShardRouter(sys.argv[1], 2, {"USD":8}, clock=lambda:now)
def fail_next_shard(snapshot):
    os._exit(83)
router._services[1].publish_market = fail_next_shard
router.publish_market(MarketSnapshot(2, now, {"USD":AssetSpec(D(1),D(1))},
                    {"BTC-PERP":InstrumentSpec(D(101),D('.1'),D('.05'))}))
'''
        result = self.child(code)
        self.assertEqual(result.returncode, 83, result.stderr)
        restarted = self.reopen()
        for router in (self.router, restarted):
            self.assert_rejected("router_halted", router.submit_order, account, "blocked", "BTC-PERP", D(1), D(100))
            self.assert_rejected("publication_incomplete", router.set_kill_switch, False)
            self.assertTrue(router.diagnostics()["state"]["publishing"])
        restarted.publish_market(self.market(3))
        self.assertFalse(restarted.diagnostics()["ready"])
        restarted.set_kill_switch(False)
        self.assertEqual(restarted.submit_order(account, "recovered", "BTC-PERP", D(1), D(100))["status"], "OPEN")

    def test_process_exit_during_activation_cannot_bypass_global_halt(self):
        self.router.publish_market(self.market())
        account = self.fund(0)
        code = r'''
import os, sys
from datetime import datetime
from uta.sharding import ShardRouter
router = ShardRouter(sys.argv[1], 2, {"USD":8}, clock=lambda:datetime.fromisoformat(sys.argv[2]))
def fail_second_activation(enabled):
    os._exit(84)
router._services[1].set_kill_switch = fail_second_activation
router.set_kill_switch(False)
'''
        result = self.child(code)
        self.assertEqual(result.returncode, 84, result.stderr)
        restarted = self.reopen()
        self.assertTrue(restarted.diagnostics()["state"]["halted"])
        # Even though one local flag was opened, every cooperating router sees
        # the persisted global halt and refuses to authorize new exposure.
        self.assertTrue(restarted._services[0].readiness()["ready"])
        for router in (self.router, restarted):
            self.assert_rejected("router_halted", router.submit_order, account, "blocked", "BTC-PERP", D(1), D(100))
        restarted.set_kill_switch(False)
        self.assertEqual(restarted.submit_order(account, "allowed", "BTC-PERP", D(1), D(100))["status"], "OPEN")

    def test_process_exit_during_initial_layout_does_not_silently_create_missing_shards(self):
        path = Path(self.temporary.name) / "incomplete"
        code = r'''
import os, sys
from datetime import datetime
from uta.service import ExchangeService
from uta.sharding import ShardRouter
original = ExchangeService.__init__
def stop_during_initialization(self, database, *args, **kwargs):
    if database.path.endswith("shard-0001.sqlite3"):
        os._exit(85)
    return original(self, database, *args, **kwargs)
ExchangeService.__init__ = stop_during_initialization
ShardRouter(sys.argv[1], 2, {"USD":8}, clock=lambda:datetime.fromisoformat(sys.argv[2]))
'''
        result = self.child(code, path=path)
        self.assertEqual(result.returncode, 85, result.stderr)
        self.assertTrue((path / "shard-0000.sqlite3").exists())
        self.assertFalse((path / "shard-0001.sqlite3").exists())
        self.assert_rejected("shard_unavailable", ShardRouter, path, 2, {"USD": 8}, clock=lambda: NOW)
        self.assertFalse((path / "shard-0001.sqlite3").exists())

    def test_exclusive_halt_in_another_process_waits_for_inflight_routed_admission(self):
        self.activate()
        account = self.fund(0)
        entered = Path(self.temporary.name) / "admission-entered"
        release = Path(self.temporary.name) / "release-admission"
        accepted = Path(self.temporary.name) / "admission-committed"
        halted = Path(self.temporary.name) / "halt-committed"
        code = r'''
import json, sys, time
from pathlib import Path
from datetime import datetime
from decimal import Decimal as D
from uta.sharding import ShardRouter
router = ShardRouter(sys.argv[1], 2, {"USD":8}, clock=lambda:datetime.fromisoformat(sys.argv[2]))
if sys.argv[3] == "admit":
    account = sys.argv[4]
    service = router._services[router.shard_for(account)]
    original = service.submit_order
    def wait_with_shared_gate(*args, **kwargs):
        Path(sys.argv[5]).touch()
        deadline = time.monotonic() + 10
        while not Path(sys.argv[6]).exists():
            if time.monotonic() > deadline:
                raise RuntimeError("test admission release timed out")
            time.sleep(.01)
        result = original(*args, **kwargs)
        Path(sys.argv[7]).touch()
        return result
    service.submit_order = wait_with_shared_gate
    print(json.dumps(router.submit_order(account,"before-halt","BTC-PERP",D(1),D(100))),flush=True)
else:
    result = router.set_kill_switch(True)
    Path(sys.argv[5]).touch()
    print(json.dumps(result),flush=True)
'''
        import uta.sharding
        repository = Path(uta.sharding.__file__).resolve().parent.parent
        arguments = [sys.executable, "-c", code, str(self.path), NOW.isoformat()]
        admission = subprocess.Popen(arguments + ["admit", account, str(entered), str(release), str(accepted)],
                                     cwd=repository, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        self.addCleanup(lambda: admission.kill() if admission.poll() is None else None)
        deadline = monotonic() + 10
        while not entered.exists() and admission.poll() is None and monotonic() < deadline:
            sleep(.01)
        self.assertTrue(entered.exists(), "admission must hold the shared gate before halt starts")
        halt = subprocess.Popen(arguments + ["halt", account, str(halted)], cwd=repository,
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        self.addCleanup(lambda: halt.kill() if halt.poll() is None else None)
        sleep(.15)
        self.assertIsNone(halt.poll(), "the other process must not cross an active shared gate")
        self.assertFalse(halted.exists())
        release.touch()
        admission_out, admission_error = admission.communicate(timeout=20)
        halt_out, halt_error = halt.communicate(timeout=20)
        self.assertEqual(admission.returncode, 0, admission_error)
        self.assertEqual(halt.returncode, 0, halt_error)
        self.assertEqual(json.loads(admission_out)["status"], "OPEN")
        self.assertTrue(json.loads(halt_out)["halted"])
        self.assertTrue(accepted.exists())
        self.assertTrue(halted.exists())
        self.assertTrue(self.router._state()["halted"])
        self.assert_rejected("router_halted", self.router.submit_order,
                             account, "after-halt", "BTC-PERP", D(1), D(100))


if __name__ == "__main__":
    unittest.main()
