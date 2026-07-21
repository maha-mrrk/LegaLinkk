"""Keyword-based intent detection for agent routing."""

from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class IntentMatch:
    """Detected domains for a user question."""

    domains: tuple[str, ...]
    keywords_hit: tuple[str, ...]


# Domain → trigger keywords (matched as whole words / phrases, case-insensitive).
DOMAIN_KEYWORDS: dict[str, tuple[str, ...]] = {
    "legal": (
        "clause",
        "clauses",
        "obligation",
        "obligations",
        "liability",
        "liabilities",
        "contract",
        "contracts",
        "warranty",
        "warranties",
        "indemnity",
        "termination",
        "breach",
        "legal",
        "law",
        "rights",
        "duty",
        "duties",
    ),
    "finance": (
        "payment",
        "payments",
        "invoice",
        "invoices",
        "penalty",
        "penalties",
        "pricing",
        "price",
        "fee",
        "fees",
        "cost",
        "costs",
        "amount",
        "amounts",
        "interest",
        "finance",
        "financial",
        "budget",
        "refund",
    ),
    "compliance": (
        "gdpr",
        "compliance",
        "regulation",
        "regulations",
        "iso",
        "privacy",
        "rgpd",
        "regulatory",
        "audit",
        "policy",
        "policies",
        "standard",
        "standards",
        "data protection",
        "conformité",
        "conformite",
    ),
}

DOMAIN_TO_AGENT: dict[str, str] = {
    "legal": "LegalAgent",
    "finance": "FinanceAgent",
    "compliance": "ComplianceAgent",
}


class IntentRouter:
    """Detect which agent domains a query touches."""

    def detect(self, query: str) -> IntentMatch:
        text = (query or "").strip().lower()
        if not text:
            return IntentMatch(domains=(), keywords_hit=())

        domains: list[str] = []
        hits: list[str] = []

        for domain, keywords in DOMAIN_KEYWORDS.items():
            matched = [kw for kw in keywords if self._contains(text, kw)]
            if matched:
                domains.append(domain)
                hits.extend(matched)

        return IntentMatch(domains=tuple(domains), keywords_hit=tuple(hits))

    def agent_names_for(self, query: str) -> list[str]:
        """Map detected domains to agent class names."""
        match = self.detect(query)
        return [DOMAIN_TO_AGENT[d] for d in match.domains if d in DOMAIN_TO_AGENT]

    @staticmethod
    def _contains(text: str, keyword: str) -> bool:
        if " " in keyword:
            return keyword in text
        return re.search(rf"\b{re.escape(keyword)}\b", text) is not None
