import unittest

from tokapp_collector.dedup import Deduplicator
from tokapp_collector.models import TokappMessage


def message(message_id: int, text: str, group_id: int) -> TokappMessage:
    return TokappMessage(
        id=message_id,
        text=text,
        sender="Escola Exemple",
        moment="2026-09-04T08:00:00Z",
        group_id=group_id,
        raw={"id": message_id, "mensaje": text},
    )


class DeduplicatorTests(unittest.TestCase):
    def test_child_names_and_group_ids_do_not_create_two_events(self) -> None:
        dedup = Deduplicator(
            child_aliases={"fill_1": ["Àlex"], "fill_2": ["Berta"]},
            group_recipients={"10": "fill_1", "20": "fill_2"},
        )

        first = message(1, "Benvolguda família de l’Àlex: demà hi ha vaga.", 10)
        second = message(2, "Benvolguda família de la Berta: demà hi ha vaga.", 20)

        self.assertEqual(dedup.fingerprint(first), dedup.fingerprint(second))
        self.assertEqual(dedup.recipients(first), ["fill_1"])
        self.assertEqual(dedup.recipients(second), ["fill_2"])

    def test_signed_attachment_query_does_not_break_deduplication(self) -> None:
        dedup = Deduplicator()
        first = message(1, "Circular adjunta", 10)
        second = message(2, "Circular adjunta", 20)
        first.attachment_url = "https://files.example.test/circular.pdf?token=one"
        second.attachment_url = "https://files.example.test/circular.pdf?token=two"

        self.assertEqual(dedup.fingerprint(first), dedup.fingerprint(second))


if __name__ == "__main__":
    unittest.main()
