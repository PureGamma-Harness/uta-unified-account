"""Run the real synthetic multi-service chain with both caches enabled."""
from decimal import Decimal as D
import unittest
from unittest.mock import patch

from uta.service import ExchangeService
from uta.vertical import run_vertical_acceptance


class CachedVerticalAcceptanceTests(unittest.TestCase):
    def test_classic_credit_spot_paired_liquidation_and_restart_with_warm_caches(self):
        services = []
        def enabled_service(*args, **kwargs):
            service = ExchangeService(*args, reserve_cache_size=32, market_cache_size=4, **kwargs)
            services.append(service)
            return service
        # Only construction selects real opt-in settings. Ledger, debt, spot,
        # matching, liquidation, durable restart and reconciliation stay real.
        with patch("uta.vertical.ExchangeService", side_effect=enabled_service):
            result = run_vertical_acceptance()
        self.assertEqual(result["status"], "passed")
        self.assertFalse(result["production_approved"])
        self.assertFalse(result["source_fence_verified"])
        self.assertEqual(result["linear_matches"], 3)
        self.assertEqual(result["spot_matches"], 2)
        self.assertEqual(D(result["final_balances"]["USD"]), D("93.152"))
        self.assertEqual(D(result["final_balances"]["BTC"]), D(".999"))
        self.assertGreaterEqual(len(services), 2, "the chain must actually reopen authority storage")
        self.assertTrue(any(service.reserve_cache_stats()["hits"] for service in services))
        self.assertTrue(any(service.market_cache_stats()["hits"] for service in services))
        self.assertTrue(all(service.reserve_cache_stats()["capacity"] == 32 and
                            service.market_cache_stats()["capacity"] == 4 for service in services))
