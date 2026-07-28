"""Deterministic scope guard for explicitly selected specialist agents."""

from __future__ import annotations

from dataclasses import dataclass

from app.agents.intent import IntentRouter

_LABELS = {
    "legal": "juridique",
    "finance": "financier",
    "compliance": "conformité",
}
_COMMANDS = {
    "legal": "/legal",
    "finance": "/finance",
    "compliance": "/compliance",
}


@dataclass(frozen=True, slots=True)
class DomainAssessment:
    """Result of checking one question against a selected agent domain."""

    allowed: bool
    target_domain: str
    detected_domains: tuple[str, ...]
    keywords_hit: tuple[str, ...]
    message: str | None = None


class DomainGuardService:
    """Prevent a selected specialist from answering outside its mandate."""

    def __init__(self, router: IntentRouter | None = None) -> None:
        self._router = router or IntentRouter()

    def assess(self, query: str, *, target_domain: str) -> DomainAssessment:
        match = self._router.detect(query)
        detected = match.domains
        if target_domain in detected:
            return DomainAssessment(
                allowed=True,
                target_domain=target_domain,
                detected_domains=detected,
                keywords_hit=match.keywords_hit,
            )

        target_label = _LABELS.get(target_domain, target_domain)
        if detected:
            suggested = detected[0]
            suggested_label = _LABELS.get(suggested, suggested)
            message = (
                f"Cette question ne relève pas du domaine {target_label}. "
                f"Elle semble relever du domaine {suggested_label}. "
                f"Utilisez la commande {_COMMANDS.get(suggested, f'/{suggested}')}."
            )
        else:
            message = (
                f"Cette question ne relève pas clairement du domaine {target_label}. "
                "Reformulez-la avec des éléments propres à ce domaine ou choisissez "
                "un autre assistant."
            )

        return DomainAssessment(
            allowed=False,
            target_domain=target_domain,
            detected_domains=detected,
            keywords_hit=match.keywords_hit,
            message=message,
        )


__all__ = ["DomainAssessment", "DomainGuardService"]
