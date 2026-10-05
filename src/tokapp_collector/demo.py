from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List

from .classifier import RuleEngine, RulesClassifier
from .dedup import Deduplicator
from .models import TokappMessage
from .service import CollectorService
from .storage import JsonStore
from .telegram import TelegramPublisher


class DemoTokapp:
    def __init__(self, messages: List[TokappMessage]) -> None:
        self.messages = messages

    def fetch_messages(self) -> List[TokappMessage]:
        return self.messages

    def acknowledge_received(self, _ids: List[int]) -> None:
        raise AssertionError("La demo no pot confirmar missatges")


class DemoTelegramClient:
    def __init__(self) -> None:
        self.messages: List[Dict[str, Any]] = []

    def send_message(self, **kwargs: Any) -> Dict[str, Any]:
        self.messages.append(dict(kwargs))
        return {"message_id": len(self.messages)}

    def edit_message(self, **kwargs: Any) -> Dict[str, Any]:
        self.messages.append({"edit": True, **kwargs})
        return {"message_id": kwargs["message_id"]}


def run_demo(output_dir: Path) -> Dict[str, Any]:
    children = {"fill_1": ["Àlex"], "fill_2": ["Berta"]}
    groups = {"10": "fill_1", "20": "fill_2"}
    messages = [
        TokappMessage(
            1001,
            "Família de l’Àlex: demà hi ha vaga. No es garanteix el servei habitual.",
            "Escola Exemple",
            "2026-09-04T08:00:00Z",
            raw={"id": 1001},
            group_id=10,
        ),
        TokappMessage(
            1002,
            "Família de la Berta: demà hi ha vaga. No es garanteix el servei habitual.",
            "Escola Exemple",
            "2026-09-04T08:01:00Z",
            raw={"id": 1002},
            group_id=20,
        ),
        TokappMessage(
            1003,
            "Aquest mes publiquem el butlletí general de l'escola.",
            "Escola Exemple",
            "2026-09-04T09:00:00Z",
            raw={"id": 1003},
        ),
    ]
    client = DemoTelegramClient()
    publisher = TelegramPublisher(client, important_topic_id=10, other_topic_id=20)
    service = CollectorService(
        tokapp=DemoTokapp(messages),
        store=JsonStore(output_dir),
        classifier=RulesClassifier(
            RuleEngine(
                high_keywords=["vaga", "aturada", "serveis mínims"],
                spam_keywords=["promoció comercial"],
                notify_when_uncertain=False,
            )
        ),
        deduplicator=Deduplicator(children, groups),
        publisher=publisher,
        ack_received=False,
        dedup_window_hours=48,
    )
    stats = service.process_once()
    return {
        "stats": stats.to_dict(),
        "output_dir": str(output_dir),
        "telegram_calls": client.messages,
    }
