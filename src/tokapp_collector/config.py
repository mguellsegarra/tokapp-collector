from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Optional


class ConfigError(ValueError):
    pass


def load_dotenv(path: Path) -> None:
    if not path.exists():
        return
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in {'"', "'"}:
            value = value[1:-1]
        os.environ.setdefault(key, value)


def _bool(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    normalized = value.strip().casefold()
    if normalized in {"1", "true", "yes", "on", "si", "sí"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    raise ConfigError(f"{name} ha de ser true o false")


def _int(name: str, default: Optional[int] = None) -> Optional[int]:
    value = os.getenv(name)
    if value is None or not value.strip():
        return default
    try:
        return int(value)
    except ValueError as error:
        raise ConfigError(f"{name} ha de ser un enter") from error


def _required(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise ConfigError(f"Falta la variable {name}")
    return value


@dataclass
class AppConfig:
    tokapp_username: str
    tokapp_password: str
    tokapp_base_url: str
    tokapp_app_version: str
    ack_received: bool
    poll_interval_seconds: int
    request_timeout_seconds: int
    data_dir: Path
    rules_path: Path
    dedup_window_hours: int
    ai_provider: str
    openai_api_key: Optional[str]
    openai_model: str
    openai_base_url: str
    telegram_token: str
    telegram_chat_id: str
    telegram_important_topic_id: Optional[int]
    telegram_other_topic_id: Optional[int]
    telegram_error_topic_id: Optional[int]
    publisher_mode: str

    @classmethod
    def from_env(cls, env_file: Path | None = None) -> "AppConfig":
        load_dotenv(env_file or Path(".env"))
        ai_provider = os.getenv("AI_PROVIDER", "openai").strip().casefold()
        openai_key = os.getenv("OPENAI_API_KEY")
        if ai_provider == "openai" and not openai_key:
            raise ConfigError("AI_PROVIDER=openai requereix OPENAI_API_KEY")
        if ai_provider not in {"openai", "rules"}:
            raise ConfigError("AI_PROVIDER només pot ser openai o rules")
        poll_interval = int(_int("POLL_INTERVAL_SECONDS", 180) or 180)
        if poll_interval < 30:
            raise ConfigError("POLL_INTERVAL_SECONDS no pot ser inferior a 30")
        instance = cls(
            tokapp_username=_required("TOKAPP_USERNAME"),
            tokapp_password=_required("TOKAPP_PASSWORD"),
            tokapp_base_url=os.getenv("TOKAPP_BASE_URL", "https://app.tokapp.net/?"),
            tokapp_app_version=os.getenv("TOKAPP_APP_VERSION", "5.0.0"),
            ack_received=_bool("TOKAPP_ACK_RECEIVED", False),
            poll_interval_seconds=poll_interval,
            request_timeout_seconds=int(_int("REQUEST_TIMEOUT_SECONDS", 25) or 25),
            data_dir=Path(os.getenv("DATA_DIR", "data")).expanduser(),
            rules_path=Path(os.getenv("RULES_PATH", "config/rules.json")).expanduser(),
            dedup_window_hours=int(_int("DEDUP_WINDOW_HOURS", 48) or 48),
            ai_provider=ai_provider,
            openai_api_key=openai_key,
            openai_model=os.getenv("OPENAI_MODEL", "gpt-5.4-mini"),
            openai_base_url=os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1"),
            telegram_token=os.getenv("TELEGRAM_BOT_TOKEN", ""),
            telegram_chat_id=os.getenv("TELEGRAM_CHAT_ID", ""),
            telegram_important_topic_id=_int("TELEGRAM_IMPORTANT_TOPIC_ID"),
            telegram_other_topic_id=_int("TELEGRAM_OTHER_TOPIC_ID"),
            telegram_error_topic_id=_int("TELEGRAM_ERROR_TOPIC_ID"),
            publisher_mode=os.getenv("PUBLISHER", "telegram").strip().lower() or "telegram",
        )
        if instance.publisher_mode not in {"telegram", "local"}:
            raise ConfigError("PUBLISHER ha de ser telegram o local")
        if instance.publisher_mode == "telegram" and (
            not instance.telegram_token or not instance.telegram_chat_id
        ):
            raise ConfigError("TELEGRAM_BOT_TOKEN i TELEGRAM_CHAT_ID són obligatoris amb PUBLISHER=telegram")
        return instance

    def load_rules(self) -> Dict[str, Any]:
        try:
            data = json.loads(self.rules_path.read_text(encoding="utf-8"))
        except FileNotFoundError as error:
            raise ConfigError(f"No existeix el fitxer de regles: {self.rules_path}") from error
        except json.JSONDecodeError as error:
            raise ConfigError(f"El fitxer de regles no és JSON vàlid: {error}") from error
        if not isinstance(data, dict):
            raise ConfigError("El fitxer de regles ha de contenir un objecte JSON")
        return data
