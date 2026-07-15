# LegalLink Backend

FastAPI backend for **LegalLink** — an AI-powered platform for analysing legal contracts and regulatory documents.

This repository currently includes the FastAPI infrastructure and the Document Management module.
AI / RAG / OCR / Celery / Redis are intentionally out of scope for later increments.

## Stack

| Component | Choice |
|-----------|--------|
| Runtime | Python 3.12 |
| Package manager | Poetry |
| Framework | FastAPI |
| ORM | SQLAlchemy 2.0 (async) |
| Migrations | Alembic |
| Database | PostgreSQL |
| Validation | Pydantic v2 |
| Containers | Docker + Docker Compose |

## Project structure

```
backend/
├── app/
│   ├── api/              # HTTP routes (versioned)
│   │   └── v1/
│   │       └── endpoints/
│   ├── core/             # Config, logging
│   ├── db/               # Engine, session, base model
│   ├── models/           # SQLAlchemy ORM models
│   ├── repositories/     # Data-access layer
│   ├── schemas/          # Pydantic request/response schemas
│   ├── services/         # Business logic
│   ├── utils/            # Shared helpers
│   └── main.py           # Application factory
├── storage/documents/    # Local PDF storage
├── alembic/              # Database migrations
├── tests/
├── Dockerfile
├── pyproject.toml
└── .env.example
```

## Prerequisites

- Python 3.12+
- [Poetry](https://python-poetry.org/docs/#installation)
- Docker & Docker Compose (optional, recommended)

## Quick start (Docker)

From the repository root:

```bash
# 1. Create environment file
cp backend/.env.example backend/.env

# 2. Start PostgreSQL + API
docker compose up --build

# 3. Apply database migrations
docker compose exec backend poetry run alembic upgrade head
```

Services:

| Service | URL |
|---------|-----|
| API | http://localhost:8000 |
| Swagger UI | http://localhost:8000/docs |
| ReDoc | http://localhost:8000/redoc |
| Health | http://localhost:8000/api/v1/health |
| PostgreSQL | localhost:5432 |

## Local development (without Docker for the API)

```bash
# Start only the database
docker compose up db -d

# Configure environment (set POSTGRES_HOST=localhost)
cp backend/.env.example backend/.env

cd backend
poetry install
poetry run uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

## Environment variables

Copy `.env.example` to `.env` and adjust as needed:

| Variable | Description | Default |
|----------|-------------|---------|
| `APP_NAME` | Application display name | `LegalLink` |
| `APP_ENV` | Environment (`development` / `production`) | `development` |
| `DEBUG` | Enable SQL echo & verbose behaviour | `false` |
| `API_V1_PREFIX` | API route prefix | `/api/v1` |
| `LOG_LEVEL` | Logging level | `INFO` |
| `POSTGRES_USER` | Database user | `legallink` |
| `POSTGRES_PASSWORD` | Database password | `legallink` |
| `POSTGRES_HOST` | Database host | `localhost` |
| `POSTGRES_PORT` | Database port | `5432` |
| `POSTGRES_DB` | Database name | `legallink` |

## Document Management API

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/api/v1/documents` | Upload a PDF (`multipart/form-data`, field `file`) |
| `GET` | `/api/v1/documents` | List documents |
| `GET` | `/api/v1/documents/{id}` | Get document metadata |
| `DELETE` | `/api/v1/documents/{id}` | Delete document + stored file |

Validation rules:

- Only PDF files (extension + MIME + `%PDF` magic bytes)
- Maximum size: 25 MB
- Files stored under `storage/documents/` with a UUID filename
- After upload, text is extracted with PyMuPDF and stored in PostgreSQL (`extracted_text`, `page_count`)

Example upload:

```bash
curl -F "file=@./contract.pdf;type=application/pdf" http://localhost:8000/api/v1/documents
```

## Database migrations

```bash
cd backend

# Autogenerate a migration after adding models
poetry run alembic revision --autogenerate -m "describe change"

# Apply migrations
poetry run alembic upgrade head

# Roll back one revision
poetry run alembic downgrade -1
```

## Tests

```bash
cd backend
poetry install
poetry run pytest
```

## API documentation

Interactive OpenAPI docs are served automatically by FastAPI:

- Swagger UI → `/docs`
- ReDoc → `/redoc`
- OpenAPI JSON → `/openapi.json`

## Architecture notes

- **Modular layout** — API, domain models, repositories, and services are separated so features can grow without coupling.
- **Async SQLAlchemy** — `asyncpg` for the app; sync `psycopg2` for Alembic.
- **Config via `.env`** — `pydantic-settings` loads and validates all configuration.
- **Health check** — `GET /api/v1/health` reports process and database status.

## Out of scope (this step)

The following will be added in later increments:

- AI / LangGraph / OpenAI Agents SDK
- RAG (retrieval + reranker)
- OCR
- Celery / Redis
- Laravel gateway / React frontend
- LangFuse observability
