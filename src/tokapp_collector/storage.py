from __future__ import annotations

import json
import os
import re
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, Optional


def _parse_datetime(value: str) -> datetime:
    normalized = value.replace("Z", "+00:00")
    parsed = datetime.fromisoformat(normalized)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


class JsonStore:
    def __init__(self, root: Path) -> None:
        self.root = root
        self.messages_dir = root / "messages"
        self.events_dir = root / "events"
        self.state_dir = root / "state"
        self.root.mkdir(mode=0o700, parents=True, exist_ok=True)
        for directory in (self.messages_dir, self.events_dir, self.state_dir):
            directory.mkdir(mode=0o700, parents=True, exist_ok=True)

    @staticmethod
    def _safe_name(value: str) -> str:
        cleaned = re.sub(r"[^A-Za-z0-9_.-]", "_", value)
        if not cleaned or cleaned in {".", ".."}:
            raise ValueError("Nom de fitxer no vàlid")
        return cleaned

    @staticmethod
    def _atomic_write(path: Path, data: Dict[str, Any]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        descriptor, temporary = tempfile.mkstemp(prefix=f".{path.name}.", dir=str(path.parent))
        try:
            with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
                json.dump(data, handle, ensure_ascii=False, indent=2, sort_keys=True)
                handle.write("\n")
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary, path)
        except BaseException:
            try:
                os.unlink(temporary)
            except FileNotFoundError:
                pass
            raise

    @staticmethod
    def _read(path: Path) -> Dict[str, Any]:
        return json.loads(path.read_text(encoding="utf-8"))

    def message_path(self, message_id: str) -> Path:
        return self.messages_dir / f"{self._safe_name(message_id)}.json"

    def event_path(self, event_id: str) -> Path:
        return self.events_dir / f"{self._safe_name(event_id)}.json"

    def save_message(self, message_id: str, data: Dict[str, Any]) -> None:
        self._atomic_write(self.message_path(message_id), data)

    def load_message(self, message_id: str) -> Optional[Dict[str, Any]]:
        path = self.message_path(message_id)
        return self._read(path) if path.exists() else None

    def save_event(self, event_id: str, data: Dict[str, Any]) -> None:
        self._atomic_write(self.event_path(event_id), data)

    def load_event(self, event_id: str) -> Optional[Dict[str, Any]]:
        path = self.event_path(event_id)
        return self._read(path) if path.exists() else None

    def find_recent_event(
        self,
        fingerprint: str,
        now: str,
        window_hours: int,
    ) -> Optional[Dict[str, Any]]:
        threshold = _parse_datetime(now) - timedelta(hours=window_hours)
        newest: Optional[Dict[str, Any]] = None
        newest_at: Optional[datetime] = None
        for path in self.events_dir.glob("*.json"):
            event = self._read(path)
            if event.get("fingerprint") != fingerprint:
                continue
            seen_at = _parse_datetime(str(event["last_seen_at"]))
            if seen_at < threshold:
                continue
            if newest_at is None or seen_at > newest_at:
                newest = event
                newest_at = seen_at
        return newest

    def save_state(self, name: str, data: Dict[str, Any]) -> None:
        path = self.state_dir / f"{self._safe_name(name)}.json"
        self._atomic_write(path, data)

    def load_state(self, name: str) -> Optional[Dict[str, Any]]:
        path = self.state_dir / f"{self._safe_name(name)}.json"
        return self._read(path) if path.exists() else None
