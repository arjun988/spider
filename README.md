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

- [x] **Phase 1 — Foundation**: Docker Compose, schema, FastAPI, dashboard shell, config
- [x] **Phase 2 — GitHub**: App JWT/installation tokens, webhooks (idempotent), repo sync, PR/diff fetch, `/review` commands, review publisher
- [x] **Phase 3 — Intelligence**: clone/fetch, Tree-sitter symbols, chunking, Gemini embeddings, pgvector retrieval, incremental index
- [x] **Phase 4 — AI review**: LangGraph stages — analyze → retrieve → bug/security/test → verify → decide
- [x] **Phase 5 — Verify & publish**: static analysis, isolated Docker sandbox, inline GitHub comments
- [x] **Phase 6 — Admin**: BYOK with live key validation, usage/cost charts, budgets, repo actions
- [x] **Phase 7 — Quality**: unit tests, sample buggy repo, sandbox Dockerfile, docs

## Quick start

### Prerequisites

- Docker & Docker Compose
- GitHub App credentials (for live PR reviews)
- Gemini API key (BYOK)

### 1. Configure environment

```bash
cp .env.example .env
```

Set at least:

- `SECRET_KEY` / `ENCRYPTION_KEY`
- `GEMINI_API_KEY` (or configure in Settings UI)
- `GITHUB_APP_ID`, `GITHUB_APP_WEBHOOK_SECRET`, `GITHUB_APP_NAME`
- Place private key at `secrets/github-app.pem`

### 2. Start the stack

```bash
docker compose up --build
```

| Service | URL |
|---------|-----|
| Dashboard | http://localhost:3000 |
| API docs | http://localhost:8000/docs |
| Health | http://localhost:8000/api/health |

Optional sandbox image:

```bash
docker build -t spider-sandbox:latest -f backend/Dockerfile.sandbox backend
```

### 3. Install the GitHub App

1. Create a GitHub App with permissions: Contents (read), Pull requests (read/write), Metadata (read)
2. Subscribe to `pull_request`, `installation`, `installation_repositories`, `issue_comment`
3. Webhook URL: `https://<host>/api/webhooks/github`
4. Install on your org; open **Repositories** in the dashboard and **Sync**
5. Trigger indexing with **Re-index**

### 4. Review flow

- Opening/updating a PR enqueues an async review (deduped per commit SHA)
- Comment `/review` or `/review-again` on a PR to trigger manually
- Verified findings are posted as inline review comments; clean PRs get a summary with no invented issues

## Manual review trigger (API)

```bash
curl -X POST http://localhost:8000/api/pull-requests/<pr-uuid>/review
```

## Tests

```bash
docker compose exec backend pytest -q
```

Sample intentional-bug repo: `samples/buggy_repo/` (SQL injection, hardcoded secret, missing funds check, division by zero, path traversal).

## Security notes

- API keys encrypted at rest; responses only return masked values
- Installation tokens and PEM keys never sent to the frontend
- Webhook HMAC verification required in production
- Sandbox runs read-only, non-root, no network, with CPU/memory/PID limits
- Monthly Gemini budget enforced before review tasks run

## Project layout

```
backend/app/
  github/       # App auth, webhooks, PR, publisher
  indexing/     # clone, parse, embed, retrieve
  agents/       # LangGraph multi-stage review
  verification/ # sandbox + static analysis
  services/     # review, cost, analytics, gemini
  api/routes/   # HTTP API
frontend/app/   # Dashboard pages
samples/        # Fixtures for pipeline validation
```
