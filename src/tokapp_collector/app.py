from __future__ import annotations

from typing import Any

from .ai import OpenAIClassifier
from .classifier import GuardedClassifier, RuleEngine, RulesClassifier
from .config import AppConfig
from .dedup import Deduplicator
from .service import CollectorService
from .storage import JsonStore
from .telegram import LocalPublisher, TelegramClient, TelegramPublisher
from .tokapp import TokappClient


def build_components(config: AppConfig) -> dict[str, Any]:
    rules_data = config.load_rules()
    child_aliases = {
        str(key): [str(value) for value in values]
        for key, values in (rules_data.get("child_aliases") or {}).items()
    }
    group_recipients = {
        str(key): str(value)
        for key, value in (rules_data.get("group_recipients") or {}).items()
    }
    rules = RuleEngine(
        high_keywords=rules_data.get("high_keywords") or [],
        spam_keywords=rules_data.get("spam_keywords") or [],
        notify_when_uncertain=bool(rules_data.get("notify_when_uncertain", True)),
    )
    if config.ai_provider == "openai":
        classifier = GuardedClassifier(
            OpenAIClassifier(
                api_key=str(config.openai_api_key),
                model=config.openai_model,
                base_url=config.openai_base_url,
                timeout_seconds=config.request_timeout_seconds,
                child_aliases=child_aliases,
            ),
            rules,
        )
    else:
        classifier = RulesClassifier(rules)

    tokapp = TokappClient(
        username=config.tokapp_username,
        password=config.tokapp_password,
        base_url=config.tokapp_base_url,
        app_version=config.tokapp_app_version,
        timeout_seconds=config.request_timeout_seconds,
    )
    if config.publisher_mode == "local":
        telegram_client = None
        publisher = LocalPublisher()
    else:
        telegram_client = TelegramClient(
            token=config.telegram_token,
            chat_id=config.telegram_chat_id,
            timeout_seconds=config.request_timeout_seconds,
        )
        publisher = TelegramPublisher(
            telegram_client,
            important_topic_id=config.telegram_important_topic_id,
            other_topic_id=config.telegram_other_topic_id,
            error_topic_id=config.telegram_error_topic_id,
        )
    store = JsonStore(config.data_dir)
    service = CollectorService(
        tokapp=tokapp,
        store=store,
        classifier=classifier,
        deduplicator=Deduplicator(child_aliases, group_recipients),
        publisher=publisher,
        ack_received=config.ack_received,
        dedup_window_hours=config.dedup_window_hours,
    )
    return {
        "service": service,
        "tokapp": tokapp,
        "telegram": telegram_client,
        "publisher": publisher,
        "classifier": classifier,
        "store": store,
    }
