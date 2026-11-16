"""Bounded bridge to the in-memory book, NOT the durable trading authority."""
from collections import deque
from decimal import Decimal
import unittest
from unittest.mock import patch

from formal.explore_reservation import State, next_states
from uta.reservations import ReservationBook, VersionConflict, InsufficientMargin


def apply_edge(book, before, action, after):
    if not action.startswith("begin"):
        index = next(i for i in range(3) if before.phase[i] != after.phase[i])
        identifier = f"o{index + 1}"
        if action.startswith("commit"):
            book.reserve(identifier, Decimal(before.amount[index]), expected_version=before.seen[index])
        elif action.startswith("release"):
            book.release(identifier, expected_version=before.version)
        elif action.startswith("reject"):
            snapshot = book.snapshot()
            expected = VersionConflict if before.seen[index] != before.version else InsufficientMargin
            try:
                book.reserve(identifier, Decimal(before.amount[index]), expected_version=before.seen[index])
            except expected:
                pass
            else:
                raise AssertionError("modeled rejection was accepted")
            if book.snapshot() != snapshot:
                raise AssertionError("rejection mutated the book")
        else:
            raise AssertionError(action)
    snapshot = book.snapshot()
    if (snapshot.version, snapshot.reserved, snapshot.available) != (
            after.version, sum(after.held), 2 - sum(after.held)):
        raise AssertionError("modeled state differs from book snapshot")


class ReservationModelBridgeTests(unittest.TestCase):
    def test_every_bounded_transition_matches_in_memory_book(self):
        initial = State()
        paths, queue = {initial: []}, deque([initial])
        while queue:
            before = queue.popleft()
            for action, after in next_states(before, unsafe=False):
                if after not in paths:
                    paths[after] = paths[before] + [(before, action, after)]
                    queue.append(after)
        checked = 0
        for before, path in paths.items():
            for action, after in next_states(before, unsafe=False):
                book = ReservationBook(Decimal(2))
                for source, step, target in path:
                    apply_edge(book, source, step, target)
                apply_edge(book, before, action, after)
                checked += 1
        self.assertEqual((len(paths), checked), (2628, 3873))

    def test_bridge_detects_a_version_guard_mutant(self):
        book = ReservationBook(Decimal(2))
        before = State(phase=("held", "pending", "idle"), seen=(0, 0, 0),
                       amount=(1, 1, 0), held=(1, 0, 0), version=1)
        book.reserve("o1", Decimal(1), expected_version=0)
        action, after = next((a, n) for a, n in next_states(before, unsafe=False)
                             if a == "reject(o2)")
        with patch.object(book, "_check_version", return_value=None):
            with self.assertRaisesRegex(AssertionError, "modeled rejection was accepted"):
                apply_edge(book, before, action, after)
