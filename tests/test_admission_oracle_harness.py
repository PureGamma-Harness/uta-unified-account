"""Check evidence classification without executing the command matrix."""
from contextlib import redirect_stdout
import io
import json
import unittest
from unittest.mock import patch
from tools import check_admission_oracle as harness


def result(*, skipped=False, error=None):
    item = unittest.FunctionTestCase(lambda: None)
    value = unittest.TestResult()
    value.startTest(item)
    if skipped:
        value.addSkip(item, "not executed")
    elif error:
        value.errors.append((item, error))
    else:
        value.addSuccess(item)
    value.stopTest(item)
    return value


class AdmissionOracleHarnessTests(unittest.TestCase):
    def test_skipped_or_not_run_is_not_positive_evidence(self):
        self.assertFalse(harness.details(unittest.TestResult())["passed"])
        self.assertFalse(harness.details(result(skipped=True))["passed"])
        self.assertTrue(harness.details(result())["passed"])

    def classify(self, positive, negative):
        output = io.StringIO()
        with patch.object(harness, "SEEDS", (0,)), patch.object(harness, "BATCH_SIZES", (1,)):
            with patch.object(harness, "run_case", side_effect=[positive, negative]), redirect_stdout(output):
                status = harness.main()
        return status, json.loads(output.getvalue())

    def test_unrelated_negative_failure_is_not_detection(self):
        status, report = self.classify(result(), result(error="ImportError: fixture missing"))
        self.assertEqual(status, 1)
        self.assertFalse(report["negative_control"]["expected_failure_detected"])

    def test_expected_negative_does_not_hide_skipped_positive(self):
        trace = 'future.result(timeout=10)["status"]\ninsufficient available margin for order and fee reserve'
        status, report = self.classify(result(skipped=True), result(error=trace))
        self.assertEqual(status, 1)
        self.assertTrue(report["negative_control"]["expected_failure_detected"])
        self.assertFalse(report["all_passed"])

    def test_expected_negative_and_real_positive_are_classified_separately(self):
        trace = 'future.result(timeout=10)["status"]\ninsufficient available margin for order and fee reserve'
        status, report = self.classify(result(), result(error=trace))
        self.assertEqual(status, 0)
        self.assertTrue(report["all_passed"])
        self.assertFalse(report["negative_control"]["passed"])

    def test_expected_failure_is_not_positive_evidence(self):
        expected = result()
        expected.expectedFailures.append((unittest.FunctionTestCase(lambda: None),
                                          "documented failing oracle case"))
        self.assertTrue(expected.wasSuccessful())  # unittest's own convention
        report = harness.details(expected)
        self.assertFalse(report["passed"])
        self.assertEqual(report["expected_failures"], 1)
        trace = 'future.result(timeout=10)["status"]\ninsufficient available margin for order and fee reserve'
        status, matrix = self.classify(expected, result(error=trace))
        self.assertEqual(status, 1)
        self.assertFalse(matrix["all_passed"])
