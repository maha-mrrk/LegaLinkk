"""Build grounded RAG prompts for legal document Q&A."""

from __future__ import annotations

from dataclasses import dataclass


DEFAULT_NO_ANSWER = (
    "I cannot answer this question based on the uploaded documents."
)

SYSTEM_INSTRUCTIONS = """You are LegalLink, a precise legal-document assistant.

Rules:
1. Answer ONLY using the retrieved document context provided by the user.
2. Do not use prior knowledge, assumptions, or external facts.
3. If the answer is not explicitly supported by the context, reply exactly with:
   {no_answer}
4. Prefer concise, factual answers. Quote or paraphrase only from the context.
5. When helpful, mention the source document filename and page number(s).
6. Never invent clause numbers, dates, parties, or amounts that are not in the context.
"""


@dataclass(frozen=True, slots=True)
class ChatPrompt:
    """OpenAI-compatible chat messages for grounded generation."""

    system: str
    user: str

    def as_messages(self) -> list[dict[str, str]]:
        return [
            {"role": "system", "content": self.system},
            {"role": "user", "content": self.user},
        ]


class PromptBuilder:
    """Construct system + user prompts for the GeneratorService."""

    def __init__(self, *, no_answer_message: str = DEFAULT_NO_ANSWER) -> None:
        self._no_answer = no_answer_message

    @property
    def no_answer_message(self) -> str:
        return self._no_answer

    def build(self, *, question: str, context: str) -> ChatPrompt:
        system = SYSTEM_INSTRUCTIONS.format(no_answer=self._no_answer)
        context_block = (context or "").strip()
        if not context_block:
            context_block = "(No retrieved context was available.)"

        user = (
            "Retrieved legal context:\n"
            "---------------------\n"
            f"{context_block}\n"
            "---------------------\n\n"
            f"User question:\n{question.strip()}\n\n"
            "Answer grounded only on the context above:"
        )
        return ChatPrompt(system=system, user=user)
