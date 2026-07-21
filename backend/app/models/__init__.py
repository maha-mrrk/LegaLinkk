"""ORM models.

Import all models here so Alembic can discover them via ``Base.metadata``.
"""

from app.db.base import Base
from app.models.chunk import DocumentChunk
from app.models.conversation import Conversation, Message, MessageRole
from app.models.document import Document, DocumentStatus, ExtractionMethod
from app.models.embedding import ChunkEmbedding, DocumentEmbedding, IndexStatus
from app.models.user import User

__all__ = [
    "Base",
    "ChunkEmbedding",
    "Conversation",
    "Document",
    "DocumentChunk",
    "DocumentEmbedding",
    "DocumentStatus",
    "ExtractionMethod",
    "IndexStatus",
    "Message",
    "MessageRole",
    "User",
]
