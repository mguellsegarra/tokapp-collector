from __future__ import annotations

import hashlib
import html
import json
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from html.parser import HTMLParser
from typing import Any, Dict, List, Optional


class TelegramError(RuntimeError):
    pass


class _TokappHTMLConverter(HTMLParser):
    INLINE_TAGS = {
        "b": "b",
        "strong": "b",
        "i": "i",
        "em": "i",
        "u": "u",
        "ins": "u",
        "s": "s",
        "strike": "s",
        "del": "s",
        "code": "code",
    }
    BLOCK_TAGS = {"p", "div", "section", "article", "blockquote"}
    HIDDEN_TAGS = {"script", "style", "head"}

    def __init__(self, *, formatted: bool) -> None:
        super().__init__(convert_charrefs=True)
        self.formatted = formatted
        self.parts: List[str] = []
        self.open_tags: List[tuple[str, str]] = []
        self.hidden_depth = 0

    def _break(self) -> None:
        if self.parts and not self.parts[-1].endswith("\n"):
            self.parts.append("\n")

    @staticmethod
    def _safe_href(attrs: List[tuple[str, Optional[str]]]) -> Optional[str]:
        href = next((value for key, value in attrs if key.casefold() == "href"), None)
        if not href:
            return None
        try:
            parsed = urllib.parse.urlsplit(href.strip())
        except ValueError:
            return None
        if parsed.scheme.casefold() not in {"http", "https", "mailto"}:
            return None
        return href.strip()

    def handle_starttag(self, tag: str, attrs: List[tuple[str, Optional[str]]]) -> None:
        tag = tag.casefold()
        if tag in self.HIDDEN_TAGS:
            self.hidden_depth += 1
            return
        if self.hidden_depth:
            return
        if tag in self.BLOCK_TAGS:
            self._break()
            return
        if tag == "br":
            self._break()
            return
        if tag == "li":
            self._break()
            self.parts.append("• ")
            return
        rendered = self.INLINE_TAGS.get(tag)
        if tag == "a":
            href = self._safe_href(attrs)
            if href:
                rendered = f'a href="{html.escape(href, quote=True)}"'
        if self.formatted and rendered:
            self.parts.append(f"<{rendered}>")
            self.open_tags.append((tag, rendered.split(" ", 1)[0]))

    def handle_startendtag(self, tag: str, attrs: List[tuple[str, Optional[str]]]) -> None:
        self.handle_starttag(tag, attrs)

    def handle_endtag(self, tag: str) -> None:
        tag = tag.casefold()
        if tag in self.HIDDEN_TAGS:
            if self.hidden_depth:
                self.hidden_depth -= 1
            return
        if self.hidden_depth:
            return
        if tag in self.BLOCK_TAGS or tag == "li":
            self._break()
            return
        if not self.formatted:
            return
        for index in range(len(self.open_tags) - 1, -1, -1):
            if self.open_tags[index][0] != tag:
                continue
            for _, rendered in reversed(self.open_tags[index:]):
                self.parts.append(f"</{rendered}>")
            del self.open_tags[index:]
            return

    def handle_data(self, data: str) -> None:
        if self.hidden_depth or not data:
            return
        compact = re.sub(r"\s+", " ", data)
        if not compact.strip():
            if self.parts and not self.parts[-1].endswith((" ", "\n")):
                self.parts.append(" ")
            return
        if not self.parts or self.parts[-1].endswith("\n"):
            compact = compact.lstrip()
        if self.parts and self.parts[-1].endswith(" "):
            compact = compact.lstrip()
        self.parts.append(html.escape(compact, quote=False) if self.formatted else compact)

    def result(self) -> str:
        if self.formatted:
            for _, rendered in reversed(self.open_tags):
                self.parts.append(f"</{rendered}>")
            self.open_tags.clear()
        value = "".join(self.parts)
        value = re.sub(r"[ \t]+\n", "\n", value)
        value = re.sub(r"\n{3,}", "\n\n", value)
        return value.strip()


def tokapp_html_to_telegram(value: str) -> str:
    converter = _TokappHTMLConverter(formatted=True)
    converter.feed(value)
    converter.close()
    return converter.result()


def tokapp_html_to_text(value: str) -> str:
    converter = _TokappHTMLConverter(formatted=False)
    converter.feed(value)
    converter.close()
    return converter.result()


class TelegramClient:
    def __init__(self, token: str, chat_id: str, timeout_seconds: int = 20) -> None:
        if not token or not chat_id:
            raise ValueError("Telegram necessita token i chat_id")
        self.base_url = f"https://api.telegram.org/bot{token}"
        self.chat_id = chat_id
        self.timeout_seconds = timeout_seconds

    def _request(self, method: str, payload: Dict[str, Any], retry: bool = True) -> Dict[str, Any]:
        body = json.dumps(payload).encode("utf-8")
        request = urllib.request.Request(
            f"{self.base_url}/{method}",
            data=body,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=self.timeout_seconds) as response:
                result = json.load(response)
        except urllib.error.HTTPError as error:
            try:
                result = json.loads(error.read().decode("utf-8"))
            except (ValueError, UnicodeDecodeError):
                raise TelegramError(f"Telegram HTTP {error.code}") from None
            finally:
                error.close()
        except OSError:
            raise TelegramError("No s'ha pogut contactar amb Telegram") from None

        if result.get("ok"):
            return dict(result["result"])

        description = str(result.get("description") or "Error desconegut de Telegram")
        if method == "editMessageText" and description.startswith("Bad Request: message is not modified"):
            return {"message_id": payload["message_id"]}

        parameters = result.get("parameters") or {}
        if retry and parameters.get("migrate_to_chat_id") is not None:
            self.chat_id = str(parameters["migrate_to_chat_id"])
            payload["chat_id"] = self.chat_id
            return self._request(method, payload, retry=False)
        if retry and parameters.get("retry_after") is not None:
            time.sleep(min(int(parameters["retry_after"]), 60))
            return self._request(method, payload, retry=False)
        error_code = result.get("error_code")
        raise TelegramError(
            f"Telegram API error {error_code}"
            if isinstance(error_code, int)
            else "Telegram ha rebutjat la petició"
        )

    def send_message(
        self,
        *,
        text: str,
        disable_notification: bool,
        message_thread_id: Optional[int] = None,
    ) -> Dict[str, Any]:
        payload: Dict[str, Any] = {
            "chat_id": self.chat_id,
            "text": text,
            "parse_mode": "HTML",
            "disable_notification": disable_notification,
            "link_preview_options": {"is_disabled": True},
        }
        if message_thread_id is not None:
            payload["message_thread_id"] = message_thread_id
        return self._request("sendMessage", payload)

    def edit_message(
        self,
        *,
        message_id: int,
        text: str,
    ) -> Dict[str, Any]:
        payload: Dict[str, Any] = {
            "chat_id": self.chat_id,
            "message_id": message_id,
            "text": text,
            "parse_mode": "HTML",
            "link_preview_options": {"is_disabled": True},
        }
        return self._request("editMessageText", payload)

    def get_me(self) -> Dict[str, Any]:
        return self._request("getMe", {})


class TelegramPublisher:
    def __init__(
        self,
        client: Any,
        important_topic_id: Optional[int] = None,
        other_topic_id: Optional[int] = None,
        error_topic_id: Optional[int] = None,
    ) -> None:
        self.client = client
        self.important_topic_id = important_topic_id
        self.other_topic_id = other_topic_id
        self.error_topic_id = error_topic_id

    @staticmethod
    def _is_important(event: Dict[str, Any]) -> bool:
        analysis = event["analysis"]
        return bool(
            analysis["importance"] == "high"
            or analysis["action_required"]
            or analysis.get("deadline")
        )

    @staticmethod
    def _format_recipients(recipients: List[str]) -> str:
        if not recipients:
            return "no identificat"
        return ", ".join(value.replace("_", " ") for value in recipients)

    def format_event(self, event: Dict[str, Any], include_original: bool = True) -> str:
        analysis = event["analysis"]
        important = self._is_important(event)
        label = "IMPORTANT" if important else analysis["importance"].upper()
        category = str(analysis["category"]).replace("_", " ").upper()
        lines = [
            f"<b>{html.escape(label)} · {html.escape(category)}</b>",
            "",
            html.escape(str(analysis["summary"])),
        ]
        if analysis.get("action"):
            lines.extend(["", f"<b>Cal fer:</b> {html.escape(str(analysis['action']))}"])
        if analysis.get("deadline"):
            lines.append(f"<b>Termini:</b> {html.escape(str(analysis['deadline']))}")
        lines.append(
            f"<b>Afecta:</b> {html.escape(self._format_recipients(event.get('recipients', [])))}"
        )
        duplicate_count = int(event.get("duplicate_count", 1))
        if duplicate_count > 1:
            lines.append(f"<b>Agrupat:</b> rebut {duplicate_count} vegades")
        sender = str(event.get("sender") or "TokApp")
        lines.append(f"<b>Emissor:</b> {html.escape(sender)}")
        if include_original:
            original = tokapp_html_to_telegram(str(event.get("text") or ""))
            lines.extend(
                [
                    "",
                    "<b>Text original</b>",
                    f"<blockquote>{original}</blockquote>",
                ]
            )
        return "\n".join(lines)

    @staticmethod
    def _chunks(text: str, size: int = 3300) -> List[str]:
        return [text[index : index + size] for index in range(0, len(text), size)]

    def publish(self, event: Dict[str, Any]) -> Dict[str, Any]:
        important = self._is_important(event)
        topic_id = self.important_topic_id if important else self.other_topic_id
        original = str(event.get("text") or "")
        formatted_original = tokapp_html_to_telegram(original)
        include_original = len(formatted_original) <= 2200
        result = self.client.send_message(
            text=self.format_event(event, include_original=include_original),
            disable_notification=not important,
            message_thread_id=topic_id,
        )
        if not include_original:
            plain_original = tokapp_html_to_text(original)
            for index, chunk in enumerate(self._chunks(plain_original), start=1):
                text = (
                    f"<b>Text original · part {index}</b>\n"
                    f"<blockquote>{html.escape(chunk)}</blockquote>"
                )
                self.client.send_message(
                    text=text,
                    disable_notification=True,
                    message_thread_id=topic_id,
                )
        return result

    def update(self, event: Dict[str, Any]) -> None:
        telegram = event.get("telegram") or {}
        message_id = telegram.get("message_id")
        if not message_id:
            return
        formatted_original = tokapp_html_to_telegram(str(event.get("text") or ""))
        self.client.edit_message(
            message_id=int(message_id),
            text=self.format_event(event, include_original=len(formatted_original) <= 2200),
        )

    def publish_error(self, message: str) -> Dict[str, Any]:
        return self.client.send_message(
            text=f"<b>ERROR DEL COLLECTOR</b>\n\n{html.escape(message)}",
            disable_notification=False,
            message_thread_id=self.error_topic_id,
        )


class LocalPublisher:
    """Confirma el processament local; CollectorService s'encarrega de desar-lo."""

    def __init__(self) -> None:
        self.last_error: str | None = None

    def publish(self, event: Dict[str, Any]) -> Dict[str, Any]:
        event_id = str(event.get("event_id") or "event")
        # El servei comparteix l'esquema de publicació amb Telegram.
        message_id = int.from_bytes(hashlib.sha256(event_id.encode()).digest()[:4], "big") + 1
        return {"message_id": message_id, "publisher": "local"}

    def update(self, event: Dict[str, Any]) -> Dict[str, Any]:
        telegram = event.get("telegram") or {}
        message_id = telegram.get("message_id") or self.publish(event)["message_id"]
        return {"message_id": int(message_id), "publisher": "local", "updated": True}

    def publish_error(self, message: str) -> Dict[str, Any]:
        self.last_error = message
        return {"ok": True, "publisher": "local", "error": message}
