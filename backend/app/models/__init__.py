"""ORM models.

Import all models here so Alembic can discover them via ``Base.metadata``.
"""

from app.db.base import Base
from app.models.analysis import ANALYSIS_VERSION, AnalysisStatus, DocumentAnalysis
from app.models.chunk import DocumentChunk
from app.models.conversation import Conversation, Message, MessageRole
from app.models.document import Document, DocumentStatus, ExtractionMethod
from app.models.embedding import ChunkEmbedding, DocumentEmbedding, IndexStatus
from app.models.generated_document import GeneratedDocument, GeneratedDocumentKind
from app.models.user import User

__all__ = [
    "ANALYSIS_VERSION",
    "AnalysisStatus",
    "Base",
    "ChunkEmbedding",
    "Conversation",
    "Document",
    "DocumentAnalysis",
    "DocumentChunk",
    "DocumentEmbedding",
    "DocumentStatus",
    "ExtractionMethod",
    "GeneratedDocument",
    "GeneratedDocumentKind",
    "IndexStatus",
    "Message",
    "MessageRole",
    "User",
]
