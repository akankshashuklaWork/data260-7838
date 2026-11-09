"""Evaluator Agent: checks an answer against the reference dataset (the ground truth)."""

from __future__ import annotations

from typing import Any

from . import reference


class EvaluatorAgent:
    def evaluate(self, question: str, answer: str) -> dict[str, Any]:
        """Return result PASS or REVISE, a short explanation, and feedback when the result is REVISE."""
        info = reference.classify(question)
        record, field = info["record"], info["field"]

        if record is None or field not in (record["facts"] if record else {}):
            # No reference facts cover this question, so the only supported answer is a refusal.
            if reference.is_decline(answer):
                return {
                    "result": "PASS",
                    "explanation": "The reference data has no facts for this question and the answer correctly declines.",
                    "feedback": None,
                    "failure_type": None,
                    "label": "unrelated",
                }
            return {
                "result": "REVISE",
                "explanation": "The reference data has no facts for this question, but the answer states information anyway.",
                "feedback": "The reference dataset does not cover this question. Do not answer from general knowledge; say you do not have that information.",
                "failure_type": "unsupported_answer",
                "label": "unrelated",
            }

        fact = record["facts"][field]
        label = reference.FIELD_LABELS[field]
        if reference.check_fact(fact["check"], answer):
            return {
                "result": "PASS",
                "explanation": f"The answer matches the reference {label} for {record['property']} ({fact['value']}).",
                "feedback": None,
                "failure_type": None,
                "label": label,
            }
        failure = "missing_value" if reference.is_decline(answer) else "wrong_value"
        problem = "does not give" if failure == "missing_value" else "contradicts"
        return {
            "result": "REVISE",
            "explanation": f"The answer {problem} the reference {label} for {record['property']}.",
            "feedback": f"Use the reference dataset: {record['property']} {label} is {fact['value']}. State this exact value.",
            "failure_type": failure,
            "label": label,
        }
