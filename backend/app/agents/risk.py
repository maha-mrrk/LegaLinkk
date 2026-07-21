"""Rule-based legal risk assessment.

This module is intentionally decoupled from the ``LegalAgent`` so the
rule-based classifier can later be swapped for an ML/LLM classifier without
touching the agent. Any object implementing :class:`RiskClassifier` can be
injected into the agent.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, runtime_checkable

RiskLevel = str  # "low" | "medium" | "high"

_SEVERITY_ORDER: dict[str, int] = {"low": 0, "medium": 1, "high": 2}


@dataclass(frozen=True, slots=True)
class RiskFinding:
    """A single triggered risk rule."""

    level: RiskLevel
    category: str
    detail: str


@dataclass(frozen=True, slots=True)
class RiskAssessment:
    """Aggregated risk outcome returned by a classifier."""

    risk_level: RiskLevel
    findings: tuple[RiskFinding, ...] = ()
    missing_information: tuple[str, ...] = ()
    recommendations: tuple[str, ...] = ()


@runtime_checkable
class RiskClassifier(Protocol):
    """Contract for legal risk classifiers (rule-based today, ML tomorrow)."""

    def classify(
        self,
        *,
        context_text: str,
        answer: str | None = None,
        question: str | None = None,
    ) -> RiskAssessment: ...


# --- Keyword lexicons (bilingual FR/EN) -------------------------------------

_UNLIMITED_LIABILITY = (
    "unlimited liability",
    "unlimited liabilities",
    "without limitation of liability",
    "responsabilité illimitée",
    "responsabilite illimitee",
    "responsabilité sans limite",
    "sans limitation de responsabilité",
    "sans limitation de responsabilite",
)

_TERMINATION_TERMS = (
    "termination",
    "terminate",
    "terminated",
    "résiliation",
    "resiliation",
    "résilier",
    "resilier",
    "resiliated",
)

_CONFIDENTIALITY_TERMS = (
    "confidential",
    "confidentiality",
    "confidentialité",
    "confidentialite",
    "non-disclosure",
    "non disclosure",
    "nda",
)

_PAYMENT_TERMS = (
    "payment",
    "invoice",
    "price",
    "pricing",
    "paiement",
    "facture",
    "prix",
    "montant",
)

_PAYMENT_DEADLINE_TERMS = (
    "day",
    "days",
    "net 30",
    "net 60",
    "due date",
    "deadline",
    "within",
    "jour",
    "jours",
    "délai",
    "delai",
    "échéance",
    "echeance",
    "date de paiement",
)

_OBLIGATION_TERMS = (
    "obligation",
    "obligations",
    "shall",
    "must",
    "doit",
    "s'engage",
    "sengage",
    "engagement",
)

_AMBIGUITY_TERMS = (
    "reasonable",
    "appropriate",
    "as needed",
    "if necessary",
    "best effort",
    "best efforts",
    "raisonnable",
    "approprié",
    "approprie",
    "si nécessaire",
    "si necessaire",
    "meilleurs efforts",
    "dans la mesure du possible",
)


def _contains_any(haystack: str, needles: tuple[str, ...]) -> bool:
    return any(needle in haystack for needle in needles)


class RuleBasedRiskClassifier:
    """Deterministic keyword-driven risk classifier.

    The classifier only reasons over the retrieved contractual context, so any
    "missing clause" verdict is a heuristic over the retrieved evidence rather
    than a guarantee about the full document. This keeps the component simple
    and fully replaceable by an AI model later on.
    """

    def classify(
        self,
        *,
        context_text: str,
        answer: str | None = None,
        question: str | None = None,
    ) -> RiskAssessment:
        text = f"{context_text or ''}\n{answer or ''}".lower()

        findings: list[RiskFinding] = []
        missing: list[str] = []
        recommendations: list[str] = []

        has_context = bool((context_text or "").strip())

        # --- HIGH severity rules ---------------------------------------------
        if _contains_any(text, _UNLIMITED_LIABILITY):
            findings.append(
                RiskFinding(
                    level="high",
                    category="liability",
                    detail="Unlimited or uncapped liability detected.",
                )
            )
            recommendations.append(
                "Cap liability to a defined amount (e.g. total contract value)."
            )

        # "Missing clause" heuristics only make sense when some context exists;
        # an empty context means retrieval found nothing, not that the clause is
        # absent from the contract.
        if has_context and not _contains_any(text, _TERMINATION_TERMS):
            findings.append(
                RiskFinding(
                    level="high",
                    category="termination",
                    detail="No termination/resiliation clause found in the context.",
                )
            )
            missing.append("Termination / resiliation clause")
            recommendations.append(
                "Add an explicit termination clause with notice and conditions."
            )

        if has_context and not _contains_any(text, _CONFIDENTIALITY_TERMS):
            findings.append(
                RiskFinding(
                    level="high",
                    category="confidentiality",
                    detail="No confidentiality/NDA clause found in the context.",
                )
            )
            missing.append("Confidentiality clause")
            recommendations.append(
                "Add a confidentiality clause covering scope and duration."
            )

        # --- MEDIUM severity rules -------------------------------------------
        if _contains_any(text, _PAYMENT_TERMS) and not _contains_any(
            text, _PAYMENT_DEADLINE_TERMS
        ):
            findings.append(
                RiskFinding(
                    level="medium",
                    category="payment",
                    detail="Payment mentioned without a clear deadline or schedule.",
                )
            )
            missing.append("Explicit payment deadline / schedule")
            recommendations.append(
                "Specify payment deadlines, amounts, and late-payment penalties."
            )

        if _contains_any(text, _OBLIGATION_TERMS) and _contains_any(
            text, _AMBIGUITY_TERMS
        ):
            findings.append(
                RiskFinding(
                    level="medium",
                    category="obligations",
                    detail="Obligations phrased with vague/ambiguous wording.",
                )
            )
            recommendations.append(
                "Replace ambiguous wording with measurable, objective obligations."
            )

        risk_level = self._aggregate_level(findings)

        if risk_level == "low" and not recommendations:
            recommendations.append(
                "Contractual language appears clear and balanced; keep periodic review."
            )

        # De-duplicate while preserving order.
        return RiskAssessment(
            risk_level=risk_level,
            findings=tuple(findings),
            missing_information=tuple(dict.fromkeys(missing)),
            recommendations=tuple(dict.fromkeys(recommendations)),
        )

    @staticmethod
    def _aggregate_level(findings: list[RiskFinding]) -> RiskLevel:
        if not findings:
            return "low"
        highest = max(_SEVERITY_ORDER[f.level] for f in findings)
        for level, value in _SEVERITY_ORDER.items():
            if value == highest:
                return level
        return "low"


__all__ = [
    "RiskAssessment",
    "RiskClassifier",
    "RiskFinding",
    "RiskLevel",
    "RuleBasedRiskClassifier",
]
