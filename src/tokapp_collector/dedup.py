from __future__ import annotations

import hashlib
import re
import unicodedata
import urllib.parse
from typing import Dict, Iterable, List

from .models import TokappMessage


class Deduplicator:
    def __init__(
        self,
        child_aliases: Dict[str, List[str]] | None = None,
        group_recipients: Dict[str, str] | None = None,
    ) -> None:
        self.child_aliases = child_aliases or {}
        self.group_recipients = group_recipients or {}

    @staticmethod
    def _basic_normalize(value: str) -> str:
        value = unicodedata.normalize("NFKC", value).casefold()
        value = re.sub(r"\s+", " ", value)
        return value.strip()

    def normalize_text(self, text: str) -> str:
        normalized = self._basic_normalize(text)
        aliases = sorted(
            (alias for values in self.child_aliases.values() for alias in values),
            key=len,
            reverse=True,
        )
        for alias in aliases:
            alias_normalized = self._basic_normalize(alias)
            if alias_normalized:
                normalized = re.sub(
                    rf"(?<!\w){re.escape(alias_normalized)}(?!\w)",
                    "<child>",
                    normalized,
                )
        normalized = re.sub(
            r"\b(?:del|de la|de l['’]|d['’])\s*<child>",
            "<child>",
            normalized,
        )
        normalized = re.sub(r"\s+", " ", normalized).strip()
        return normalized

    def fingerprint(self, message: TokappMessage) -> str:
        attachment = ""
        if message.attachment_url:
            parsed = urllib.parse.urlsplit(message.attachment_url)
            attachment = urllib.parse.urlunsplit(
                (parsed.scheme, parsed.netloc, parsed.path, "", "")
            )
        components = [
            self._basic_normalize(message.sender),
            self.normalize_text(message.text),
            self._basic_normalize(attachment),
        ]
        return hashlib.sha256("\x1f".join(components).encode("utf-8")).hexdigest()

    def recipients(self, message: TokappMessage) -> List[str]:
        found: List[str] = []
        haystack = self._basic_normalize(message.text)
        for recipient, aliases in self.child_aliases.items():
            if any(self._basic_normalize(alias) in haystack for alias in aliases):
                found.append(recipient)
        mapped = self.group_recipients.get(str(message.group_id))
        if mapped and mapped not in found:
            found.append(mapped)
        return found

    @staticmethod
    def merge_recipients(*groups: Iterable[str]) -> List[str]:
        result: List[str] = []
        for group in groups:
            for value in group:
                if value not in result:
                    result.append(value)
        return result
