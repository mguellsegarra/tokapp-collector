from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class TokappMessage:
    id: int
    text: str
    sender: str
    moment: str
    raw: Dict[str, Any]
    group_id: int = 0
    contact_id: int = 0
    attachment_type: int = 0
    attachment_url: Optional[str] = None
    thumbnail_url: Optional[str] = None
    location: Optional[str] = None
    event: bool = False

    @classmethod
    def from_api(cls, raw: Dict[str, Any]) -> "TokappMessage":
        return cls(
            id=int(raw["id"]),
            text=str(raw.get("mensaje") or ""),
            sender=str(raw.get("nombreRemitente") or raw.get("nombre_remitente") or "TokApp"),
            moment=str(raw.get("momento") or ""),
            raw=raw,
            group_id=int(raw.get("id_grupo") or 0),
            contact_id=int(raw.get("id_contacto") or 0),
            attachment_type=int(raw.get("tipo_adjunto") or 0),
            attachment_url=raw.get("url_adjunto"),
            thumbnail_url=raw.get("miniatura"),
            location=raw.get("ubicacion"),
            event=bool(raw.get("evento") or False),
        )


@dataclass
class AnalysisResult:
    summary: str
    category: str
    importance: str
    action_required: bool
    action: Optional[str]
    deadline: Optional[str]
    recipients: List[str]
    confidence: float
    reason: str

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "AnalysisResult":
        return cls(
            summary=str(data["summary"]),
            category=str(data["category"]),
            importance=str(data["importance"]),
            action_required=bool(data["action_required"]),
            action=data.get("action"),
            deadline=data.get("deadline"),
            recipients=[str(value) for value in data.get("recipients", [])],
            confidence=float(data["confidence"]),
            reason=str(data["reason"]),
        )


@dataclass
class ProcessStats:
    fetched: int = 0
    created_events: int = 0
    duplicates: int = 0
    acknowledged: int = 0
    skipped: int = 0
    errors: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)
