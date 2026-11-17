"""Observe real native SQL candidate evaluation; never grant or replace a gate."""
from decimal import Decimal as D
import json
import os
import sys
import unittest

from tests.credit_v2_runtime_fixture import SyntheticCreditAuthority
from uta.credit_native_v2 import _sql_gate


class HistoricalIntentProbe(unittest.TestCase):
    def test_later_real_repayment_ignores_nonmatching_historical_intent(self):
        # This probe must create and clean its own disposable database. It never
        # accesses the retained loan-only database used by independent review.
        self.assertNotIn("UTA_CREDIT_V2_PRIVATE_DB_DIRECTORY", os.environ)
        fixture = SyntheticCreditAuthority()
        self.addCleanup(fixture.close)
        fixture.install_and_open()
        fifo = fixture.fifo
        fifo.enqueue_borrow("alice", "loan-first", "BTC", D(".4"),
            actor_id="synthetic:gate-probe", source_reference="synthetic:gate-probe:loan")
        self.assertEqual(fifo.process_one()["state"], "SUCCEEDED")
        fifo.enqueue_repay("alice", "repay-second", "BTC", D(".1"),
            actor_id="synthetic:gate-probe", source_reference="synthetic:gate-probe:repay")
        observations = []
        def trace(frame, event, value):
            if frame.f_code is _sql_gate.__code__:
                if event == "exception":
                    error_type, error, _ = value
                    observations.append({"event": "exception", "phase": frame.f_locals.get("phase"),
                        "arguments": list(frame.f_locals.get("args", ())),
                        "type": error_type.__name__, "code": getattr(error, "code", None), "message": str(error)})
                elif event == "return" and value == 0:
                    observations.append({"event": "refused_candidate", "phase": frame.f_locals.get("phase"),
                        "arguments": list(frame.f_locals.get("args", ()))})
                return trace
            return None
        failure = None
        prior_trace = sys.gettrace()
        try:
            sys.settrace(trace)
            receipt = fifo.process_one()
        except Exception as error:
            failure = error
        finally:
            sys.settrace(prior_trace)
        with fixture.services.exchange.database.read_transaction() as connection:
            proof = {"inbox": [dict(row) for row in connection.execute(
                "SELECT command_id,state FROM uta_command_inbox ORDER BY sequence")],
                "intents": connection.execute("SELECT COUNT(*) FROM credit_v2_intents").fetchone()[0],
                "journals": connection.execute("SELECT COUNT(*) FROM ledger_events").fetchone()[0],
                "debt": [dict(row) for row in connection.execute("SELECT asset,principal,interest FROM uta_liabilities")],
                "foreign_key_check": [tuple(row) for row in connection.execute("PRAGMA foreign_key_check")]}
        print(json.dumps({"probe": "actual native scopes; trace observer only; disposable DB",
            "observations": observations, "post_commit_or_rollback_proof": proof}, sort_keys=True))
        if failure is not None:
            raise failure
        self.assertEqual((receipt["state"], receipt["result"]["principal"]), ("SUCCEEDED", "0.3"))


if __name__ == "__main__":
    unittest.main()
