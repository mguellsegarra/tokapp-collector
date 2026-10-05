from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List

from .dedup import Deduplicator
from .models import ProcessStats, TokappMessage


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


class CollectorService:
    def __init__(
        self,
        *,
        tokapp: Any,
        store: Any,
        classifier: Any,
        deduplicator: Deduplicator,
        publisher: Any,
        ack_received: bool,
        dedup_window_hours: int,
    ) -> None:
        self.tokapp = tokapp
        self.store = store
        self.classifier = classifier
        self.deduplicator = deduplicator
        self.publisher = publisher
        self.ack_received = ack_received
        self.dedup_window_hours = dedup_window_hours

    def process_once(self) -> ProcessStats:
        messages: List[TokappMessage] = self.tokapp.fetch_messages()
        stats = ProcessStats(fetched=len(messages))
        ready_to_ack: List[int] = []
        for message in messages:
            try:
                status = self._process_message(message, stats)
                if status:
                    ready_to_ack.append(message.id)
            except Exception as error:
                stats.errors.append(f"{message.id}: {error}")

        if self.ack_received and ready_to_ack:
            self.tokapp.acknowledge_received(ready_to_ack)
            acknowledged_at = utc_now()
            for message_id in ready_to_ack:
                record = self.store.load_message(str(message_id))
                if record:
                    record["acknowledged_at"] = acknowledged_at
                    record["status"] = "acknowledged"
                    self.store.save_message(str(message_id), record)
            stats.acknowledged = len(ready_to_ack)
        return stats

    def _process_message(self, message: TokappMessage, stats: ProcessStats) -> bool:
        existing_source = self.store.load_message(str(message.id))
        if existing_source and existing_source.get("status") in {"processed", "acknowledged"}:
            stats.skipped += 1
            return existing_source.get("status") != "acknowledged"

        now = utc_now()
        source_record: Dict[str, Any] = {
            "id": message.id,
            "received_at": now,
            "tokapp_moment": message.moment,
            "sender": message.sender,
            "text": message.text,
            "group_id": message.group_id,
            "contact_id": message.contact_id,
            "attachment_url": message.attachment_url,
            "status": "stored",
            "raw": message.raw,
        }
        self.store.save_message(str(message.id), source_record)

        fingerprint = self.deduplicator.fingerprint(message)
        recipients = self.deduplicator.recipients(message)
        event = self.store.find_recent_event(
            fingerprint,
            now=now,
            window_hours=self.dedup_window_hours,
        )
        if event:
            is_new_source = message.id not in event.get("source_message_ids", [])
            event["source_message_ids"] = list(
                dict.fromkeys([*event.get("source_message_ids", []), message.id])
            )
            event["recipients"] = self.deduplicator.merge_recipients(
                event.get("recipients", []), recipients
            )
            event["duplicate_count"] = len(event["source_message_ids"])
            event["last_seen_at"] = now
            self.store.save_event(str(event["event_id"]), event)
            if event.get("telegram"):
                self.publisher.update(event)
            else:
                telegram_result = self.publisher.publish(event)
                event["telegram"] = {"message_id": int(telegram_result["message_id"])}
                self.store.save_event(str(event["event_id"]), event)
                stats.created_events += 1
            if is_new_source:
                stats.duplicates += 1
        else:
            analysis = self.classifier.classify(message)
            ai_recipients = [value.casefold() for value in analysis.recipients]
            recipients = self.deduplicator.merge_recipients(recipients, ai_recipients)
            event_id = f"event-{message.id}"
            event = {
                "event_id": event_id,
                "fingerprint": fingerprint,
                "first_seen_at": now,
                "last_seen_at": now,
                "source_message_ids": [message.id],
                "duplicate_count": 1,
                "sender": message.sender,
                "text": message.text,
                "attachment_url": message.attachment_url,
                "recipients": recipients,
                "analysis": analysis.to_dict(),
                "telegram": None,
            }
            self.store.save_event(event_id, event)
            telegram_result = self.publisher.publish(event)
            event["telegram"] = {"message_id": int(telegram_result["message_id"])}
            self.store.save_event(event_id, event)
            stats.created_events += 1

        source_record["event_id"] = event["event_id"]
        source_record["status"] = "processed"
        source_record["processed_at"] = utc_now()
        self.store.save_message(str(message.id), source_record)
        return True
