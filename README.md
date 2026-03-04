# Reckoner

A fast, single-page dashboard for monitoring your cloud AI service credits and balances across OpenRouter, OpenAI, Anthropic, xAI (Grok), Mistral, Groq, Manus, Warp, and more.

## Features

- **Single dashboard** — all your AI provider balances at a glance
- **Auto-refresh** — balances update every 60 seconds in the browser, with background polling every 5–30 minutes
- **Live refresh** — force an immediate refresh of any provider or all at once
- **In-app settings** — configure credentials directly from the dashboard UI
- **Railway-ready** — deploys as a single service with `uv` and Nixpacks
- **Docker support** — multi-stage Dockerfile included

## Provider Support

| Provider | Method | Auth Required | Notes |
|----------|--------|---------------|-------|
| **OpenRouter** | Official API | API Key | Full balance + usage data |
| **OpenAI** | Admin API | Admin Key | 30-day spend (no balance endpoint) |
| **Anthropic** | Undocumented console API | Session Cookie + Org ID | Prepaid credit balance |
| **xAI (Grok)** | Official Management API | Management Key + Team ID | Prepaid credit balance |
| **Mistral AI** | Session scraping | Session Cookie | Best-effort |
| **Groq** | Session scraping | Session Cookie | Best-effort |
| **Manus** | Session scraping | Session Cookie / API Key | Best-effort |
| **Warp** | Session scraping | Session Cookie | Best-effort |

## Quick Start

### Local Development

**Prerequisites:** Python 3.11+, Node.js 22+, pnpm, uv

```bash
# Clone the repo
git clone https://github.com/CaptainASIC/reckoner
cd reckoner

# Backend
cd backend
uv sync
cp ../.env.example ../.env
# Edit .env with your credentials
uv run uvicorn main:app --reload --port 8000

# Frontend (separate terminal)
cd frontend
pnpm install
pnpm dev
```

Open http://localhost:5173 for the dashboard.

### Deploy to Railway

1. Push this repo to GitHub
2. Create a new Railway project → **Deploy from GitHub repo**
3. Railway will auto-detect `railway.toml` and build with Nixpacks
4. Add environment variables in Railway's **Variables** tab (see `.env.example`)
5. Done — Railway provides a public URL

### Deploy with Docker

```bash
docker build -t reckoner .
docker run -p 8000:8000 --env-file .env reckoner
```

## Configuration

### Environment Variables

Copy `.env.example` to `.env` and fill in your credentials. All variables are optional — only configure the services you use.

### In-App Settings

Click the ⚙️ icon on any provider card to configure credentials directly in the dashboard. Settings are persisted in the local SQLite database.

## Getting Credentials

### OpenRouter
1. Go to [openrouter.ai/settings/keys](https://openrouter.ai/settings/keys)
2. Create an API key
3. Set `OPENROUTER_API_KEY`

### OpenAI
1. Go to [platform.openai.com/settings/organization/admin-keys](https://platform.openai.com/settings/organization/admin-keys)
2. Create an Admin key (`sk-admin-...`)
3. Set `OPENAI_ADMIN_KEY`
> Note: OpenAI has no direct balance endpoint. The dashboard shows your 30-day spend.

### Anthropic
1. Log in to [platform.claude.com](https://platform.claude.com)
2. Open DevTools (F12) → Network tab
3. Find a request to `/api/organizations/<org-id>/prepaid/credits`
4. Copy the `org_id` from the URL
5. Copy the `sessionKey` value from the Cookie header
6. Set `ANTHROPIC_ORG_ID` and `ANTHROPIC_SESSION_COOKIE`

### xAI (Grok)
1. Log in to [console.x.ai](https://console.x.ai)
2. Go to Settings → Management Keys → Create a key
3. Find your Team ID in the console URL or account settings
4. Set `XAI_MANAGEMENT_KEY` and `XAI_TEAM_ID`

### Tier 2 Providers (Mistral, Groq, Manus, Warp)
1. Log in to the respective console
2. Open DevTools (F12) → Application → Cookies (or Network → Headers)
3. Copy the full cookie string
4. Set the corresponding `*_SESSION_COOKIE` variable

## Architecture

```
reckoner/
├── backend/                  # FastAPI application
│   ├── main.py               # App entry point, serves frontend
│   ├── scheduler.py          # Background balance refresh
│   ├── config_manager.py     # Settings persistence
│   ├── models/
│   │   ├── database.py       # SQLite schema + connection
│   │   └── schemas.py        # Pydantic v2 models
│   ├── providers/            # One file per AI service
│   │   ├── base.py           # Abstract base class
│   │   ├── openrouter.py
│   │   ├── openai.py
│   │   ├── anthropic.py
│   │   ├── xai.py
│   │   ├── mistral.py
│   │   ├── groq.py
│   │   ├── manus.py
│   │   └── warp.py
│   └── routers/
│       ├── credits.py        # Balance endpoints
│       ├── settings.py       # Config endpoints
│       └── health.py         # Health check
├── frontend/                 # React + TypeScript + Tailwind
│   └── src/
│       ├── App.tsx
│       ├── components/
│       │   ├── ProviderCard.tsx
│       │   ├── SettingsModal.tsx
│       │   └── SummaryBar.tsx
│       ├── hooks/
│       │   ├── useDashboard.ts
│       │   └── useSettings.ts
│       ├── types/index.ts
│       └── utils/
│           ├── api.ts
│           └── format.ts
├── railway.toml              # Railway deployment config
├── nixpacks.toml             # Nixpacks build config
├── Dockerfile                # Docker deployment
└── .env.example              # Environment variable template
```

## API Reference

| Endpoint | Method | Description |
|----------|--------|-------------|
| `GET /api/health` | GET | Health check |
| `GET /api/credits/` | GET | Full dashboard (cached) |
| `POST /api/credits/refresh` | POST | Refresh all providers |
| `POST /api/credits/refresh/{id}` | POST | Refresh single provider |
| `GET /api/credits/providers` | GET | List providers with metadata |
| `GET /api/settings/providers` | GET | Get settings (masked) |
| `PUT /api/settings/providers/{id}` | PUT | Update provider credentials |

Interactive docs available at `/docs` (FastAPI Swagger UI).

## Adding a New Provider

1. Create `backend/providers/yourprovider.py` extending `BaseProvider`
2. Implement `fetch_balance()` and `is_configured()`
3. Register in `backend/providers/__init__.py`
4. That's it — the dashboard picks it up automatically

## License

MIT
