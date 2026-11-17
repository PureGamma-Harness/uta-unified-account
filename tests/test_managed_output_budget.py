"""Pure JSON and owned temporary output fixtures; no SQL or child processes."""
from copy import deepcopy
import unittest

from tools.managed_output_budget import GIB, explicit_output_budget, output_budget_bytes


class OutputBudgetPolicyTests(unittest.TestCase):
    def test_missing_field_preserves_six_gib_and_does_not_mutate_plan(self):
        plan = {'observer': {'blocks': 12}}
        before = deepcopy(plan)
        self.assertEqual(output_budget_bytes(plan), 6 * GIB)
        self.assertFalse(explicit_output_budget(plan))
        self.assertEqual(plan, before)

    def test_explicit_integer_byte_boundaries_and_future_two_gib(self):
        for value in (GIB, GIB + 1, 2 * GIB, 6 * GIB):
            with self.subTest(value=value):
                plan = {'observer': {'output_budget_bytes': value}}
                self.assertEqual(output_budget_bytes(plan), value)
                self.assertTrue(explicit_output_budget(plan))

    def test_rejects_out_of_range_values(self):
        for value in (-1, 0, 1, GIB - 1, 6 * GIB + 1):
            with self.subTest(value=value), self.assertRaisesRegex(ValueError, 'budget_bytes_invalid'):
                output_budget_bytes({'observer': {'output_budget_bytes': value}})

    def test_rejects_bool_float_string_null_and_containers(self):
        for value in (True, False, float(GIB), str(GIB), None, [], {}):
            with self.subTest(value=value), self.assertRaisesRegex(ValueError, 'budget_bytes_invalid'):
                output_budget_bytes({'observer': {'output_budget_bytes': value}})

    def test_rejects_missing_or_invalid_observer_metadata(self):
        for plan in (None, [], {}, {'observer': None}, {'observer': []}):
            with self.subTest(plan=plan), self.assertRaisesRegex(ValueError, 'budget_plan_invalid'):
                output_budget_bytes(plan)

    def test_future_reservation_arithmetic_is_not_a_qualification(self):
        new = 6 * GIB + output_budget_bytes({'observer': {'output_budget_bytes': 2 * GIB}}) + GIB + GIB
        self.assertEqual(new, 10_737_418_240)
        self.assertEqual(new + 6 * GIB + 256 * 1024**2, 17_448_304_640)


if __name__ == '__main__':
    unittest.main()
