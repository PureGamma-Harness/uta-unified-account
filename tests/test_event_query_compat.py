"""Version-independent empty event queries without relaxing nonempty input."""
import unittest
from unittest.mock import patch

from uta.gateway import _RequestError, _event_cursor


class EventQueryCompatibilityTests(unittest.TestCase):
    def test_omitted_query_uses_defaults_without_version_specific_parser_behavior(self):
        with patch("uta.gateway.parse_qsl", side_effect=ValueError("CPython 3.10 empty query")) as parse:
            self.assertEqual(_event_cursor(""), (0, 100))
            parse.assert_not_called()

    def test_explicit_cursors_and_percent_encoded_digits_remain_supported(self):
        for query, expected in (("after=0", (0, 100)), ("limit=1", (0, 1)),
                                ("after=2&limit=1000", (2, 1000)),
                                ("after=%30&limit=2", (0, 2)),
                                ("after=9223372036854775807", (2**63 - 1, 100))):
            with self.subTest(query=query):
                self.assertEqual(_event_cursor(query), expected)

    def test_nonempty_malformed_duplicate_and_out_of_range_queries_remain_rejected(self):
        for query in ("&", "after=1&", "&after=1", "after=1&&limit=2", "after", "limit=",
                      "after=0&after=1", "limit=1&limit=2", "other=1", "after=-1", "after=+1",
                      "after=%20", "after=１２", "after=9223372036854775808", "limit=0",
                      "limit=1001", "limit=1;after=2", "after=1%26limit%3D2", "%"):
            with self.subTest(query=query), self.assertRaises(_RequestError) as error:
                _event_cursor(query)
            self.assertEqual((error.exception.status, error.exception.code), (400, "invalid_query"))


if __name__ == "__main__":
    unittest.main()
