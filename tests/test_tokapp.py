import io
import json
import urllib.parse
import unittest

from tokapp_collector.tokapp import TokappClient


class FakeResponse(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *_args):
        self.close()


class SequentialOpener:
    def __init__(self, responses):
        self.responses = list(responses)
        self.requests = []

    def __call__(self, request, timeout):
        self.requests.append(request)
        return FakeResponse(json.dumps(self.responses.pop(0)).encode())


class TokappTests(unittest.TestCase):
    def test_login_fetch_and_ack_contract(self) -> None:
        opener = SequentialOpener(
            [
                {"error": 0, "login": 42, "sessionKey": "session-secret"},
                {
                    "error": 0,
                    "getmensajes": [
                        {
                            "id": 9,
                            "id_contacto": 3,
                            "id_grupo": 4,
                            "momento": "2026-09-04T08:00:00Z",
                            "mensaje": "Hola",
                            "nombreRemitente": "Escola",
                        }
                    ],
                },
                {"error": 0},
            ]
        )
        client = TokappClient(
            username="user@example.test",
            password="plain-password",
            opener=opener,
        )

        messages = client.fetch_messages()
        client.acknowledge_received([9, 10])

        login_form = urllib.parse.parse_qs(opener.requests[0].data.decode())
        fetch_form = urllib.parse.parse_qs(opener.requests[1].data.decode())
        ack_form = urllib.parse.parse_qs(opener.requests[2].data.decode())
        self.assertNotEqual(login_form["passwordHash"][0], "plain-password")
        self.assertEqual(fetch_form["ui"], ["42"])
        self.assertEqual(opener.requests[1].headers["Session"], "session-secret")
        self.assertEqual(ack_form["ids"], ["9,10"])
        self.assertEqual(messages[0].sender, "Escola")


if __name__ == "__main__":
    unittest.main()
