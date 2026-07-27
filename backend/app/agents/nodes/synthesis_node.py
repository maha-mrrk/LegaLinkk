"""SynthesisNode — cross-references the 3 agent analyses into one recommendation.

Thin orchestration node: it reads ``legal_result`` / ``finance_result`` /
``compliance_result`` from the shared state and asks the existing LLM provider
(``services/llm``) to weigh and combine them into a single, actionable
recommendation. It never re-runs retrieval and never invents facts — the
recommendation is built explicitly from the three analyses already on the state.
"""

from __future__ import annotations

from typing import Any

from app.agents.base_agent import BaseGraphAgent
from app.agents.nodes._state_utils import ensure_metadata
from app.agents.nodes.agent_prompts import SYNTHESIS_SYSTEM_PROMPT
from app.core.config import Settings, get_settings
from app.core.exceptions import AppError
from app.core.logging import get_logger
from app.services.llm import LLMProvider, get_llm_provider
from app.state.graph_state import GraphState

logger = get_logger(__name__)

# (state key, human label) for the three analyses, in synthesis order.
_INPUTS: tuple[tuple[str, str], ...] = (
    ("legal_result", "Analyse juridique (Legal)"),
    ("finance_result", "Analyse financière (Finance)"),
    ("compliance_result", "Analyse conformité (Compliance)"),
)


class SynthesisNode(BaseGraphAgent):
    """Produce ``final_recommendation`` from the three specialized analyses."""

    def __init__(
        self,
        llm_provider: LLMProvider | None = None,
        *,
        settings: Settings | None = None,
    ) -> None:
        self._settings = settings or get_settings()
        self._llm = llm_provider

    def _get_llm(self) -> LLMProvider:
        if self._llm is None:
            self._llm = get_llm_provider(self._settings)
        return self._llm

    @property
    def name(self) -> str:
        return "synthesis"

    @property
    def description(self) -> str:
        return (
            "Cross-reference the legal, finance and compliance analyses into a "
            "single weighted recommendation."
        )

    async def execute(self, state: GraphState) -> GraphState:
        available: list[tuple[str, dict[str, Any]]] = []
        missing: list[str] = []
        for key, label in _INPUTS:
            result = state.get(key) or {}
            if result.get("status") == "ok" and (result.get("answer") or "").strip():
                available.append((label, result))
            else:
                missing.append(label)

        if not available:
            logger.warning("[multi_agent] synthesis: no usable analyses to combine")
            state["final_recommendation"] = (
                "Aucune analyse spécialisée n'a pu être produite pour ce contrat. "
                "Veuillez réessayer."
            )
            return state

        sections = [
            f"### {label}\n{result['answer'].strip()}" for label, result in available
        ]
        missing_note = (
            f"\n\nNote : les analyses suivantes sont indisponibles : "
            f"{', '.join(missing)}."
            if missing
            else ""
        )
        user_prompt = (
            "Voici les analyses spécialisées d'un même contrat. Produis une "
            "recommandation globale qui les croise et les pondère explicitement.\n\n"
            + "\n\n".join(sections)
            + missing_note
        )
        messages = [
            {"role": "system", "content": SYNTHESIS_SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ]

        logger.info(
            "[multi_agent] synthesis over %s/%s analyses",
            len(available),
            len(_INPUTS),
        )
        try:
            completion = await self._get_llm().complete(
                messages, temperature=self._settings.llm_temperature
            )
            recommendation = (completion.content or "").strip()
        except Exception as exc:
            logger.exception("[multi_agent] synthesis generation failed")
            message = (
                exc.message
                if isinstance(exc, AppError)
                else "La synthèse n'a pas pu être générée."
            )
            state["final_recommendation"] = message
            return state

        state["final_recommendation"] = recommendation or (
            "La synthèse n'a pas pu être générée."
        )
        metadata = ensure_metadata(state)
        metadata["synthesis"] = {
            "provider": self._get_llm().provider_name,
            "model": completion.model,
            "tokens_used": completion.total_tokens,
            "inputs_used": [label for label, _ in available],
        }
        return state
