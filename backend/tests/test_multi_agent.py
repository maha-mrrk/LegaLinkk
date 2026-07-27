"""Unit tests for the multi-agent LangGraph: command parsing, conditional
routing, and the synthesis node combining the three agent analyses."""

from __future__ import annotations

import pytest

from app.agents.nodes.command_parser_node import CommandParserNode
from app.agents.nodes.synthesis_node import SynthesisNode
from app.graphs.multi_agent_graph import (
    route_after_command,
    route_after_compliance,
    route_after_finance,
    route_after_legal,
)
from app.services.llm.base import LLMGenerationResult
from app.state.graph_state import GraphState


# --- CommandParserNode -------------------------------------------------------


@pytest.mark.parametrize(
    "message, expected_target, expected_query",
    [
        ("/legal analyse les clauses de résiliation", "legal", "analyse les clauses de résiliation"),
        ("/FINANCE quels sont les pénalités ?", "finance", "quels sont les pénalités ?"),
        ("/Compliance RGPD ?", "compliance", "RGPD ?"),
        ("  /legal   analyse  ", "legal", "analyse"),
    ],
)
async def test_command_parser_detects_prefix(
    message: str, expected_target: str, expected_query: str
) -> None:
    state: GraphState = {"user_query": message}
    result = await CommandParserNode().execute(state)
    assert result["target_agent"] == expected_target
    assert result["user_query"] == expected_query


async def test_command_parser_command_without_text_uses_default_question() -> None:
    result = await CommandParserNode().execute({"user_query": "/legal"})
    assert result["target_agent"] == "legal"
    assert result["user_query"]  # non-empty fallback question


async def test_command_parser_without_command_runs_all() -> None:
    result = await CommandParserNode().execute(
        {"user_query": "Quel est le délai de paiement ?"}
    )
    assert result["target_agent"] is None
    assert result["user_query"] == "Quel est le délai de paiement ?"


async def test_command_parser_ignores_mid_message_slash() -> None:
    # A slash that is not a leading command must not trigger routing.
    result = await CommandParserNode().execute(
        {"user_query": "Le taux est de 3/4 par mois"}
    )
    assert result["target_agent"] is None


# --- conditional routing -----------------------------------------------------


def test_routing_single_target_goes_straight_to_end() -> None:
    assert route_after_command({"target_agent": "legal"}) == "legal"
    assert route_after_command({"target_agent": "finance"}) == "finance"
    assert route_after_command({"target_agent": "compliance"}) == "compliance"

    # In single mode each agent stops immediately (END mapped as "end").
    assert route_after_legal({"target_agent": "legal"}) == "end"
    assert route_after_finance({"target_agent": "finance"}) == "end"
    assert route_after_compliance({"target_agent": "compliance"}) == "end"


def test_routing_default_chains_all_agents_then_synthesis() -> None:
    # No command → enter at legal and chain through to synthesis.
    assert route_after_command({"target_agent": None}) == "legal"
    assert route_after_legal({"target_agent": None}) == "finance"
    assert route_after_finance({"target_agent": None}) == "compliance"
    assert route_after_compliance({"target_agent": None}) == "synthesis"


# --- SynthesisNode -----------------------------------------------------------


class _FakeLLM:
    """Minimal LLMProvider stub capturing the messages it receives."""

    provider_name = "fake"
    model = "fake-model"

    def __init__(self) -> None:
        self.last_messages: list[dict[str, str]] | None = None

    async def complete(self, messages, *, temperature=None, max_tokens=None):
        self.last_messages = messages
        return LLMGenerationResult(
            content="Recommandation globale de synthèse.",
            model=self.model,
            total_tokens=42,
            finish_reason="stop",
        )


def _ok(agent: str, domain: str, answer: str) -> dict:
    return {
        "agent": agent,
        "domain": domain,
        "status": "ok",
        "answer": answer,
        "sources": [],
        "metadata": {},
    }


async def test_synthesis_consumes_all_three_results() -> None:
    llm = _FakeLLM()
    node = SynthesisNode(llm_provider=llm)
    state: GraphState = {
        "target_agent": None,
        "legal_result": _ok("LegalAgent", "legal", "Risque juridique élevé."),
        "finance_result": _ok("FinanceAgent", "finance", "Pénalités importantes."),
        "compliance_result": _ok("ComplianceAgent", "compliance", "Manque RGPD."),
    }

    result = await node.execute(state)

    assert result["final_recommendation"] == "Recommandation globale de synthèse."
    # The prompt must be built from all three analyses.
    user_prompt = llm.last_messages[-1]["content"]
    assert "Risque juridique élevé." in user_prompt
    assert "Pénalités importantes." in user_prompt
    assert "Manque RGPD." in user_prompt
    assert result["metadata"]["synthesis"]["inputs_used"] == [
        "Analyse juridique (Legal)",
        "Analyse financière (Finance)",
        "Analyse conformité (Compliance)",
    ]


async def test_synthesis_handles_missing_analysis() -> None:
    llm = _FakeLLM()
    node = SynthesisNode(llm_provider=llm)
    state: GraphState = {
        "legal_result": _ok("LegalAgent", "legal", "Analyse juridique."),
        "finance_result": {"agent": "FinanceAgent", "status": "error", "answer": None},
        "compliance_result": None,
    }

    result = await node.execute(state)

    assert result["final_recommendation"] == "Recommandation globale de synthèse."
    user_prompt = llm.last_messages[-1]["content"]
    assert "Analyse juridique." in user_prompt
    # The missing dimensions are flagged and only the available one is used.
    assert "indisponibles" in user_prompt
    assert result["metadata"]["synthesis"]["inputs_used"] == ["Analyse juridique (Legal)"]


async def test_synthesis_without_any_result_skips_llm() -> None:
    llm = _FakeLLM()
    node = SynthesisNode(llm_provider=llm)

    result = await node.execute({})

    assert llm.last_messages is None  # LLM never called
    assert "Aucune analyse" in result["final_recommendation"]
