"""Storage idempotency namespaces only; not API tenant authorization."""
from decimal import Decimal as D
import unittest
import test_service_catalog as fixture_module
from uta.service import ServiceError


class AccountScopedReplayTests(unittest.TestCase):
    def test_identical_ids_are_independent_across_accounts_after_restart(self):
        fixture = fixture_module.ServiceCatalogTests()
        fixture.setUp()
        self.addCleanup(fixture.doCleanups)
        service = fixture.funded()
        service.create_account('bob')
        service.deposit('bob', 'funds', 'USD', D('2000'))
        for account, quantity in [('alice', '1'), ('bob', '2')]:
            service.submit_order(account, 'shared-order', 'X', D(quantity), D('100'))
            service.apply_fill(account, 'shared-order', 'shared-fill', D(quantity), D('100'))
        def snapshot():
            with service.database.transaction() as connection:
                return '\n'.join(connection.iterdump())
        with service.database.transaction() as connection:
            rows = connection.execute('SELECT account_id,quantity FROM uta_fills ORDER BY account_id').fetchall()
            self.assertEqual([(row[0], D(row[1])) for row in rows], [('alice', D('1')), ('bob', D('2'))])
        before = snapshot()
        service = fixture.create()
        for account, quantity in [('alice', '1.00'), ('bob', '2.00')]:
            service.submit_order(account, 'shared-order', 'X', D(quantity), D('100.00'))
            service.apply_fill(account, 'shared-order', 'shared-fill', D(quantity), D('100.00'))
        self.assertEqual(snapshot(), before)
        for account, other_quantity in [('alice', '2'), ('bob', '1')]:
            with self.subTest(account=account):
                with self.assertRaises(ServiceError) as rejected:
                    service.apply_fill(account, 'shared-order', 'shared-fill', D(other_quantity), D('100'))
                self.assertEqual(rejected.exception.code, 'idempotency_conflict')
                self.assertEqual(snapshot(), before)
        service.ledger.verify()
