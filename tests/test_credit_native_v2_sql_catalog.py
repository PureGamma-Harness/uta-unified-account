"""Actual effect-DDL compilation only; positive native acceptance is separate."""
import unittest

from tests.test_credit_native_v2_primitives import component
from uta import credit_native_v2 as native


class CreditV2EffectCatalogTests(unittest.TestCase):
    def test_all_compiled_effect_gates_create_on_actual_core_parent_catalog(self):
        with component() as (_, con):
            con.execute("BEGIN IMMEDIATE")
            for name, (_, sql) in native.EFFECT_TRIGGER_SQL.items():
                con.execute(sql)
            con.commit()
            installed = {row[0]: row[1] for row in con.execute(
                "SELECT name,sql FROM sqlite_master WHERE name LIKE 'credit_v2_gate_%'")}
            self.assertEqual(installed, {name: sql for name, (_, sql) in native.EFFECT_TRIGGER_SQL.items()})
            self.assertEqual(len(installed), 22)
            self.assertEqual(con.execute("PRAGMA foreign_key_check").fetchall(), [])
            self.assertEqual(con.execute("SELECT COUNT(*) FROM uta_credit_decisions").fetchone()[0], 0)
            self.assertEqual(con.execute("SELECT COUNT(*) FROM credit_commands").fetchone()[0], 0)
            # This explicitly does not register successful callbacks, create a
            # capability, claim an owner or execute a new borrowing operation.

    def test_effects_and_catalog_have_separate_exact_object_inventories(self):
        self.assertEqual(set(native.OBJECT_SQL), set(native.CATALOG_OBJECT_SQL) | set(native.EFFECT_TRIGGER_SQL))
        self.assertEqual(len(native.OBJECT_SQL), 48)
        self.assertTrue(all("uta_credit_v2_deny" in sql for _, sql in native.EFFECT_TRIGGER_SQL.values()))
