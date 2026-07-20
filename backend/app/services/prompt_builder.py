"""Build grounded RAG prompts for legal document Q&A."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence


DEFAULT_NO_ANSWER = (
    "I cannot answer this question based on the uploaded documents."
)

SYSTEM_INSTRUCTIONS = """You are LegalLink, a precise legal-document assistant.

Rules:
1. Answer ONLY using the retrieved document context provided by the user.
2. Do not use prior knowledge, assumptions, or external facts.
3. You may use the previous conversation only to resolve references
   (e.g. pronouns, "that document", follow-up questions), but still ground
   every factual claim in the retrieved context.
4. If the answer is not explicitly supported by the context, reply exactly with:
   {no_answer}
5. Prefer concise, factual answers. Quote or paraphrase only from the context.
6. When helpful, mention the source document filename and page number(s).
7. Never invent clause numbers, dates, parties, or amounts that are not in the context.
"""


@dataclass(frozen=True, slots=True)
class ChatPrompt:
    """OpenAI-compatible chat messages for grounded generation."""

    system: str
    user: str
    history: tuple[dict[str, str], ...] = ()

    def as_messages(self) -> list[dict[str, str]]:
        messages: list[dict[str, str]] = [{"role": "system", "content": self.system}]
        messages.extend(self.history)
        messages.append({"role": "user", "content": self.user})
        return messages


class PromptBuilder:
    """Construct system + history + context + question prompts."""

    def __init__(self, *, no_answer_message: str = DEFAULT_NO_ANSWER) -> None:
        self._no_answer = no_answer_message

    @property
    def no_answer_message(self) -> str:
        return self._no_answer

    def build(
        self,
        *,
        question: str,
        context: str,
        history: Sequence[dict[str, str]] | None = None,
    ) -> ChatPrompt:
        system = SYSTEM_INSTRUCTIONS.format(no_answer=self._no_answer)
        context_block = (context or "").strip()
        if not context_block:
            context_block = "(No retrieved context was available.)"

        history_turns = self._normalize_history(history or [])

        user = (
            "Retrieved legal context:\n"
            "---------------------\n"
            f"{context_block}\n"
            "---------------------\n\n"
            f"Current user question:\n{question.strip()}\n\n"
            "Answer grounded only on the context above "
            "(use conversation history only for references):"
        )
        return ChatPrompt(
            system=system,
            user=user,
            history=tuple(history_turns),
        )

    @staticmethod
    def _normalize_history(
        history: Sequence[dict[str, str]],
    ) -> list[dict[str, str]]:
        turns: list[dict[str, str]] = []
        for item in history:
            role = str(item.get("role") or "").strip().lower()
            content = str(item.get("content") or "").strip()
            if role not in {"user", "assistant"} or not content:
                continue
            turns.append({"role": role, "content": content})
        return turns
