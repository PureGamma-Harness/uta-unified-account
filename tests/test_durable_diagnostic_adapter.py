"""Real HTTP adapter contract for bounded and partially failed diagnostics."""
from http.client import HTTPConnection
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from threading import Thread
import unittest
from unittest.mock import patch

from uta.durable_gateway import make_server
from uta.durable_process import DurableProcessRouter
from uta.gateway import Credential


RISK, READER = "K" * 43, "R" * 43


class DurableDiagnosticAdapterTests(unittest.TestCase):
    def setUp(self):
        self.directory = TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.router = DurableProcessRouter.initialize(Path(self.directory.name) / "managed", 1,
                                                     {"USD": 8}, managed=True)
        self.addCleanup(self.router.close)
        self.server = make_server(self.router, port=0, credentials=(Credential(RISK, "risk"), Credential(READER, "reader", "alice")))
        thread = Thread(target=self.server.serve_forever, kwargs={"poll_interval": .01})
        thread.start()
        def close():
            self.server.shutdown(); self.server.server_close(); thread.join(3)
        self.addCleanup(close)

    def request(self, path="/v2/worker-health", token=RISK):
        connection = HTTPConnection(*self.server.server_address, timeout=3)
        try:
            connection.request("GET", path, headers={"Authorization": "Bearer " + token})
            response = connection.getresponse()
            return response.status, json.loads(response.read())
        finally:
            connection.close()

    def test_unknown_control_is_nullable_and_never_promoted_from_worker_liveness(self):
        base = {"state": None, "state_observed": False, "workers": [], "managed": True,
                "workers_alive": True, "ready": False, "financial_ready": False, "reason": "diagnostic_timeout"}
        for observed in (base, {**base, "ready": True, "financial_ready": True}, {**base, "state": {}}):
            with patch.object(self.router, "diagnostics", return_value=observed):
                status, data = self.request()
                self.assertEqual(status, 200, data)
                self.assertIsNone(data["control"])
                self.assertFalse(data["control_observed"])
                self.assertFalse(data["ready"])
                self.assertFalse(data["financial_ready"])
                self.assertFalse(data["dispatch_available"])
                self.assertTrue(data["workers_alive"])
                self.assertEqual(data["reason"], "diagnostic_timeout")

    def test_stale_market_details_remain_false_and_sensitive_reason_text_is_not_echoed(self):
        observed = {"state": {"halted": False, "publishing": False, "epoch": 2, "market_version": 7,
                               "error": "/private/control/path"}, "state_observed": True,
                    "workers": [{"shard": 0, "pid": 123, "owner_pid": 123, "lease_active": True,
                                 "generation": 2, "alive": True, "market_ready": False,
                                 "market_version": 7, "market_observed_at": "2026-11-17T00:00:00+00:00",
                                 "reason": "market_stale", "report": {"path": "/private/raw-report"}}],
                    "managed": True, "workers_alive": True, "ready": False, "financial_ready": False,
                    "reason": "market_stale"}
        with patch.object(self.router, "diagnostics", return_value=observed):
            status, data = self.request("/v2/metrics")
        self.assertEqual(status, 200, data)
        diagnostic = data["durable"]
        self.assertTrue(diagnostic["control_observed"])
        self.assertFalse(diagnostic["financial_ready"])
        self.assertFalse(diagnostic["workers"][0]["market_ready"])
        self.assertEqual(diagnostic["workers"][0]["reason"], "market_stale")
        self.assertNotIn("/private", json.dumps(data))

    def test_legacy_ready_does_not_claim_new_financial_observation_and_scope_precedes_read(self):
        observed = {"state": {"halted": False, "publishing": False, "epoch": 1, "market_version": 1,
                               "error": None}, "workers": [], "managed": True, "ready": True}
        with patch.object(self.router, "diagnostics", return_value=observed) as read:
            status, _ = self.request(token=READER)
            self.assertEqual(status, 403)
            read.assert_not_called()
            status, data = self.request()
        self.assertEqual(status, 200, data)
        self.assertTrue(data["dispatch_available"])
        self.assertFalse(data["ready"])
        self.assertFalse(data["financial_ready"])
        self.assertEqual(data["readiness_source"], "legacy_process_control_only")


if __name__ == "__main__":
    unittest.main()
