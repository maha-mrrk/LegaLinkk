"""Tests for deterministic, severity-sensitive contract scoring."""

from app.services.risk_score import calculate_risk_score, derive_risk_level


def _findings(level: str, count: int) -> list[dict[str, str]]:
    return [
        {
            "level": level,
            "category": f"category-{index}",
            "detail": f"finding-{index}",
        }
        for index in range(count)
    ]


def test_excellent_contract_scores_100() -> None:
    assert calculate_risk_score([]) == 100


def test_high_risks_progressively_lower_score() -> None:
    assert calculate_risk_score(_findings("high", 1)) == 45
    assert calculate_risk_score(_findings("high", 2)) == 41
    assert calculate_risk_score(_findings("high", 5)) == 29
    assert calculate_risk_score(_findings("high", 16)) == 0


def test_score_bands_match_highest_severity() -> None:
    assert calculate_risk_score(_findings("medium", 1)) == 78
    assert calculate_risk_score(_findings("medium", 10)) == 50
    assert calculate_risk_score(_findings("low", 1)) == 95
    assert calculate_risk_score(_findings("low", 10)) == 80


def test_secondary_findings_and_missing_information_add_penalties() -> None:
    findings = [
        *_findings("high", 1),
        *_findings("medium", 2),
        *_findings("low", 3),
    ]
    assert calculate_risk_score(findings, ["Date", "Signature"]) == 40


def test_exact_duplicates_are_counted_once() -> None:
    finding = {"level": "high", "category": "ordre public", "detail": "Clause nulle"}
    assert calculate_risk_score([finding, finding, finding]) == 45


def test_reported_balanced_contract_does_not_collapse_to_zero() -> None:
    findings = [
        *_findings("high", 2),
        *_findings("medium", 6),
        *_findings("low", 4),
    ]
    missing = [f"missing-{index}" for index in range(11)]
    assert calculate_risk_score(findings, missing) == 25


def test_level_is_derived_from_highest_finding() -> None:
    findings = [*_findings("medium", 6), *_findings("high", 2)]
    assert derive_risk_level(findings, default="medium") == "high"
