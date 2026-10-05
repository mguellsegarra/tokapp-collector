import unittest

from tokapp_collector.classifier import RuleEngine, RulesClassifier
from tokapp_collector.models import AnalysisResult, TokappMessage


class ClassifierTests(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = RuleEngine(
            high_keywords=["vaga", "aturada", "serveis mínims"],
            spam_keywords=["promoció comercial"],
            notify_when_uncertain=True,
        )

    def test_future_strike_is_always_important_and_actionable(self) -> None:
        msg = TokappMessage(
            id=1,
            text="Us informem que demà hi ha vaga i no es garanteix el servei habitual.",
            sender="Direcció",
            moment="2026-09-04T08:00:00Z",
            raw={},
        )
        result = RulesClassifier(self.engine).classify(msg)

        self.assertEqual(result.category, "vaga")
        self.assertEqual(result.importance, "high")
        self.assertTrue(result.action_required)

    def test_hard_rule_overrides_an_ai_false_negative(self) -> None:
        result = AnalysisResult(
            summary="Informació sobre una aturada demà.",
            category="informacio",
            importance="low",
            action_required=False,
            action=None,
            deadline=None,
            recipients=[],
            confidence=0.95,
            reason="Informatiu",
        )
        msg = TokappMessage(2, "Demà hi ha aturada.", "Escola", "2026-09-04T08:00:00Z", raw={})

        corrected = self.engine.enforce(msg, result)
        self.assertEqual(corrected.importance, "high")
        self.assertTrue(corrected.action_required)


if __name__ == "__main__":
    unittest.main()
