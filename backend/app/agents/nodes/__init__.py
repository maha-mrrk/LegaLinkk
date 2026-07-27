"""Reusable graph nodes wrapping existing services (LangGraph preparation).

Each node is a thin orchestration wrapper: it inherits from ``BaseGraphAgent``,
receives a ``GraphState``, delegates to an existing service (the single source
of truth), updates the state and returns it. No business logic lives here.
"""

from app.agents.nodes.chunking_node import ChunkingNode
from app.agents.nodes.cleaning_node import CleaningNode
from app.agents.nodes.command_parser_node import CommandParserNode
from app.agents.nodes.compliance_node import ComplianceNode
from app.agents.nodes.embedding_node import EmbeddingNode
from app.agents.nodes.finance_node import FinanceNode
from app.agents.nodes.generator_node import GeneratorNode
from app.agents.nodes.indexing_node import IndexingNode
from app.agents.nodes.legal_node import LegalNode
from app.agents.nodes.ocr_node import OCRNode
from app.agents.nodes.parser_node import ParserNode
from app.agents.nodes.reranker_node import RerankerNode
from app.agents.nodes.retrieval_node import RetrievalNode
from app.agents.nodes.synthesis_node import SynthesisNode

__all__ = [
    # Ingestion / RAG pipeline nodes
    "ParserNode",
    "OCRNode",
    "CleaningNode",
    "ChunkingNode",
    "EmbeddingNode",
    "IndexingNode",
    "RetrievalNode",
    "RerankerNode",
    "GeneratorNode",
    # Multi-agent graph nodes
    "CommandParserNode",
    "LegalNode",
    "FinanceNode",
    "ComplianceNode",
    "SynthesisNode",
]
