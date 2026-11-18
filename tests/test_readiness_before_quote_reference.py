"""Pure reference cases for test orchestration, with no UTA/SQLite/process use.

These cases cannot validate native owner readiness. They check that the fixture
retains a failed first observation and never creates a quote in its place.
"""
from copy import deepcopy
from threading import RLock
import unittest
from unittest.mock import Mock, patch

from readiness_before_quote import complete_owner_observation, current_quote_after_owner_ready


def owner_observation():
    return {"state_observed": True, "supervisor_alive": True, "workers_alive": True,
        "ready": False, "financial_ready": False, "reason": "publication_incomplete",
        "state": {"halted": True, "publishing": False, "market_version": None},
        "workers": [{"shard": shard, "pid": 100 + shard, "owner_pid": 100 + shard,
            "generation": 3, "alive": True, "lease_active": True, "owner_ready": True,
            "market_ready": False, "funding_registry_ready": False,
            "reason": "market_missing",
            "report": {"state": "ready", "shard": shard, "pid": 100 + shard, "generation": 3}}
            for shard in range(2)]}


class RouterDouble:
    def __init__(self, observations):
        self.layout = {"shard_count": 2}
        self._mutex = RLock()
        self._workers = {shard: (Mock(pid=100 + shard, is_alive=Mock(return_value=True)),)
                         for shard in range(2)}
        self._reports = {row["shard"]: row["report"] for row in owner_observation()["workers"]}
        self.diagnostics = Mock(side_effect=observations)


class BeforeQuoteReferenceTests(unittest.TestCase):
    def test_first_unknown_is_retained_without_a_second_observation_or_quote(self):
        unknown = {"ready": False, "financial_ready": False, "state_observed": False,
            "reason": "diagnostic_timeout", "workers": []}
        router = RouterDouble([unknown, owner_observation()])
        make_quote = Mock()
        with self.assertRaisesRegex(AssertionError, "first before-quote owner observation failed"):
            current_quote_after_owner_ready(self, router, make_quote)
        self.assertEqual(router.diagnostics.call_count, 1)
        make_quote.assert_not_called()
        self.assertEqual(self.owner_before_quote_evidence["native_observations"], [unknown])
        self.assertNotIn("witness_utc", self.owner_before_quote_evidence)

    def test_complete_owner_witness_precedes_factory_without_promoting_financial_ready(self):
        observation = owner_observation()
        original = deepcopy(observation)
        router = RouterDouble([observation])
        quote = object()
        def make_quote():
            self.assertEqual(router.diagnostics.call_count, 1)
            self.assertEqual(self.owner_before_quote_evidence["native_observations"], [original])
            self.assertIn("witness_utc", self.owner_before_quote_evidence)
            return quote
        self.assertIs(current_quote_after_owner_ready(self, router, make_quote), quote)
        self.assertEqual(observation, original)
        self.assertFalse(observation["ready"])
        self.assertFalse(observation["financial_ready"])

    def test_stale_generation_and_inactive_owner_are_not_a_complete_witness(self):
        for field, value in (("owner_pid", 999), ("lease_active", False),
                             ("owner_ready", False), ("generation", 4)):
            with self.subTest(field=field):
                observation = owner_observation()
                observation["workers"][0][field] = value
                self.assertFalse(complete_owner_observation(observation, (0, 1)))

    def test_unknown_after_owner_fields_were_read_still_fails_the_single_attempt(self):
        for scope in ("top_timeout", "row_timeout", "row_guard_error"):
            with self.subTest(scope=scope):
                observation = owner_observation()
                if scope == "top_timeout":
                    observation.update(reason="diagnostic_timeout", observation_error={"type": "service_error"})
                else:
                    observation["workers"][0]["reason"] = (
                        "diagnostic_timeout" if scope == "row_timeout" else "shard_unavailable")
                router, make_quote = RouterDouble([observation, owner_observation()]), Mock()
                with self.assertRaisesRegex(AssertionError, "first before-quote owner observation failed"):
                    current_quote_after_owner_ready(self, router, make_quote)
                self.assertEqual(router.diagnostics.call_count, 1)
                make_quote.assert_not_called()
                self.assertEqual(self.owner_before_quote_evidence["native_observations"], [observation])

    def test_unconsumed_current_ready_frame_cannot_trigger_diagnostic_or_quote(self):
        router = RouterDouble([owner_observation()])
        router._reports[0]["pid"] = 99
        make_quote, clock = Mock(), [0.0]
        def advance(seconds):
            clock[0] += seconds
        with patch("readiness_before_quote.monotonic", side_effect=lambda: clock[0]), \
             patch("readiness_before_quote.sleep", side_effect=advance):
            with self.assertRaisesRegex(AssertionError, "before-quote READY frame budget exhausted"):
                current_quote_after_owner_ready(self, router, make_quote, timeout=.02)
        router.diagnostics.assert_not_called()
        make_quote.assert_not_called()
        self.assertEqual(self.owner_before_quote_evidence["native_observations"], [])

    def test_late_native_return_retains_report_without_quote_or_second_observation(self):
        for completed in (1.0, 1.01):
            with self.subTest(completed=completed):
                observation, clock = owner_observation(), [0.0]
                router, make_quote = RouterDouble([]), Mock()
                def return_late(**kwargs):
                    clock[0] = completed
                    return observation
                router.diagnostics = Mock(side_effect=return_late)
                with patch("readiness_before_quote.monotonic", side_effect=lambda: clock[0]):
                    with self.assertRaisesRegex(AssertionError, "completed outside total budget"):
                        current_quote_after_owner_ready(self, router, make_quote, timeout=1)
                self.assertEqual(router.diagnostics.call_count, 1)
                make_quote.assert_not_called()
                self.assertEqual(self.owner_before_quote_evidence["native_observations"], [observation])
                self.assertEqual(self.owner_before_quote_evidence["native_completed_monotonic"], completed)
                self.assertNotIn("witness_utc", self.owner_before_quote_evidence)

    def test_identity_equality_requires_native_integer_types(self):
        for scope, field, value in (("row", "shard", False), ("row", "owner_pid", 100.0),
                                    ("row", "generation", 3.0), ("frame", "shard", False),
                                    ("frame", "pid", 100.0), ("frame", "generation", 3.0)):
            with self.subTest(scope=scope, field=field):
                observation = owner_observation()
                target = observation["workers"][0]
                if scope == "frame":
                    target = target["report"]
                target[field] = value
                self.assertFalse(complete_owner_observation(observation, (0, 1)))
        router, make_quote, clock = RouterDouble([owner_observation()]), Mock(), [0.0]
        router._reports[0]["pid"] = 100.0
        def advance(seconds):
            clock[0] += seconds
        with patch("readiness_before_quote.monotonic", side_effect=lambda: clock[0]), \
             patch("readiness_before_quote.sleep", side_effect=advance):
            with self.assertRaisesRegex(AssertionError, "before-quote READY frame budget exhausted"):
                current_quote_after_owner_ready(self, router, make_quote, timeout=.02)
        router.diagnostics.assert_not_called()
        make_quote.assert_not_called()


if __name__ == "__main__":
    unittest.main()
