"""Pure synthetic exception dispatch: no native DB or protocol reproduction."""
from pathlib import Path
import sqlite3
import unittest
from unittest.mock import patch

from tests.test_durable_faults import router_writer_available_without_dml


class ConnectionVector:
    total_changes = 0
    def __init__(self, error):
        self.error, self.closed = error, False
    def execute(self, sql):
        raise self.error
    def close(self):
        self.closed = True


class InjectedStopProbePolicyTests(unittest.TestCase):
    def vector(self, code, message="synthetic probe error"):
        error = sqlite3.OperationalError(message)
        error.sqlite_errorcode = code
        return error

    def probe(self, error, **kwargs):
        connection = ConnectionVector(error)
        with patch.object(sqlite3, "connect", return_value=connection):
            try:
                return router_writer_available_without_dml(Path("/synthetic-unused.sqlite3"), **kwargs)
            finally:
                self.assertTrue(connection.closed)

    def test_protocol_remains_fatal_without_owned_injected_stop(self):
        error = self.vector(15)
        with self.assertRaises(sqlite3.OperationalError) as caught:
            self.probe(error)
        self.assertIs(caught.exception, error)

    def test_only_owned_protocol_is_explicit_unobserved_technical_unknown(self):
        result = self.probe(self.vector(15), own_injected_stop=True)
        self.assertIs(result["available"], False)
        self.assertIs(result["lease_observed"], False)
        self.assertEqual(result["classification"], "technical_unknown_own_stop_protocol")
        self.assertEqual(result["native_errorcode"], 15)
        self.assertNotIn("active", result)

    def test_legacy_protocol_fallback_is_exact_and_owned_only(self):
        error = sqlite3.OperationalError("locking protocol")
        if hasattr(error, "sqlite_errorcode"):
            del error.sqlite_errorcode
        result = self.probe(error, own_injected_stop=True)
        self.assertIs(result["available"], False)
        self.assertIs(result["lease_observed"], False)
        with self.assertRaises(sqlite3.OperationalError):
            self.probe(error)

    def test_present_invalid_native_attribute_cannot_use_message_fallback(self):
        for code in (None, True, "15"):
            with self.subTest(code=code), self.assertRaises(sqlite3.OperationalError):
                self.probe(self.vector(code, "locking protocol"), own_injected_stop=True)

    def test_io_corruption_notadb_locked_and_other_errors_still_raise(self):
        for code in (10, 11, 26, 6, 1):
            error = self.vector(code)
            with self.subTest(code=code), self.assertRaises(sqlite3.OperationalError) as caught:
                self.probe(error, own_injected_stop=True)
            self.assertIs(caught.exception, error)

    def test_existing_busy_classification_does_not_require_a_stop_flag(self):
        for own in (False, True):
            with self.subTest(own=own):
                result = self.probe(self.vector(5), own_injected_stop=own)
                self.assertIs(result["available"], False)
                self.assertEqual(result["classification"], "sqlite_busy")

    def test_nonboolean_context_is_rejected_before_any_connection(self):
        for value in (None, 1, "true"):
            with self.subTest(value=value), patch.object(sqlite3, "connect") as connect:
                with self.assertRaises(ValueError):
                    router_writer_available_without_dml(Path("/synthetic-unused.sqlite3"), own_injected_stop=value)
                connect.assert_not_called()
