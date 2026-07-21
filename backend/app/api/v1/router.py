"""Aggregate API v1 router."""

from fastapi import APIRouter

from app.api.v1.endpoints import agents, chat, documents, health, retrieval

api_router = APIRouter()
api_router.include_router(health.router)
api_router.include_router(documents.router)
api_router.include_router(retrieval.router)
api_router.include_router(chat.router)
api_router.include_router(agents.router)
