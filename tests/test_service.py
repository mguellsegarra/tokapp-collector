import tempfile
import unittest
from pathlib import Path

from tokapp_collector.classifier import RuleEngine, RulesClassifier
from tokapp_collector.dedup import Deduplicator
from tokapp_collector.models import TokappMessage
from tokapp_collector.service import CollectorService
from tokapp_collector.storage import JsonStore


class FakeTokapp:
    def __init__(self, messages):
        self.messages = messages
        self.acked = []

    def fetch_messages(self):
        return self.messages

    def acknowledge_received(self, ids):
        self.acked.extend(ids)


class FakePublisher:
    def __init__(self):
        self.published = []
        self.updated = []

    def publish(self, event):
        self.published.append(event.copy())
        return {"message_id": 88}

    def update(self, event):
        self.updated.append(event.copy())


class FailsFirstPublisher(FakePublisher):
    def publish(self, event):
        if not self.published:
            self.published.append(event.copy())
            raise RuntimeError("fallada temporal de Telegram")
        return super().publish(event)


class ServiceTests(unittest.TestCase):
    def test_duplicates_are_stored_separately_but_only_one_telegram_is_created(self) -> None:
        messages = [
            TokappMessage(1, "Família de l’Àlex: demà hi ha vaga.", "Escola", "2026-09-04T08:00:00Z", group_id=10, raw={"id": 1}),
            TokappMessage(2, "Família de la Berta: demà hi ha vaga.", "Escola", "2026-09-04T08:01:00Z", group_id=20, raw={"id": 2}),
        ]
        with tempfile.TemporaryDirectory() as tmp:
            store = JsonStore(Path(tmp))
            tokapp = FakeTokapp(messages)
            publisher = FakePublisher()
            service = CollectorService(
                tokapp=tokapp,
                store=store,
                classifier=RulesClassifier(RuleEngine(["vaga"], [], True)),
                deduplicator=Deduplicator(
                    {"fill_1": ["Àlex"], "fill_2": ["Berta"]},
                    {"10": "fill_1", "20": "fill_2"},
                ),
                publisher=publisher,
                ack_received=True,
                dedup_window_hours=48,
            )

            stats = service.process_once()

            self.assertEqual(stats.fetched, 2)
            self.assertEqual(stats.created_events, 1)
            self.assertEqual(stats.duplicates, 1)
            self.assertEqual(len(publisher.published), 1)
            self.assertEqual(len(publisher.updated), 1)
            self.assertEqual(tokapp.acked, [1, 2])
            self.assertTrue((Path(tmp) / "messages" / "1.json").exists())
            self.assertTrue((Path(tmp) / "messages" / "2.json").exists())

    def test_retry_publishes_event_left_without_telegram_result(self) -> None:
        message = TokappMessage(
            1,
            "Demà hi ha vaga.",
            "Escola",
            "2026-09-04T08:00:00Z",
            raw={"id": 1},
        )
        with tempfile.TemporaryDirectory() as tmp:
            store = JsonStore(Path(tmp))
            publisher = FailsFirstPublisher()
            service = CollectorService(
                tokapp=FakeTokapp([message]),
                store=store,
                classifier=RulesClassifier(RuleEngine(["vaga"], [], True)),
                deduplicator=Deduplicator(),
                publisher=publisher,
                ack_received=True,
                dedup_window_hours=48,
            )

            first = service.process_once()
            second = service.process_once()

            self.assertEqual(len(first.errors), 1)
            self.assertEqual(second.errors, [])
            self.assertEqual(second.created_events, 1)
            self.assertEqual(len(publisher.published), 2)
            self.assertEqual(service.tokapp.acked, [1])
            self.assertEqual(store.load_event("event-1")["telegram"], {"message_id": 88})


if __name__ == "__main__":
    unittest.main()
