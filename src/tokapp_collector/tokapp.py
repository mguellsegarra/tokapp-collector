from __future__ import annotations

import hashlib
import json
import urllib.error
import urllib.parse
import urllib.request
from typing import Any, Callable, Dict, List, Optional

from .models import TokappMessage


class TokappApiError(RuntimeError):
    def __init__(self, message: str, code: Optional[int] = None) -> None:
        super().__init__(message)
        self.code = code


class TokappClient:
    def __init__(
        self,
        *,
        username: str,
        password: str,
        base_url: str = "https://app.tokapp.net/?",
        app_version: str = "5.0.0",
        timeout_seconds: int = 25,
        opener: Callable[..., Any] = urllib.request.urlopen,
    ) -> None:
        self.username = username
        self.password_hash = hashlib.md5(password.encode("utf-8")).hexdigest()
        self.base_url = base_url
        self.app_version = app_version
        self.timeout_seconds = timeout_seconds
        self.opener = opener
        self.session_key: Optional[str] = None
        self.user_id: Optional[int] = None

    def _post(
        self,
        endpoint: str,
        fields: Dict[str, Any],
        *,
        authenticated: bool,
    ) -> Dict[str, Any]:
        headers = {
            "PLATAFORMA": "android",
            "VERSION": self.app_version,
            "APPNAME": "tokapp",
            "Content-Type": "application/x-www-form-urlencoded",
            "User-Agent": "TokApp-Collector/0.1",
        }
        if authenticated:
            if not self.session_key:
                raise TokappApiError("No hi ha sessió de TokApp")
            headers["SESSION"] = self.session_key
        request = urllib.request.Request(
            self.base_url + endpoint,
            data=urllib.parse.urlencode(fields).encode("utf-8"),
            headers=headers,
            method="POST",
        )
        try:
            with self.opener(request, timeout=self.timeout_seconds) as response:
                payload = json.load(response)
        except urllib.error.HTTPError as error:
            error.close()
            raise TokappApiError(f"TokApp ha retornat HTTP {error.code}") from None
        except (OSError, ValueError):
            raise TokappApiError("No s'ha pogut contactar amb TokApp o interpretar la resposta") from None
        if not isinstance(payload, dict):
            raise TokappApiError("TokApp ha retornat una resposta inesperada")
        code = int(payload.get("error", -1))
        if code != 0:
            raise TokappApiError(
                f"TokApp error {code}",
                code=code,
            )
        return payload

    def login(self) -> None:
        payload = self._post(
            "c=Login&a=Login",
            {
                "username": self.username,
                "passwordHash": self.password_hash,
                "get_perfil": "1",
            },
            authenticated=False,
        )
        self.session_key = str(payload["sessionKey"])
        self.user_id = int(payload["login"])

    def fetch_messages(self) -> List[TokappMessage]:
        if not self.session_key or self.user_id is None:
            self.login()
        try:
            payload = self._post(
                "c=Chat&a=gm",
                {"idc": "0", "idg": "0", "esc": "0", "ui": str(self.user_id)},
                authenticated=True,
            )
        except TokappApiError:
            self.session_key = None
            self.user_id = None
            self.login()
            payload = self._post(
                "c=Chat&a=gm",
                {"idc": "0", "idg": "0", "esc": "0", "ui": str(self.user_id)},
                authenticated=True,
            )
        raw_messages = payload.get("getmensajes") or []
        if not isinstance(raw_messages, list):
            raise TokappApiError("getmensajes no és una llista")
        return [TokappMessage.from_api(raw) for raw in raw_messages]

    def acknowledge_received(self, ids: List[int]) -> None:
        if not ids:
            return
        self._post(
            "c=Chat&a=SetMensajesRecibidos",
            {"ids": ",".join(str(value) for value in ids)},
            authenticated=True,
        )
