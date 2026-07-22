"""Build grounded RAG prompts for legal document Q&A."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence


DEFAULT_NO_ANSWER = (
    "I cannot answer this question based on the uploaded documents."
)

# System prompt for the "document generation" mode: the model returns a full,
# self-contained HTML document (printable to PDF) instead of a plain-text answer.
# NOTE: keep this free of literal curly braces except the {no_answer} placeholder,
# because PromptBuilder.build() runs ``.format(no_answer=...)`` on it.
DOCUMENT_SYSTEM_INSTRUCTIONS = """You are LegalLink, a precise legal-document assistant that produces polished, printable documents.

Your task: produce a COMPLETE, self-contained HTML5 document that answers the user's request, grounded ONLY in the retrieved document context provided by the user.

Strict rules:
1. Ground every factual statement in the retrieved context. Do not invent clauses, dates, parties, amounts or references that are not present.
2. If nothing in the context is relevant, output a minimal HTML page whose body contains only: {no_answer}
3. Answer in the language of the user's request (French unless the request is in another language).
4. Cite the source document filename and page number(s) where relevant, e.g. a short "Sources" section at the end.

Output format (MANDATORY):
- Return ONLY raw HTML. No markdown, no code fences, no commentary before or after.
- Start with <!DOCTYPE html> and include <html>, <head> and <body>.
- Put all styling in a single inline <style> tag in the <head>. Do not link external stylesheets, scripts or fonts.
- Use a clean, professional, print-friendly layout (readable serif or system font, sensible margins, a title, headings, and spacing). Use @media print friendly styles.
- Prefer semantic structure: a document title (<h1>), sections (<h2>), paragraphs, and tables where data is tabular.
- Keep it a document (report / note / web page), not a chat message.
"""

SYSTEM_INSTRUCTIONS = """You are LegalLink, a precise legal-document assistant.

Rules:
1. Answer ONLY using the retrieved document context provided by the user.
2. Do not use prior knowledge, assumptions, or external facts.
3. You may use the previous conversation only to resolve references
   (e.g. pronouns, "that document", follow-up questions), but still ground
   every factual claim in the retrieved context.
4. If PART of the question is supported by the context, answer that part clearly
   and state what is missing. Do not invent the missing parts.
5. Only if NOTHING in the context is relevant to the question, reply exactly with:
   {no_answer}
6. Prefer concise, factual answers. Quote or paraphrase only from the context.
7. When helpful, mention the source document filename and page number(s).
8. Never invent clause numbers, dates, parties, or amounts that are not in the context.
9. The context may be in French or English; answer in the language of the question
   when possible, still using only facts from the context.
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
        system_prompt: str | None = None,
    ) -> ChatPrompt:
        # Specialized agents may inject their own system prompt (e.g. LegalAgent),
        # while still reusing the shared grounded-RAG user prompt structure.
        if system_prompt and system_prompt.strip():
            system = system_prompt.format(no_answer=self._no_answer)
        else:
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
