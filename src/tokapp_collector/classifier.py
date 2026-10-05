from __future__ import annotations

import re
from dataclasses import replace
from typing import Iterable, Protocol

from .models import AnalysisResult, TokappMessage


class Classifier(Protocol):
    def classify(self, message: TokappMessage) -> AnalysisResult:
        ...


class RuleEngine:
    def __init__(
        self,
        high_keywords: Iterable[str],
        spam_keywords: Iterable[str],
        notify_when_uncertain: bool,
    ) -> None:
        self.high_keywords = [value.casefold() for value in high_keywords]
        self.spam_keywords = [value.casefold() for value in spam_keywords]
        self.notify_when_uncertain = notify_when_uncertain

    def hard_category(self, message: TokappMessage) -> str | None:
        text = message.text.casefold()
        if any(value in text for value in ("vaga", "aturada", "serveis mínims")):
            return "vaga"
        if any(value in text for value in self.high_keywords):
            return "important"
        return None

    def enforce(self, message: TokappMessage, result: AnalysisResult) -> AnalysisResult:
        hard_category = self.hard_category(message)
        if hard_category:
            action = result.action
            if hard_category == "vaga" and not action:
                action = "Comprovar l’afectació i els serveis mínims, i organitzar-se si cal."
            return replace(
                result,
                category=hard_category,
                importance="high",
                action_required=True,
                action=action,
                reason=(result.reason + "; regla prioritària: " + hard_category).strip("; "),
            )
        if self.notify_when_uncertain and result.confidence < 0.65:
            return replace(
                result,
                importance="high",
                reason=(result.reason + "; confiança baixa, s’avisa per seguretat").strip("; "),
            )
        return result


class RulesClassifier:
    """Classificació per paraules clau amb un resum mecànic, sense API d'IA."""

    def __init__(self, rules: RuleEngine) -> None:
        self.rules = rules

    @staticmethod
    def _summary(text: str) -> str:
        compact = re.sub(r"\s+", " ", text).strip()
        if not compact:
            return "Missatge de TokApp sense text."
        sentence = re.split(r"(?<=[.!?])\s+", compact, maxsplit=1)[0]
        return sentence if len(sentence) <= 240 else sentence[:237].rstrip() + "..."

    def classify(self, message: TokappMessage) -> AnalysisResult:
        text = message.text.casefold()
        hard = self.rules.hard_category(message)
        spam = any(value in text for value in self.rules.spam_keywords)
        result = AnalysisResult(
            summary=self._summary(message.text),
            category=hard or ("spam" if spam else "informacio"),
            importance="high" if hard else ("spam" if spam else "low"),
            action_required=bool(hard),
            action=None,
            deadline="demà" if "demà" in text else None,
            recipients=[],
            confidence=0.7 if hard else 0.55,
            reason="Regles locals de contingència",
        )
        return self.rules.enforce(message, result)


class GuardedClassifier:
    def __init__(self, delegate: Classifier, rules: RuleEngine) -> None:
        self.delegate = delegate
        self.rules = rules

    def classify(self, message: TokappMessage) -> AnalysisResult:
        return self.rules.enforce(message, self.delegate.classify(message))
