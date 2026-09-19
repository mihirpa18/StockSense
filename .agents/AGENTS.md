# StockSense — Agent Rules & Project Context

## Project Overview

StockSense is a **full-stack investment research platform** for Indian retail investors. It lets users upload company annual reports (PDFs), chat with them using RAG (Retrieval-Augmented Generation), build and review investment theses, maintain a decision journal, write research notes, and track a watchlist with live market data.

**Target market:** Indian stock market (NSE/BSE). Currency is INR. Company tickers follow NSE conventions (e.g., `TATAMOTORS`, `RELIANCE`).

---

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│  Frontend (React + Vite + Tailwind)                     │
│  Port: 5173                                             │
│  src/pages: Auth, Dashboard, Company, Watchlist,        │
│             Journal, ThesisReview                        │
│  src/lib/api.js — Axios client with JWT interceptor     │
│  src/lib/supabase.js — Supabase anon client             │
└───────────────────┬─────────────────┬───────────────────┘
                    │ REST (JWT)      │ Direct (anon key)
                    ▼                 ▼
┌──────────────────────┐    ┌────────────────────┐
│  FastAPI Backend     │    │  Supabase          │
│  Port: 8000          │    │  (Auth + Postgres  │
│  Prefix: /api/*      │    │   + pgvector +     │
│  Auth: JWT via       │    │   Storage)         │
│  Depends()           │    │  RLS on all tables │
│  DB: service_role    │    └────────────────────┘
│  key (bypasses RLS)  │              ▲
└──────────┬───────────┘              │
           │ HTTP (localhost:3000)     │ Storage/DB
           ▼                          │
┌──────────────────────┐    ┌─────────┴──────────┐
│  NSE Market Service  │    │  Arq Worker        │
│  (Node.js/Express)   │    │  (Background PDF   │
│  stock-nse-india lib │    │   processing via   │
│  Port: 3000          │    │   Redis queue)     │
└──────────────────────┘    └────────────────────┘
```

### Processes to Run

1. **Frontend:** `cd frontend && npm run dev` → port 5173
2. **Backend API:** `cd backend && uvicorn app.main:app --reload` → port 8000
3. **Market Service:** `cd backend/market-service && node index.js` → port 3000
4. **Background Worker:** `cd backend && arq app.worker.WorkerSettings` → processes PDF uploads asynchronously via Redis

---

## Tech Stack

### Backend (`backend/`)
| Layer | Technology |
|-------|-----------|
| Framework | FastAPI 0.111 + Uvicorn |
| Language | Python 3.x |
| Database | Supabase (Postgres + pgvector + Storage) |
| Embeddings | Mistral `mistral-embed` (1024-dim vectors via `langchain_mistralai`) |
| LLM | Google Gemini `gemini-2.5-flash` (via `langchain_google_genai`) |
| Observability | LangSmith tracing (`@traceable`) |
| Job Queue & Caching | Redis (Upstash) + `arq` background worker |
| Rate Limiting | Redis-backed token bucket with Lua scripts |
| PDF parsing | PyMuPDF (`fitz`) |
| Tokenization | `tiktoken` (cl100k_base) |
| Market & Fundamental Data | `market_data_serp` (SerpApi Google Finance) + custom Node.js NSE service + `yfinance` |
| Web search | `duckduckgo-search` (no API key) |
| Auth | JWT verification via `python-jose` (ES256 + HS256) |
| Config | `pydantic-settings` (`.env` file) |

### Frontend (`frontend/`)
| Layer | Technology |
|-------|-----------|
| Framework | React 18 + Vite 5 |
| Routing | react-router-dom v6 |
| Styling | Tailwind CSS 3 |
| HTTP | Axios (with JWT interceptor) |
| Auth | Supabase Auth (@supabase/supabase-js) |
| Icons | lucide-react |
| Toasts | react-hot-toast |
| 3D background | Three.js |

### Database (Supabase/Postgres)
- **pgvector** extension for vector storage (`vector(1024)`)
- **HNSW index** on embeddings (cosine similarity)
- **GIN index** for full-text search
- **RLS** on all user-data tables
- **Storage**: `raw-uploads` private bucket for PDF uploads
- **Hybrid search** via `match_chunks` RPC (RRF algorithm)

---

## Directory Structure

```
stocksense/
├── backend/
│   ├── app/
│   │   ├── main.py              # FastAPI app, CORS, middleware, arq pool lifespan, routers
│   │   ├── worker.py            # arq background worker (PDF download → parse → chunk → embed → store)
│   │   ├── config.py            # pydantic-settings (env vars: Supabase, Gemini, Mistral, SerpApi, Redis, LangSmith)
│   │   ├── dependencies.py      # JWT auth: get_current_user_id (ES256/HS256)
│   │   ├── db/
│   │   │   ├── supabase.py      # Supabase client factory (service_role key)
│   │   │   └── redis_client.py  # Sync Redis client singleton
│   │   ├── models/
│   │   │   └── schemas.py       # Pydantic request/response models
│   │   ├── routers/
│   │   │   ├── chat.py          # POST /api/chat/, GET sessions/history
│   │   │   ├── companies.py     # CRUD, search, watchlist, fundamentals, auto-research
│   │   │   ├── thesis.py        # Save, get, review thesis, draft thesis
│   │   │   ├── journal.py       # Create/list journal entries
│   │   │   ├── notes.py         # Save/list research notes
│   │   │   └── upload.py        # PDF upload → store raw PDF → enqueue arq worker job
│   │   ├── services/
│   │   │   ├── llm.py           # Gemini 2.5 Flash RAG answer + thesis review + thesis draft
│   │   │   ├── retriever.py     # Hybrid search via match_chunks RPC
│   │   │   ├── embedder.py      # Mistral embeddings (1024-dim, rate-limited)
│   │   │   ├── chunker.py       # Sliding window chunker (500 tokens, 50 overlap)
│   │   │   ├── pdf_parser.py    # PyMuPDF text extraction
│   │   │   ├── storage.py       # Supabase Storage helper (raw-uploads bucket)
│   │   │   ├── rate_limiter.py  # Redis token bucket rate limiter
│   │   │   ├── market_data.py   # yfinance + NSE node service
│   │   │   ├── market_data_serp.py # SerpApi Google Finance fundamentals, ratios & news
│   │   │   ├── web_researcher.py # DuckDuckGo search, PDF download, SSRF protection
│   │   │   └── auto_research_agent.py # Sequential agent: search → download → RAG ingest
│   │   └── utils/
│   │       └── logger.py        # Rotating file logger (stocksense.log)
│   ├── market-service/
│   │   ├── index.js             # Express server proxying NSE API
│   │   └── package.json         # stock-nse-india dependency
│   ├── requirements.txt
│   └── .env.example
├── frontend/
│   ├── src/
│   │   ├── App.jsx              # Router + ProtectedRoute + AppShell
│   │   ├── main.jsx             # React DOM entry
│   │   ├── index.css            # Global styles
│   │   ├── hooks/useAuth.js     # Supabase auth hook
│   │   ├── lib/
│   │   │   ├── api.js           # Axios client with JWT interceptor
│   │   │   └── supabase.js      # Supabase anon client
│   │   ├── pages/
│   │   │   ├── Auth.jsx         # Login/signup page
│   │   │   ├── Dashboard.jsx    # Home dashboard
│   │   │   ├── Company.jsx      # Company detail (chart, fundamentals, chat, thesis, notes, docs)
│   │   │   ├── Watchlist.jsx    # User's watchlist with prices
│   │   │   ├── Journal.jsx      # Decision journal entries
│   │   │   └── ThesisReview.jsx # Thesis review against new documents
│   │   └── components/
│   │       ├── layout/          # Sidebar.jsx, Topbar.jsx
│   │       ├── chat/            # ChatPanel.jsx, ChatMessage.jsx, ChatInput.jsx
│   │       ├── thesis/          # ThesisForm.jsx, ConfidenceGauge.jsx
│   │       ├── ui/              # LiquidBackground.jsx, Markdown.jsx
│   │       └── TradingViewWidget.jsx
│   ├── package.json
│   ├── vite.config.js
│   └── tailwind.config.js
├── supabase/
│   ├── schema.sql               # Full DB schema, RLS policies, match_chunks RPC
│   └── nifty50_seed.sql         # 50 Nifty companies seed data
└── reference.md                 # Technical glossary of concepts used
```

---

## Environment Variables

### Backend (`backend/.env`)
| Variable | Purpose |
|----------|---------|
| `SUPABASE_URL` | Supabase project URL |
| `SUPABASE_SERVICE_KEY` | Service role key (bypasses RLS) — **never expose to frontend** |
| `SUPABASE_JWT_SECRET` | Used to verify HS256 JWTs |
| `GEMINI_API_KEY` | Google Gemini API key (used for `gemini-2.5-flash` LLM) |
| `MISTRAL_API_KEY` | Mistral AI API key (`mistral-embed` embeddings) |
| `SERPAPI_KEY` | SerpApi key for Google Finance fundamentals, stats, & news |
| `REDIS_URL` | Upstash Redis connection URL (rate limiter, caching, arq worker) |
| `LANGSMITH_TRACING` | Set `"true"` to enable LangSmith tracing |
| `LANGSMITH_API_KEY` | LangSmith API key |
| `LANGSMITH_PROJECT` | LangSmith project name (default: `stocksense`) |
| `FRONTEND_URL` | CORS origin (default: `http://localhost:5173`) |

### Frontend (`frontend/.env`)
| Variable | Purpose |
|----------|---------|
| `VITE_SUPABASE_URL` | Supabase project URL |
| `VITE_SUPABASE_ANON_KEY` | Anon key (safe for client, RLS enforces access) |
| `VITE_API_URL` | Backend URL (default: `http://localhost:8000`) |

---

## Critical Security Patterns

### Authentication Flow
1. Frontend signs in via **Supabase Auth** → receives JWT (access_token)
2. `api.js` interceptor attaches `Authorization: Bearer <token>` to every backend request
3. Backend's `get_current_user_id` dependency verifies JWT (supports both ES256 and HS256) and extracts `user_id` from the `sub` claim
4. `user_id` is **never accepted from client input** — always derived from the verified JWT
5. Every router filters queries by `user_id` to enforce data isolation

### Two-Layer Data Protection
- **RLS layer**: Protects direct frontend → Supabase queries (e.g., Dashboard thesis count)
- **JWT + explicit filter layer**: Protects backend-mediated requests (backend uses service key which bypasses RLS, so `user_id` filtering in routers is critical)

### SSRF Protection
- `web_researcher.py` validates URLs before downloading PDFs
- Blocks private IPs, loopback, link-local addresses
- Enforces HTTP/HTTPS only, validates PDF magic bytes

---

## RAG Pipeline (Core Feature)

```
Upload PDF → Store raw PDF in Supabase Storage ("raw-uploads")
           → Enqueue arq background job → PyMuPDF extract → Sliding window chunk (500 tokens, 50 overlap)
           → Mistral embed (1024-dim, rate-limited) → Store in chunks table (pgvector) → Delete raw PDF

User asks question → Embed question → match_chunks RPC (Hybrid Search: 
                     cosine similarity + GIN full-text → RRF fusion)
                   → Top 5 chunks → Gemini 2.5 Flash LLM generates answer with citations
```

### Key Design Decisions
- **Embedding model**: Mistral `mistral-embed` (1024 dimensions via `langchain_mistralai`)
- **LLM**: Google Gemini `gemini-2.5-flash` (via `langchain_google_genai`)
- **Background Processing**: Asynchronous via `arq` worker process and Redis
- **Rate Limiting**: Redis token bucket algorithm with atomic Lua scripts
- **Chunk size**: 500 tokens with 50-token overlap
- **Top-K**: 5 chunks retrieved per query
- **Hybrid search**: Reciprocal Rank Fusion (RRF, k=60) combining semantic + keyword search
- **Tokenizer**: tiktoken `cl100k_base`

---

## Database Tables

| Table | Purpose | Key Columns |
|-------|---------|-------------|
| `profiles` | User profiles (mirrors auth.users) | `id` (UUID), `email`, `full_name` |
| `companies` | Company reference data (not user-specific) | `ticker`, `exchange`, `fundamentals_cache` (JSONB) |
| `watchlist` | User's tracked companies | `user_id`, `company_id` (unique pair) |
| `documents` | Uploaded PDFs metadata | `status` (processing/ready/failed), `doc_type`, `fiscal_year` |
| `chunks` | RAG vector store | `content`, `embedding` (vector(1024)), `page_number` |
| `notes` | Freeform research notes | `content` (markdown), `company_id`, `user_id` |
| `theses` | Investment theses | `why_interested`, `key_risks`, `confidence` (1-10), `horizon` |
| `journal_entries` | Buy/sell decision journal | `price`, `quantity`, `reason`, `risks_identified` |
| `thesis_reviews` | AI review results | `review_result` (JSONB with assumptions + statuses) |
| `chat_history` | Chat threads | `session_id`, `role`, `content`, `citations` |

---

## Coding Conventions

### Backend
- **Router pattern**: Each router file defines an `APIRouter()`, included in `main.py` with a `/api/<name>` prefix
- **Auth**: Every mutable endpoint uses `user_id: str = Depends(get_current_user_id)`
- **DB access**: Always via `get_supabase()` factory (returns service-role client)
- **Error handling**: Use `HTTPException` with appropriate status codes
- **Logging**: Use `from app.utils.logger import logger` — never bare `print()` in production paths

### Frontend
- **API calls**: Always via functions in `src/lib/api.js` — never raw Axios/fetch
- **Auth state**: Via `useAuth()` hook
- **Protected routes**: Wrapped in `<ProtectedRoute>` component
- **Styling**: Tailwind CSS with CSS custom properties for theme (dark mode default)
- **Toasts**: `react-hot-toast` for user notifications

### General
- **No user_id in request bodies**: Always derived server-side from JWT
- **Document scoping**: When working with a specific document, always pass `document_id` to prevent cross-document contamination
- **Thesis review guards**: Prevent circular review (same source doc), stale review (old doc), and IDOR attacks

---

## Common Tasks

### Adding a New API Endpoint
1. Add Pydantic models to `backend/app/models/schemas.py`
2. Create or extend a router in `backend/app/routers/`
3. Use `Depends(get_current_user_id)` for authenticated endpoints
4. Register the router in `main.py` if it's a new file
5. Add the API call function to `frontend/src/lib/api.js`

### Adding a New Page
1. Create component in `frontend/src/pages/`
2. Add route in `App.jsx` wrapped in `<ProtectedRoute>`
3. Add nav link in `Sidebar.jsx`

### Modifying the Database Schema
1. Edit `supabase/schema.sql`
2. Run the migration in Supabase SQL editor
3. Add RLS policies for new tables
4. Update relevant Pydantic models and routers

---

## Important Caveats

- The backend uses **Supabase service_role key** which **bypasses all RLS**. Data isolation relies entirely on explicit `user_id` filters in each router.
- Document uploads run asynchronously through `arq` (`app/worker.py`). `upload_document` returns status `"processing"` immediately; clients poll or wait until status flips to `"ready"`.
- The `fundamentals_cache` in the companies table caches SerpApi/yfinance data to avoid rate limiting.
- The NSE market service (`market-service/`) must be running on port 3000 for live price data.
- Upstash Redis is required for the `arq` job queue and token-bucket rate limiting (`rate_limiter.py`).
- DuckDuckGo search uses `backend="lite"` to avoid JS/VQD rate limiting.
- The auto-research agent is a **sequential pipeline**, not a graph-based agent — no LangGraph.
