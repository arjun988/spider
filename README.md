# Spider

Internal AI-powered GitHub code review platform. Context-aware PR reviews via Gemini, repository indexing with pgvector, and verified inline comments on GitHub.

**Product principle:** optimize for finding real bugs, not producing more comments.

## Architecture

| Layer | Stack |
|-------|--------|
| Frontend | Next.js 15 (App Router), TypeScript, Tailwind, TanStack Query, Recharts |
| Backend | FastAPI, SQLAlchemy, Alembic, Celery, LangGraph |
| Data | PostgreSQL + pgvector, Redis |
| AI | Google Gemini (BYOK) via official `google-genai` SDK |
| Code intel | Tree-sitter, ripgrep, Git |

## Phase status

- [x] **Phase 1 — Foundation** (this release): Docker Compose, database schema, FastAPI, dashboard shell, config/BYOK settings API
- [ ] Phase 2 — GitHub App, webhooks, PR/diff fetching
- [ ] Phase 3 — Repository indexing & retrieval
- [ ] Phase 4 — Multi-stage LangGraph review engine
- [ ] Phase 5 — Sandbox verification & GitHub comment publishing
- [ ] Phase 6 — Analytics, budgets, admin polish
- [ ] Phase 7 — Integration tests, hardening, docs

## Quick start

### Prerequisites

- Docker & Docker Compose
- (Optional for local Python) Python 3.12+, Node 22+

### 1. Configure environment

```bash
cp .env.example .env
```

Edit `.env` and set at least:

- `SECRET_KEY` / `ENCRYPTION_KEY` — long random strings
- `GEMINI_API_KEY` — optional for Phase 1; required once reviews run
- `GITHUB_APP_*` — required from Phase 2 onward

Place the GitHub App private key at `secrets/github-app.pem` when ready (Phase 2).

### 2. Start the stack

```bash
docker compose up --build
```

Services:

| Service | URL |
|---------|-----|
| Dashboard | http://localhost:3000 |
| API / docs | http://localhost:8000/docs |
| Health | http://localhost:8000/api/health |
| Postgres | localhost:5432 |
| Redis | localhost:6379 |

Migrations run automatically on backend startup (`alembic upgrade head`).

### 3. Local backend tests (no Docker DB required for unit tests)

```bash
cd backend
python -m venv .venv
# Windows: .venv\Scripts\activate
source .venv/bin/activate
pip install -r requirements.txt
pytest tests/test_health.py -q
```

### 4. Local frontend

```bash
cd frontend
npm install
npm run dev
```

Point `NEXT_PUBLIC_API_URL` at the running API (default `http://localhost:8000`).

## GitHub App setup (Phase 2)

1. Create a GitHub App in your organization settings.
2. Permissions (minimum):
   - Repository contents: Read
   - Pull requests: Read & Write
   - Commit statuses: Read & Write
   - Metadata: Read
3. Subscribe to:
   - `pull_request` (opened, synchronize, reopened, closed)
   - `installation` (created, deleted)
   - `issue_comment` (for `/review` and `/review-again`)
4. Webhook URL: `https://<your-host>/api/webhooks/github`
5. Set webhook secret → `GITHUB_APP_WEBHOOK_SECRET`
6. Download private key → `secrets/github-app.pem`
7. Set `GITHUB_APP_ID`, client ID/secret in `.env`

## Gemini BYOK

Configure via **Settings** in the dashboard, or set `GEMINI_API_KEY` in `.env` for development.

- Keys are encrypted at rest (Fernet)
- API responses only return masked keys
- Primary and embedding model names are stored in `model_configurations` and read by agents (never hardcoded in review code)

Default models (overridable):

- Chat / review: `gemini-2.0-flash`
- Embeddings: `text-embedding-004`

## Project layout

```
backend/
  app/
    api/routes/     # HTTP endpoints
    core/           # config, security, encryption, logging
    database/       # engines & sessions
    models/         # SQLAlchemy models
    workers/        # Celery
    github/         # Phase 2
    indexing/       # Phase 3
    agents/         # Phase 4
    verification/   # Phase 5
    services/       # orchestration helpers
  alembic/          # migrations
frontend/
  app/              # Next.js pages
  components/       # UI
  lib/              # API client, utils
```

## Security notes

- Never commit `.env`, PEM keys, or API keys
- Webhook signatures verified with HMAC-SHA256
- Admin/API secrets stay server-side
- PR code execution (Phase 5) runs only in isolated containers with resource limits and no access to app secrets
