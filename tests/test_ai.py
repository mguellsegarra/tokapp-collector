import io
import json
import unittest

from tokapp_collector.ai import OpenAIClassifier
from tokapp_collector.models import TokappMessage


class FakeResponse(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *_args):
        self.close()


class AiTests(unittest.TestCase):
    def test_uses_strict_schema_store_false_and_redacts_child_name(self) -> None:
        captured = {}
        analysis = {
            "summary": "Demà hi ha vaga.",
            "category": "vaga",
            "importance": "high",
            "action_required": True,
            "action": "Organitzar-se.",
            "deadline": "demà",
            "recipients": ["fill_1"],
            "confidence": 0.98,
            "reason": "Vaga futura",
        }

        def opener(request, timeout):
            captured["payload"] = json.loads(request.data)
            captured["authorization"] = request.headers["Authorization"]
            response = {
                "output": [
                    {
                        "content": [
                            {"type": "output_text", "text": json.dumps(analysis)}
                        ]
                    }
                ]
            }
            return FakeResponse(json.dumps(response).encode())

        classifier = OpenAIClassifier(
            api_key="secret-key",
            model="test-model",
            child_aliases={"fill_1": ["Àlex"]},
            opener=opener,
        )
        result = classifier.classify(
            TokappMessage(1, "Àlex, demà hi ha vaga.", "Escola", "", raw={})
        )

        payload = captured["payload"]
        self.assertFalse(payload["store"])
        self.assertTrue(payload["text"]["format"]["strict"])
        self.assertEqual(payload["text"]["format"]["type"], "json_schema")
        self.assertNotIn("Àlex", payload["input"])
        self.assertEqual(result.importance, "high")
        self.assertEqual(captured["authorization"], "Bearer secret-key")


if __name__ == "__main__":
    unittest.main()
