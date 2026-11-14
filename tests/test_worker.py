import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from uta.storage import Database
from uta.worker import LeaseBusy, LeaseLost, OutboxConsumer, WorkerError


class Source:
    def __init__(self, sequences=(1, 2, 3)):
        self.rows = [{"sequence": sequence, "event_type": "test"} for sequence in sequences]

    def events(self, after=0, limit=100):
        return [row for row in self.rows if row["sequence"] > after][:limit]


class WorkerTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name) / "events.sqlite3"
        self.db = Database(self.path)
        self.now = datetime(2026, 11, 14, tzinfo=timezone.utc)
        self.seen = []

    def consumer(self, handler=None, **kwargs):
        return OutboxConsumer(Database(self.path), Source(), "audit", handler or self.seen.append,
                              clock=lambda: self.now, **kwargs)

    def test_cursor_survives_restart_and_subscriptions_are_independent(self):
        first = self.consumer(batch_size=2)
        self.assertEqual(first.run_once(), 2)
        restarted = self.consumer()
        self.assertEqual(restarted.cursor(), 2)
        self.assertEqual(restarted.run_once(), 1)
        self.assertEqual(restarted.run_once(), 0)
        self.assertEqual([e["sequence"] for e in self.seen], [1, 2, 3])
        other = OutboxConsumer(self.db, Source(), "risk", self.seen.append)
        self.assertEqual(other.run_once(), 3)

    def test_failure_redelivers_without_skipping_committed_checkpoint(self):
        def fail(event):
            self.seen.append(event)
            if event["sequence"] == 2:
                raise RuntimeError("sink unavailable after delivery")
        first = self.consumer(fail)
        with self.assertRaises(RuntimeError):
            first.run_once()
        self.assertEqual(first.cursor(), 1)
        self.assertEqual(self.consumer().run_once(), 2)
        self.assertEqual([e["sequence"] for e in self.seen], [1, 2, 2, 3])

    def test_handler_mutation_cannot_change_checkpoint_sequence(self):
        def annotate(event):
            event["sequence"] = 999
        consumer = self.consumer(annotate)
        self.assertEqual(consumer.run_once(), 3)
        self.assertEqual(consumer.cursor(), 3)

    def test_concurrent_subscription_is_fenced(self):
        second = self.consumer()
        def handler(event):
            with self.assertRaises(LeaseBusy):
                second.run_once()
            self.seen.append(event)
        first = self.consumer(handler)
        self.assertEqual(first.run_once(), 3)
        self.assertEqual(second.cursor(), 3)

    def test_expired_lease_cannot_checkpoint(self):
        def slow(event):
            self.seen.append(event)
            self.now += timedelta(seconds=31)
        first = self.consumer(slow)
        with self.assertRaises(LeaseLost):
            first.run_once()
        self.assertEqual(first.cursor(), 0)
        self.assertEqual(self.consumer().run_once(), 3)
        self.assertEqual([e["sequence"] for e in self.seen], [1, 1, 2, 3])

    def test_missing_or_reordered_events_fail_closed(self):
        for sequences in ((2, 3), (1, 3), (1, 1, 2)):
            with self.subTest(sequences=sequences):
                consumer = OutboxConsumer(self.db, Source(sequences), str(sequences), self.seen.append)
                with self.assertRaises(WorkerError):
                    consumer.run_once()
                self.assertLessEqual(consumer.cursor(), 1)

    def test_crashed_worker_lease_can_be_taken_over_after_expiry(self):
        first = self.consumer()
        first.run_once()
        with self.db.transaction() as conn:
            conn.execute("""UPDATE uta_event_consumers SET cursor=0,owner='dead',expires_us=?
                WHERE consumer_id='audit'""", (first._now() + 1_000_000,))
        with self.assertRaises(LeaseBusy):
            self.consumer().run_once()
        self.now += timedelta(seconds=2)
        self.assertEqual(self.consumer().run_once(), 3)


if __name__ == "__main__":
    unittest.main()
