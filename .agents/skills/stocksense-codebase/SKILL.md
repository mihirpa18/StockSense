---
name: stocksense-codebase
description: >
  Deep context about the StockSense investment research platform — its architecture,
  RAG pipeline, database schema, API endpoints, auth flow, and service interactions.
  Activate when working on any feature, bugfix, or refactor in the StockSense codebase.
---

# StockSense Codebase Context Skill

This skill provides deep context for working with the StockSense codebase. Read this
before making any changes to understand how the pieces fit together.

---

## What StockSense Does

StockSense helps Indian retail investors research stocks. A user can:

1. **Search & add companies** from a pre-seeded Nifty 50 list (or create new ones)
2. **Upload annual reports** (PDF) which get parsed, chunked, embedded, and stored as vectors
3. **Chat with documents** via RAG — ask questions, get answers with page citations
4. **Build investment theses** — structured notes with confidence scores and time horizons
5. **Review theses** against newer documents — AI compares assumptions to fresh evidence
6. **Maintain a decision journal** — log buy/sell decisions with rationale
7. **Track a watchlist** with live NSE/BSE price data and key fundamentals

---

## Service Architecture

### Three Services (must all be running for full functionality)

| Service | Directory | Command | Port |
|---------|-----------|---------|------|
| React Frontend | `frontend/` | `npm run dev` | 5173 |
| FastAPI Backend | `backend/` | `uvicorn app.main:app --reload` | 8000 |
| NSE Market Service | `backend/market-service/` | `node index.js` | 3000 |

Plus **Supabase** as the hosted database + auth provider (cloud, not local).

### Data Flow Patterns

```
Frontend ──Bearer JWT──▶ Backend ──service_role──▶ Supabase (Postgres + pgvector)
Frontend ──anon key────▶ Supabase (direct queries, protected by RLS)
Backend ──HTTP──▶ NSE Market Service (port 3000) ──▶ NSE India API
Backend ──HTTP──▶ yfinance (Yahoo Finance)
Backend ──HTTP──▶ DuckDuckGo (web search, no API key)
Backend ──HTTP──▶ Mistral API (embeddings + LLM)
```

---

## Backend Deep Dive

### Module Dependency Graph

```
main.py
  ├── config.py (Settings from .env via pydantic-settings)
  ├── dependencies.py (JWT verification → get_current_user_id)
  └── routers/
        ├── upload.py   → services/{pdf_parser, chunker, embedder}
        ├── chat.py     → services/{retriever, llm}
        ├── thesis.py   → services/{retriever, llm}
        ├── journal.py  → (direct Supabase CRUD)
        └── companies.py → services/{market_data, auto_research_agent}
                             auto_research_agent → {web_researcher, pdf_parser,
                                                     chunker, embedder, llm}
```

### API Routes

| Method | Route | Router | Auth | Purpose |
|--------|-------|--------|------|---------|
| POST | `/api/upload/` | upload.py | ✅ | Upload PDF → parse → chunk → embed → store |
| POST | `/api/chat/` | chat.py | ✅ | Send question, get RAG answer with citations |
| GET | `/api/chat/{company_id}/sessions` | chat.py | ✅ | List chat threads |
| GET | `/api/chat/session/{session_id}` | chat.py | ✅ | Get messages in a thread |
| POST | `/api/thesis/` | thesis.py | ✅ | Save/upsert investment thesis |
| GET | `/api/thesis/{company_id}` | thesis.py | ✅ | Get thesis for a company |
| POST | `/api/thesis/{thesis_id}/review` | thesis.py | ✅ | Review thesis against a document |
| POST | `/api/journal/` | journal.py | ✅ | Create journal entry |
| GET | `/api/journal/` | journal.py | ✅ | List all journal entries |
| GET | `/api/companies/search?q=` | companies.py | ❌ | Search companies by name/ticker |
| POST | `/api/companies/` | companies.py | ❌ | Create new company record |
| GET | `/api/companies/{id}` | companies.py | ❌ | Get company by ID |
| GET | `/api/companies/{id}/fundamentals` | companies.py | ❌ | Get fundamentals (cached 72h) |
| POST | `/api/companies/{id}/refresh-price` | companies.py | ❌ | Lightweight NSE price refresh |
| POST | `/api/companies/{id}/refresh-fundamentals` | companies.py | ❌ | Force yfinance refresh |
| GET | `/api/companies/watchlist` | companies.py | ✅ | Get user's watchlist |
| POST | `/api/companies/watchlist/{id}` | companies.py | ✅ | Add to watchlist |
| DELETE | `/api/companies/watchlist/{id}` | companies.py | ✅ | Remove from watchlist |
| POST | `/api/companies/refresh-prices` | companies.py | ✅ | Bulk price refresh |
| POST | `/api/companies/{id}/auto-research` | companies.py | ✅ | Trigger auto-research agent |

**Route ordering matters** in `companies.py`: `/search`, `/watchlist`, and `/refresh-prices` must be registered before `/{company_id}` to avoid being swallowed by the dynamic route.

### Services Layer

#### RAG Pipeline Services

| Service | File | Responsibility |
|---------|------|---------------|
| `pdf_parser.py` | PyMuPDF extraction | PDF bytes → list of `{page_number, text}` |
| `chunker.py` | Sliding window | Pages → chunks (500 tokens, 50 overlap, tiktoken) |
| `embedder.py` | Mistral embeddings | Text → 1024-dim vector (batch + single) |
| `retriever.py` | Hybrid search | Question → `match_chunks` RPC → top-5 chunks |
| `llm.py` | Mistral LLM | Chunks + question → answer with citations |

#### Other Services

| Service | File | Responsibility |
|---------|------|---------------|
| `market_data.py` | Price + fundamentals | NSE microservice + yfinance (with 429 retry) |
| `web_researcher.py` | Web tools | DuckDuckGo search, PDF download (SSRF-safe), news fetch |
| `auto_research_agent.py` | Research agent | Sequential: news → find PDFs → download → RAG ingest |

### Auth & Security

- **JWT verification** in `dependencies.py`: Supports both ES256 (JWKS from Supabase) and HS256 (fallback via JWT secret)
- **JWKS caching**: Fetched once from Supabase, cached in-memory
- **Hardcoded fallback JWK**: For when Supabase JWKS endpoint is unavailable
- **No user_id in request bodies**: All schemas intentionally omit `user_id` as input — it's injected server-side from verified JWT
- **IDOR prevention**: Thesis review checks `thesis.user_id == caller_user_id`
- **SSRF protection**: `is_safe_url()` validates URLs before download

---

## Frontend Deep Dive

### Page Map

| Route | Page Component | Purpose |
|-------|---------------|---------|
| `/auth` | Auth.jsx | Login/signup (unprotected) |
| `/` | Dashboard.jsx | Home dashboard |
| `/company/:id` | Company.jsx | Full company view (16KB — the largest page) |
| `/watchlist` | Watchlist.jsx | Watchlist with live prices |
| `/journal` | Journal.jsx | Decision journal |
| `/review` | ThesisReview.jsx | Thesis review UI |

### Component Hierarchy

```
App.jsx
├── AuthPage (public)
└── ProtectedRoute → AppShell
    ├── LiquidBackground (Three.js animated background)
    ├── Sidebar (nav links)
    ├── Topbar (search, user menu)
    └── <Page>
        ├── Company.jsx
        │   ├── TradingViewWidget
        │   ├── ChatPanel → ChatMessage + ChatInput
        │   └── ThesisForm + ConfidenceGauge
        └── (other pages)
```

### Key Frontend Patterns

- **JWT injection**: `api.js` interceptor auto-attaches Supabase session token to every request
- **Axios timeout**: 120 seconds (needed for auto-research + large uploads)
- **State management**: Local React state + hooks (no Redux/Zustand)
- **Dark theme**: CSS custom properties (`--panel`, `--text`, `--border`)

---

## Database Schema

### Tables (all have RLS enabled)

| Table | User-scoped? | Key constraint |
|-------|-------------|----------------|
| `profiles` | Yes (id = auth.uid) | PK references auth.users |
| `companies` | No (shared) | UNIQUE(ticker, exchange) |
| `watchlist` | Yes | UNIQUE(user_id, company_id) |
| `documents` | Yes | status: processing/ready/failed |
| `chunks` | Yes | embedding: vector(1024), HNSW + GIN indexes |
| `notes` | Yes | UNIQUE(user_id, company_id) |
| `theses` | Yes | UNIQUE(user_id, company_id), confidence 1-10 |
| `journal_entries` | Yes | action: BUY/SELL |
| `thesis_reviews` | Yes | review_result: JSONB |
| `chat_history` | Yes | session_id groups threads |

### Key Database Function

**`match_chunks`** — The hybrid search RPC:
- Takes: query_embedding, query_text, company_id, user_id, match_count, optional document_id
- Returns: chunks with document_name, fiscal_year, similarity score
- Algorithm: RRF (Reciprocal Rank Fusion, k=60) combining:
  - Semantic search: pgvector cosine distance (`<=>` operator)
  - Keyword search: GIN index + `ts_rank_cd` + `plainto_tsquery`

### Trigger

`handle_new_user()` — Fires on `auth.users` INSERT, copies user to `public.profiles`.

---

## Common Pitfalls & Gotchas

1. **ChatResponse requires session_id**: Every return path in `chat.py` must include `session_id` — it has no default. Missing it causes a Pydantic validation error, not a clean 4xx.

2. **Document scoping**: When `document_id` is None, retriever searches ALL documents for that company. Always pass `document_id` when reviewing a thesis or when the user selects a specific document.

3. **Route ordering in companies.py**: Literal routes (`/search`, `/watchlist`) must come before `/{company_id}` or FastAPI will match them as dynamic params.

4. **Thesis review guards**: Three guards prevent misleading reviews:
   - Can't review against the source document (circular logic)
   - Document must be newer than thesis (stale data)
   - Thesis must belong to the caller (IDOR protection)

5. **yfinance rate limiting**: Returns sparse data on 429. Code checks `len(info) > 5` and retries with exponential backoff.

6. **Embedding dimension mismatch**: The schema uses `vector(1024)` for Mistral. If switching embedding models, update `schema.sql`, the HNSW index, and the `match_chunks` function signature.

7. **Service role key bypasses RLS**: The backend DB client bypasses all RLS policies. Data isolation depends entirely on explicit `user_id` filters in router code.

8. **Config in separate file**: `config.py` exists separately to break circular imports (main → routers → services → settings → main).
