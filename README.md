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

## Frontend

```bash
cd frontend
cp .env.example .env
npm install
npm run dev
```

UI: http://localhost:5173 (login → dashboard). See [`frontend/README.md`](frontend/README.md).

## Repository layout

```
legaLink/
├── backend/           # FastAPI application
├── frontend/          # React + Vite UI (mockup)
├── docker-compose.yml # PostgreSQL + backend
└── README.md
```
