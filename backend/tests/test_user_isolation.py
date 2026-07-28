"""Regression tests for tenant scoping and IDOR protection."""

from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from app.core.exceptions import NotFoundError
from app.repositories.conversation import ConversationRepository
from app.repositories.document import DocumentRepository
from app.repositories.retrieval import RetrievalRepository
from app.services.conversation import ConversationService
from app.services.document import DocumentService


def _result(*, scalar=None, rows=None):
    result = SimpleNamespace()
    result.scalar_one_or_none = lambda: scalar
    result.scalar_one = lambda: scalar
    result.all = lambda: rows or []
    result.scalars = lambda: SimpleNamespace(all=lambda: rows or [])
    return result


async def test_document_lookup_scopes_uuid_to_authenticated_user() -> None:
    session = AsyncMock()
    session.execute.return_value = _result()
    repository = DocumentRepository(session)
    user_a, user_b, document_id = uuid4(), uuid4(), uuid4()

    await repository.get_by_id(document_id, user_id=user_a)
    statement_a = session.execute.await_args.args[0]
    assert statement_a.compile().params["user_id_1"] == user_a

    await repository.get_by_id(document_id, user_id=user_b)
    statement_b = session.execute.await_args.args[0]
    assert statement_b.compile().params["user_id_1"] == user_b
    assert "documents.user_id" in str(statement_b)


async def test_conversation_lookup_scopes_uuid_to_authenticated_user() -> None:
    session = AsyncMock()
    session.execute.return_value = _result()
    repository = ConversationRepository(session)
    user_a, conversation_id = uuid4(), uuid4()

    await repository.get_by_id(conversation_id, user_id=user_a)
    statement = session.execute.await_args.args[0]

    assert statement.compile().params["user_id_1"] == user_a
    assert "conversations.user_id" in str(statement)


async def test_library_wide_vector_search_is_always_user_scoped() -> None:
    session = AsyncMock()
    session.execute.return_value = _result(rows=[])
    repository = RetrievalRepository(session)
    user_b = uuid4()

    await repository.search_similar([0.1, 0.2], user_id=user_b, top_k=5)
    statement = session.execute.await_args.args[0]
    compiled = statement.compile()

    assert compiled.params["user_id_1"] == user_b
    assert "documents.user_id" in str(statement)
    assert "JOIN documents" in str(statement)


async def test_full_document_retrieval_checks_owner_through_documents_join() -> None:
    session = AsyncMock()
    session.execute.return_value = _result(rows=[])
    repository = RetrievalRepository(session)
    user_b, document_id = uuid4(), uuid4()

    await repository.list_all_by_document(document_id, user_id=user_b)
    statement = session.execute.await_args.args[0]
    compiled = statement.compile()

    assert compiled.params["user_id_1"] == user_b
    assert compiled.params["document_id_1"] == document_id
    assert "documents.user_id" in str(statement)


async def test_foreign_document_is_reported_as_not_found() -> None:
    service = DocumentService.__new__(DocumentService)
    service._repo = AsyncMock()
    service._repo.get_by_id.return_value = None
    user_b, document_a = uuid4(), uuid4()

    with pytest.raises(NotFoundError):
        await service.get_document(document_a, user_id=user_b)

    service._repo.get_by_id.assert_awaited_once_with(
        document_a, user_id=user_b
    )


async def test_foreign_conversation_cannot_receive_messages() -> None:
    session = AsyncMock()
    service = ConversationService(session)
    service._repo = AsyncMock()
    service._repo.get_by_id.return_value = None
    user_b, conversation_a = uuid4(), uuid4()

    with pytest.raises(NotFoundError):
        await service.append_message(
            conversation_a,
            user_id=user_b,
            role="user",
            content="Tentative IDOR",
        )

    service._repo.append_message.assert_not_awaited()


@pytest.mark.parametrize(
    ("payload", "expected"),
    [
        ({"risk_level": "low"}, 85),
        ({"risk_level": "medium"}, 58),
        ({"risk_level": "high"}, 32),
        ({"metadata": {"risk_score": 72.4}}, 72),
        ({"risk_score": 150}, 100),
        ({}, None),
    ],
)
def test_history_score_uses_persisted_analysis(
    payload: dict, expected: int | None
) -> None:
    assert DocumentService._analysis_score(payload) == expected
