"""Aggregate API v1 router."""

from fastapi import APIRouter, Depends

from app.api.deps import get_current_user
from app.api.v1.endpoints import agents, auth, chat, documents, health, retrieval

api_router = APIRouter()

# Public routes (no authentication required).
api_router.include_router(health.router)
api_router.include_router(auth.router)

# Protected routes (require a valid bearer token).
_protected = [Depends(get_current_user)]
api_router.include_router(documents.router, dependencies=_protected)
api_router.include_router(retrieval.router, dependencies=_protected)
api_router.include_router(chat.router, dependencies=_protected)
api_router.include_router(agents.router, dependencies=_protected)
