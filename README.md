# Spider

**AI code review that optimizes for real bugs — not more comments.**

Spider is an internal GitHub code-review platform. It indexes your repositories, runs a multi-stage AI review on every pull request, verifies findings before they ship, and posts only high-signal inline comments — with Check Runs, cost controls, and an operator dashboard.

---

## Why Spider

Most AI reviewers flood PRs with noise. Spider is built around a different bar:

- **Precision over volume** — findings must clear severity, confidence, failure-scenario, and independent verification gates
- **Context-aware** — Tree-sitter symbols + embeddings retrieve the right code, not just the diff hunk
- **Human-in-the-loop learning** — false-positive feedback raises the bar for noisy categories on future reviews
- **Operator-ready** — budgets, audit logs, webhook DLQ, onboarding, and usage exports in one place

---

## Features

### AI review pipeline
- Multi-stage LangGraph flow: **analyze → retrieve → bug/security/test hunt → verify → decide**
- Static analysis supplements (secrets, SQL concatenation) merged into the same publish gates
- Optional isolated Docker sandbox for light verification annotations
- Deduped per commit SHA; reclaim for stuck queued jobs
- Manual triggers via dashboard, API, or PR comments (`/review`, `/review-again`)

### GitHub delivery
- Inline review comments on the PR diff (no invented issues on clean PRs)
- **Check Runs** with pass/fail — fails when published critical/high findings exist
- Idempotent webhooks with HMAC verification, retries, dead-letter visibility, and admin replay

### Repository intelligence
- Clone/fetch via GitHub App installation tokens
- Tree-sitter parsing for Python, JS/TS, Go, Rust, Java (+ optional C/C++/C#/Ruby/PHP/Kotlin)
- Chunking, embeddings, and **pgvector** retrieval for context
- Full and **incremental** re-index with live progress (`files_processed` / `total_files`)
- Per-repo **review rules**: ignore paths, severity/confidence floors, language allow-lists, max findings

### Precision & feedback
- Org and per-repo severity / confidence thresholds
- Feedback types: helpful, false positive, dismissed, fixed
- Aggregated FP rates by **category and path** injected into verifier LLM prompts
- Feedback-adjusted confidence floors before publish

### Dashboard
- Overview metrics, repositories, pull requests, review detail, usage & cost charts
- Settings for LLM provider (Gemini or LiteLLM), budgets, and review defaults
- **Onboarding** checklist: install app → configure LLM → sync → index → first review
- **Audit & observability**: action log, week metrics, webhook DLQ replay
- CSV exports for findings and usage
- Light / dark theme (slate + indigo design system)
- GitHub OAuth SSO with org roles (`admin` / `member` / `viewer`); org switcher when multi-tenant

### Cost & reliability
- BYOK Gemini (encrypted at rest) or LiteLLM OpenAI-compatible proxy
- Monthly budget enforcement before review tasks run
- Usage timeseries, model breakdown, cost-by-repository
- Optional Sentry via `SENTRY_DSN`

---

## Integrations

| Integration | What Spider uses it for |
|-------------|-------------------------|
| **GitHub App** | Installations, repo sync, PR diffs, webhooks, inline reviews, Check Runs, `/review` comments |
| **Google Gemini** | Default LLM + embeddings via official `google-genai` SDK (BYOK) |
| **LiteLLM** | Optional OpenAI-compatible proxy for multi-provider routing (Compose service on `:4000`) |
| **PostgreSQL + pgvector** | Primary store and semantic code retrieval |
| **Redis + Celery** | Async indexing, reviews, webhook retry, stuck-job reclaim |
| **Docker sandbox** | Optional isolated checks (`spider-sandbox` image) |
| **Sentry** | Optional error/trace reporting when `SENTRY_DSN` is set |
| **Cloudflare Tunnel / ngrok** | Local webhook reachability for GitHub (bring your own tunnel) |

---

## Architecture

```
GitHub PR / webhook
        │
        ▼
   FastAPI API ──► Celery workers
        │              │
        │              ├─ Index (Tree-sitter → embed → pgvector)
        │              └─ Review (LangGraph → verify → publish + Check Run)
        ▼
   Next.js dashboard ◄── JWT / GitHub OAuth
```

| Layer | Stack |
|-------|--------|
| Frontend | Next.js 15, TypeScript, Tailwind, TanStack Query, Recharts |
| Backend | FastAPI, SQLAlchemy, Alembic, Celery, LangGraph |
| Data | PostgreSQL + pgvector, Redis |
| AI | Gemini (default) or LiteLLM proxy |
| Code intel | Tree-sitter, Git, ripgrep |

---

## How a review works

1. GitHub sends `pull_request` / `issue_comment` to `/api/webhooks/github`
2. Spider upserts the PR, enqueues a Celery review job (deduped on commit SHA)
3. Check Run moves to **in_progress**
4. Pipeline analyzes the change, retrieves context, hunts bugs/security/test gaps
5. Verifier + decision gates apply thresholds, repo rules, and feedback signals
6. Accepted findings become inline GitHub review comments; Check Run completes **success** or **failure**
7. Operators inspect results, leave feedback, and export metrics from the dashboard

---

## Security

- LLM API keys encrypted at rest; API responses return masked values only
- GitHub App private key and installation tokens never leave the backend
- Webhook HMAC (`X-Hub-Signature-256`) required in production
- Sandbox: read-only, non-root, no network, CPU/memory/PID limits
- Monthly budget gate before expensive review work
- Role-gated mutating APIs (`admin` / `member`); development may use auth bypass via `AUTH_DISABLED_IN_DEV`

---

## Project layout

```
backend/app/
  api/routes/     # HTTP API (auth, repos, reviews, audit, exports, webhooks, …)
  github/         # App auth, webhooks, PR fetch, publisher, Check Runs
  indexing/       # clone, parse, embed, retrieve
  agents/         # LangGraph multi-stage review + verifier
  verification/   # static analysis + sandbox
  services/       # review orchestration, LLM clients, feedback signals, audit
frontend/app/     # Dashboard (overview, repos, PRs, analytics, settings, audit, onboarding)
samples/          # Intentional buggy repo for pipeline validation
litellm/          # Optional LiteLLM proxy config
```

---

## Local setup

### Prerequisites

- Docker & Docker Compose
- A GitHub App (for live PR reviews)
- A Gemini API key (or LiteLLM + provider keys)
- Optional: `cloudflared` or `ngrok` so GitHub can reach your local webhook

### 1. Clone and configure

```bash
git clone https://github.com/arjun988/spider.git
cd spider
cp .env.example .env
```

Set at least:

| Variable | Purpose |
|----------|---------|
| `SECRET_KEY` / `ENCRYPTION_KEY` | App secrets / Fernet key material |
| `GEMINI_API_KEY` | Direct Gemini (or configure later in Settings) |
| `GITHUB_APP_ID` | GitHub App ID |
| `GITHUB_APP_CLIENT_ID` / `GITHUB_APP_CLIENT_SECRET` | OAuth SSO + App |
| `GITHUB_APP_WEBHOOK_SECRET` | Webhook HMAC |
| `GITHUB_APP_NAME` | Install URL helper |
| `FRONTEND_URL` | OAuth callback base (`http://localhost:3000`) |

Place the GitHub App private key at:

```text
secrets/github-app.pem
```

### 2. Start the stack

```bash
docker compose up --build -d
```

| Service | URL |
|---------|-----|
| Dashboard | http://localhost:3000 |
| API docs | http://localhost:8000/docs |
| Health | http://localhost:8000/api/health |
| LiteLLM UI (optional) | http://localhost:4000/ui |

Apply DB migrations if needed:

```bash
docker compose exec backend alembic upgrade head
```

Optional sandbox image:

```bash
docker build -t spider-sandbox:latest -f backend/Dockerfile.sandbox backend
```

### 3. Expose webhooks locally

```bash
cloudflared tunnel --url http://localhost:8000
```

In the GitHub App settings, set the webhook URL to:

```text
https://<your-tunnel-host>/api/webhooks/github
```

> Quick tunnels get a **new URL** every restart — update the App webhook when that happens, or use a named tunnel for stability.

### 4. Configure the GitHub App

1. Permissions: **Contents** (read), **Pull requests** (read/write), **Checks** (read/write), **Metadata** (read)
2. Events: `pull_request`, `installation`, `installation_repositories`, `issue_comment`, `check_run` (as needed)
3. Install the app on your org/user
4. In the dashboard → **Repositories** → **Sync**, then **Re-index**
5. Optional: **Onboarding** page walks install → LLM → sync → index → first review

### 5. Configure the LLM

- Open **Settings** and choose **Gemini** (default) or **LiteLLM**
- Paste a key, set models, validate connection
- Adjust severity / confidence thresholds and monthly budget

### 6. Trigger a review

- Open or update a PR on a synced repo (auto-review), or
- Comment `/review` / `/review-again` on the PR, or
- Use the dashboard **Pull Requests** → Review / Re-review, or

```bash
curl -X POST "http://localhost:8000/api/pull-requests/<pr-uuid>/review"
```

### 7. Tests

```bash
docker compose exec backend pytest -q
```

Sample intentional bugs live in `samples/buggy_repo/` (SQL injection, hardcoded secret, path traversal, and more) — covered by `tests/test_e2e_buggy_repo.py`.

### Dev auth note

With `APP_ENV=development` and `AUTH_DISABLED_IN_DEV=true`, the API allows a local admin bypass so you can use the dashboard without OAuth. For real SSO, set GitHub OAuth client credentials, `FRONTEND_URL`, and sign in at `/login`.

---

## License

Private / internal use unless otherwise specified by the repository owner.
