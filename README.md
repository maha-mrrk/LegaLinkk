# LegalLink

AI-powered web platform that helps companies analyse legal contracts and regulatory documents.

## Current status

**Step 1 — FastAPI backend skeleton** is implemented. See [`backend/README.md`](backend/README.md) for setup instructions.

Planned architecture (later increments):

- React (frontend)
- Laravel (API gateway / authentication)
- FastAPI (AI backend) ← *initialized*
- PostgreSQL + pgvector
- LangGraph / OpenAI Agents SDK
- RAG (retrieval + reranker)
- Redis / Celery
- LangFuse
- Docker

## Quick start

```bash
cp backend/.env.example backend/.env
docker compose up --build
```

| Resource | URL |
|----------|-----|
| API docs (Swagger) | http://localhost:8000/docs |
| Health check | http://localhost:8000/api/v1/health |

## Repository layout

```
legaLink/
├── backend/           # FastAPI application
├── docker-compose.yml # PostgreSQL + backend
└── README.md
```
