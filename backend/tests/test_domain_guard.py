"""Tests ensuring explicitly selected agents stay inside their mandate."""

from unittest.mock import AsyncMock
from uuid import uuid4

from app.agents.nodes.finance_node import FinanceNode
from app.services.agent_stream import AgentStreamService
from app.services.domain_guard import DomainGuardService


def test_finance_agent_rejects_legal_question() -> None:
    result = DomainGuardService().assess(
        "Cette clause est-elle nulle et contraire à la loi ?",
        target_domain="finance",
    )
    assert result.allowed is False
    assert result.detected_domains == ("legal",)
    assert "/legal" in (result.message or "")


def test_compliance_agent_accepts_rgpd_question() -> None:
    result = DomainGuardService().assess(
        "Le traitement des données personnelles respecte-t-il le RGPD ?",
        target_domain="compliance",
    )
    assert result.allowed is True


def test_finance_agent_accepts_french_financial_analysis_request() -> None:
    result = DomainGuardService().assess(
        "Donne-moi une analyse financiere de ce contrat.",
        target_domain="finance",
    )
    assert result.allowed is True
    assert "finance" in result.detected_domains


def test_question_with_no_specialist_domain_is_rejected() -> None:
    result = DomainGuardService().assess(
        "Quel temps fera-t-il demain ?",
        target_domain="legal",
    )
    assert result.allowed is False
    assert result.detected_domains == ()


async def test_graph_node_does_not_call_generator_when_out_of_scope() -> None:
    generator = AsyncMock()
    node = FinanceNode(generator)
    state = {
        "user_query": "Cette clause est-elle juridiquement valable ?",
        "target_agent": "finance",
        "metadata": {},
    }

    result = await node.execute(state)

    assert result["finance_result"]["status"] == "out_of_scope"
    assert "/legal" in result["finance_result"]["answer"]
    generator.answer_question.assert_not_awaited()


async def test_stream_returns_refusal_without_retrieval_or_llm() -> None:
    generator = AsyncMock()
    service = AgentStreamService(generator)

    events = [
        event
        async for event in service.stream(
            "/finance Cette clause est-elle nulle selon la loi ?",
            user_id=uuid4(),
        )
    ]

    assert [event["type"] for event in events] == ["agent", "delta", "done"]
    assert events[-1]["metadata"]["status"] == "out_of_scope"
    assert "/legal" in events[-1]["answer"]
    generator.stream_answer.assert_not_called()


async def test_accepted_stream_uses_specialist_token_budget() -> None:
    class Generator:
        max_tokens = None

        async def stream_answer(self, _question, **kwargs):
            self.max_tokens = kwargs["max_tokens"]
            yield {"type": "delta", "text": "Analyse complète."}
            yield {"type": "done", "answer": "Analyse complète.", "metadata": {}}

    generator = Generator()
    service = AgentStreamService(generator)

    events = [
        event
        async for event in service.stream(
            "/finance Donne une analyse financière du contrat.",
            user_id=uuid4(),
        )
    ]

    assert generator.max_tokens == 8192
    assert events[-1]["type"] == "done"
