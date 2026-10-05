from __future__ import annotations

import json
import logging
import signal
import threading
import time
from typing import Any


LOGGER = logging.getLogger(__name__)


class Runner:
    def __init__(self, service: Any, publisher: Any, poll_interval_seconds: int) -> None:
        self.service = service
        self.publisher = publisher
        self.poll_interval_seconds = poll_interval_seconds
        self.stop_event = threading.Event()
        self.last_error_notice_at: float | None = None

    def stop(self, *_args: Any) -> None:
        self.stop_event.set()

    def run_once(self) -> dict[str, Any]:
        stats = self.service.process_once()
        result = stats.to_dict()
        LOGGER.info("poll %s", json.dumps(result, ensure_ascii=False, sort_keys=True))
        if stats.errors:
            self._notify_error("; ".join(stats.errors))
        return result

    def _notify_error(self, message: str) -> None:
        now = time.monotonic()
        if self.last_error_notice_at is not None and now - self.last_error_notice_at < 3600:
            return
        try:
            self.publisher.publish_error(message[:3000])
            self.last_error_notice_at = now
        except Exception:
            LOGGER.exception("No s'ha pogut enviar l'error a Telegram")

    def run_forever(self) -> None:
        signal.signal(signal.SIGTERM, self.stop)
        signal.signal(signal.SIGINT, self.stop)
        while not self.stop_event.is_set():
            try:
                self.run_once()
            except Exception as error:
                LOGGER.exception("Error del cicle de polling")
                self._notify_error(str(error))
            self.stop_event.wait(self.poll_interval_seconds)
