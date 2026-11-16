"""Loopback routing regression with a fake service, not deployment auth proof."""
import unittest
import test_gateway as fixture_module


class GatewayPathScopeTests(unittest.TestCase):
    def test_foreign_and_ambiguous_account_paths_never_dispatch(self):
        fixture = fixture_module.GatewayTests()
        fixture.setUp()
        self.addCleanup(fixture.doCleanups)
        paths = (
            '/v1/accounts/bob',
            '/v1/accounts/%62ob',
            '/v1/accounts/alice/../bob',
            '/v1/accounts/alice%2f..%2fbob',
            '/v1/accounts//bob',
            '/v1/accounts/bob?account_id=alice',
            '/v1/accounts/bob#alice',
        )
        for path in paths:
            with self.subTest(path=path):
                before = list(fixture.service.calls)
                status, _, _ = fixture.request('GET', path, token=fixture_module.ALICE)
                self.assertIn(status, (400, 403, 404))
                self.assertEqual(fixture.service.calls, before)
        # The positive control prevents a universally rejecting server from passing.
        status, _, _ = fixture.request('GET', '/v1/accounts/alice', token=fixture_module.ALICE)
        self.assertEqual(status, 200)
        self.assertEqual(fixture.service.calls[-1], ('account', ('alice',), {}))

    def test_ambiguous_cancel_paths_do_not_reach_mutating_service(self):
        fixture = fixture_module.GatewayTests()
        fixture.setUp()
        self.addCleanup(fixture.doCleanups)
        for account_path in ('bob', '%62ob', 'alice/../bob', 'alice%2f..%2fbob', '/bob'):
            with self.subTest(account_path=account_path):
                before = list(fixture.service.calls)
                status, _, _ = fixture.request('POST', '/v1/accounts/' + account_path + '/orders/o1/cancel',
                                               {}, token=fixture_module.ALICE)
                self.assertIn(status, (400, 403, 404))
                self.assertEqual(fixture.service.calls, before)
        status, _, _ = fixture.request('POST', '/v1/accounts/alice/orders/o1/cancel',
                                       {}, token=fixture_module.ALICE)
        self.assertEqual(status, 200)
        self.assertEqual(fixture.service.calls[-1], ('cancel_order', ('alice', 'o1'), {}))
