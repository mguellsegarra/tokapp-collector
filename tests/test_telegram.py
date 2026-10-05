import io
import json
import os
import subprocess
import sys
import unittest
import urllib.error
from unittest.mock import patch

from tokapp_collector.models import AnalysisResult
from tokapp_collector.telegram import (
    TelegramClient,
    TelegramError,
    TelegramPublisher,
    tokapp_html_to_telegram,
)


class FakeTelegramClient:
    def __init__(self) -> None:
        self.sent = []
        self.edited = []

    def send_message(self, **kwargs):
        self.sent.append(kwargs)
        return {"message_id": 77}

    def edit_message(self, **kwargs):
        self.edited.append(kwargs)
        return {"message_id": kwargs["message_id"]}


def event(importance: str) -> dict:
    return {
        "event_id": "e1",
        "sender": "Escola <Exemple>",
        "text": "Text original amb A & B",
        "recipients": ["fill_1", "fill_2"],
        "duplicate_count": 2,
        "analysis": AnalysisResult(
            summary="Demà hi ha vaga.",
            category="vaga",
            importance=importance,
            action_required=importance == "high",
            action="Comprovar els serveis mínims." if importance == "high" else None,
            deadline="demà" if importance == "high" else None,
            recipients=[],
            confidence=0.98,
            reason="Vaga futura",
        ).to_dict(),
    }


class TelegramPublisherTests(unittest.TestCase):
    def test_important_message_is_not_silent(self) -> None:
        client = FakeTelegramClient()
        publisher = TelegramPublisher(client, important_topic_id=10, other_topic_id=20)
        publisher.publish(event("high"))

        self.assertFalse(client.sent[0]["disable_notification"])
        self.assertEqual(client.sent[0]["message_thread_id"], 10)

    def test_normal_message_is_sent_silently_and_remains_in_telegram(self) -> None:
        client = FakeTelegramClient()
        publisher = TelegramPublisher(client, important_topic_id=10, other_topic_id=20)
        publisher.publish(event("low"))

        self.assertTrue(client.sent[0]["disable_notification"])
        self.assertEqual(client.sent[0]["message_thread_id"], 20)
        self.assertIn("Text original", client.sent[0]["text"])

    def test_html_is_escaped(self) -> None:
        client = FakeTelegramClient()
        TelegramPublisher(client).publish(event("low"))
        self.assertIn("&lt;Exemple&gt;", client.sent[0]["text"])
        self.assertIn("A &amp; B", client.sent[0]["text"])

    def test_tokapp_html_is_cleaned_and_rendered_for_telegram(self) -> None:
        source = (
            '<p>Benvolguda família de <span tag="Exemple, Berta">'
            'Exemple, Berta</span>,</p>'
            '<p>Envieu <strong>la fitxa</strong> al correu indicat.</p>'
            '<p><a href="https://example.cat/path?a=1&b=2">Web de l’escola</a></p>'
        )

        rendered = tokapp_html_to_telegram(source)

        self.assertNotIn("<p>", rendered)
        self.assertNotIn("<span", rendered)
        self.assertIn("Exemple, Berta", rendered)
        self.assertIn("<b>la fitxa</b>", rendered)
        self.assertIn(
            '<a href="https://example.cat/path?a=1&amp;b=2">Web de l’escola</a>',
            rendered,
        )

    def test_unsafe_html_and_links_are_not_forwarded(self) -> None:
        rendered = tokapp_html_to_telegram(
            '<script>alert(1)</script><a href="javascript:alert(2)">prem aquí</a>'
        )

        self.assertNotIn("script", rendered)
        self.assertNotIn("javascript", rendered)
        self.assertEqual(rendered, "prem aquí")

    def test_malformed_link_keeps_the_message_text(self) -> None:
        rendered = tokapp_html_to_telegram('<p>Consulta <a href="https://[invalid">la circular</a>.</p>')
        self.assertEqual(rendered, "Consulta la circular.")

    def test_three_recipients_are_identified_individually(self) -> None:
        data = event("low")
        data["recipients"] = ["fill_1", "fill_2", "fill_3"]
        rendered = TelegramPublisher(FakeTelegramClient()).format_event(data)
        self.assertIn("<b>Afecta:</b> fill 1, fill 2, fill 3", rendered)


class TelegramClientTests(unittest.TestCase):
    @staticmethod
    def api_error(description: str) -> urllib.error.HTTPError:
        payload = {"ok": False, "description": description}
        return urllib.error.HTTPError(
            "https://example.test/telegram", 400, "Bad Request", None,
            io.BytesIO(json.dumps(payload).encode()),
        )

    def test_repeated_edit_is_successful_when_content_is_unchanged(self) -> None:
        client = TelegramClient("test-token", "test-chat")
        error = self.api_error("Bad Request: message is not modified: specified new message content is exactly the same")
        with patch("urllib.request.urlopen", side_effect=error) as opener:
            result = client.edit_message(message_id=77, text="Already published")
        self.assertEqual(result["message_id"], 77)
        self.assertEqual(opener.call_count, 1)

    def test_other_edit_errors_still_fail(self) -> None:
        client = TelegramClient("test-token", "test-chat")
        with patch("urllib.request.urlopen", side_effect=self.api_error("Bad Request: message to edit not found")):
            with self.assertRaises(TelegramError):
                client.edit_message(message_id=77, text="Missing message")


class LocalPublisherTests(unittest.TestCase):
    def test_publication_id_survives_a_process_restart(self) -> None:
        code = (
            "from tokapp_collector.telegram import LocalPublisher; "
            "print(LocalPublisher().publish({'event_id': 'event-123'})['message_id'])"
        )
        ids = [subprocess.check_output(
            [sys.executable, "-c", code],
            env={**os.environ, "PYTHONHASHSEED": seed}, text=True,
        ).strip() for seed in ("1", "2")]
        self.assertEqual(ids[0], ids[1])
        self.assertGreater(int(ids[0]), 0)


if __name__ == "__main__":
    unittest.main()
