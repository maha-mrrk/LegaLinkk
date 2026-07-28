"""Deterministic contract risk scoring from structured legal findings."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any

_LEVELS = ("high", "medium", "low")


def _unique_findings(
    findings: Iterable[Mapping[str, Any]],
) -> set[tuple[str, str, str]]:
    return {
        (
            str(finding.get("level") or "").strip().lower(),
            str(finding.get("category") or "").strip().lower(),
            str(finding.get("detail") or "").strip().lower(),
        )
        for finding in findings
        if isinstance(finding, Mapping)
    }


def derive_risk_level(
    findings: Iterable[Mapping[str, Any]],
    *,
    default: str = "low",
) -> str:
    """Derive a level from findings so the label cannot contradict the score."""
    levels = {finding[0] for finding in _unique_findings(findings)}
    return next((level for level in _LEVELS if level in levels), default)


def calculate_risk_score(
    findings: Iterable[Mapping[str, Any]],
    missing_information: Iterable[str] = (),
) -> int:
    """Return a 0–100 contract quality score.

    The most severe finding selects the score band, while every additional
    finding lowers the score within that band:

    - high risk: 0–49 (first high finding starts at 45);
    - medium risk: 50–79 (first medium finding starts at 78);
    - low risk: 80–99 (first low finding starts at 95);
    - no finding: up to 100.

    Exact duplicate findings and missing-information entries are counted once
    so repeated model output cannot distort the result.
    """
    unique_findings = _unique_findings(findings)
    counts = {
        level: sum(1 for finding in unique_findings if finding[0] == level)
        for level in ("high", "medium", "low")
    }
    missing_count = len(
        {
            str(item).strip().lower()
            for item in missing_information
            if str(item).strip()
        }
    )

    high = counts["high"]
    medium = counts["medium"]
    low = counts["low"]

    if high:
        # Secondary findings and missing items use bounded/diminished penalties:
        # they matter, but cannot make a reasonably balanced contract collapse
        # to zero merely because the LLM described the same omissions twice.
        score = (
            45
            - 4 * (high - 1)
            - 1.5 * medium
            - 0.5 * low
            - min(5, 0.5 * missing_count)
        )
        return max(0, min(49, round(score)))
    if medium:
        score = (
            78
            - 4 * (medium - 1)
            - low
            - min(8, 0.75 * missing_count)
        )
        return max(50, min(79, round(score)))
    if low:
        score = 95 - 2 * (low - 1) - min(10, 0.5 * missing_count)
        return max(80, min(99, round(score)))

    score = 100 - 2 * missing_count
    return max(80, min(100, score))


__all__ = ["calculate_risk_score", "derive_risk_level"]
