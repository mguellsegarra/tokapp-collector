import io
import json
import traceback
import unittest
import urllib.error
from unittest.mock import patch

from tokapp_collector.ai import AiError, OpenAIClassifier
from tokapp_collector.models import TokappMessage
from tokapp_collector.telegram import TelegramClient, TelegramError
from tokapp_collector.tokapp import TokappApiError, TokappClient


PRIVATE_MARKER = "private-fixture-do-not-log"


class Response(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *_args):
        self.close()


class ErrorPrivacyTests(unittest.TestCase):
    def assert_private_error(self, callback, exception_type):
        try:
            callback()
        except exception_type as error:
            self.assertNotIn(PRIVATE_MARKER, str(error))
            self.assertNotIn(PRIVATE_MARKER, traceback.format_exc())
        else:
            self.fail("The failed request must still raise an error")

    def test_openai_http_body_is_not_logged(self):
        error = urllib.error.HTTPError(
            "https://example.test", 401, PRIVATE_MARKER, None,
            io.BytesIO(json.dumps({"error": {"message": PRIVATE_MARKER}}).encode()),
        )
        classifier = OpenAIClassifier(api_key="test-key", model="test-model")
        with patch.object(classifier, "opener", side_effect=error):
            self.assert_private_error(
                lambda: classifier.classify(TokappMessage(1, "Example", "School", "", {})),
                AiError,
            )

    def test_openai_transport_error_is_not_logged(self):
        classifier = OpenAIClassifier(api_key="test-key", model="test-model")
        with patch.object(classifier, "opener", side_effect=OSError(PRIVATE_MARKER)):
            self.assert_private_error(
                lambda: classifier.classify(TokappMessage(1, "Example", "School", "", {})),
                AiError,
            )

    def test_invalid_analysis_value_is_not_logged(self):
        analysis = {
            "summary": "Example", "category": "informacio", "importance": "low",
            "action_required": False, "action": None, "deadline": None,
            "recipients": [], "confidence": PRIVATE_MARKER, "reason": "Example",
        }
        payload = {"output_text": json.dumps(analysis)}
        classifier = OpenAIClassifier(api_key="test-key", model="test-model")
        with patch.object(classifier, "opener", return_value=Response(json.dumps(payload).encode())):
            self.assert_private_error(
                lambda: classifier.classify(TokappMessage(1, "Example", "School", "", {})),
                AiError,
            )

    def test_tokapp_server_message_is_not_logged(self):
        client = TokappClient(username="test-user", password="test-password")
        payload = {"error": 5, "msg": PRIVATE_MARKER}
        with patch.object(client, "opener", return_value=Response(json.dumps(payload).encode())):
            self.assert_private_error(client.login, TokappApiError)

    def test_tokapp_transport_error_is_not_logged(self):
        client = TokappClient(username="test-user", password="test-password")
        with patch.object(client, "opener", side_effect=OSError(PRIVATE_MARKER)):
            self.assert_private_error(client.login, TokappApiError)

    def test_telegram_server_message_is_not_logged(self):
        client = TelegramClient("test-token", "test-chat")
        payload = {"ok": False, "error_code": 400, "description": PRIVATE_MARKER}
        with patch("urllib.request.urlopen", return_value=Response(json.dumps(payload).encode())):
            self.assert_private_error(client.get_me, TelegramError)

    def test_telegram_transport_error_is_not_logged(self):
        client = TelegramClient("test-token", "test-chat")
        with patch("urllib.request.urlopen", side_effect=OSError(PRIVATE_MARKER)):
            self.assert_private_error(client.get_me, TelegramError)


if __name__ == "__main__":
    unittest.main()
