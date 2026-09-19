# 📈 StockSense

> **Full-Stack AI Investment Research & Document Intelligence Platform for Indian Equity Markets**

[![FastAPI](https://img.shields.io/badge/FastAPI-0.111.0-009688?style=flat-square&logo=fastapi)](https://fastapi.tiangolo.com/)
[![React](https://img.shields.io/badge/React-18.3-61DAFB?style=flat-square&logo=react)](https://reactjs.org/)
[![Vite](https://img.shields.io/badge/Vite-5.2-646CFF?style=flat-square&logo=vite)](https://vitejs.dev/)
[![Supabase](https://img.shields.io/badge/Supabase-Postgres_%2B_pgvector-3ECF8E?style=flat-square&logo=supabase)](https://supabase.com/)
[![Gemini](https://img.shields.io/badge/Google_Gemini-2.5_Flash-4285F4?style=flat-square&logo=google)](https://ai.google.dev/)
[![Mistral AI](https://img.shields.io/badge/Mistral_AI-mistral--embed-FF7000?style=flat-square)](https://mistral.ai/)
[![Redis](https://img.shields.io/badge/Redis-Upstash_RateLimiter_%2B_arq-DC382D?style=flat-square&logo=redis)](https://upstash.com/)
[![LangSmith](https://img.shields.io/badge/LangSmith-Tracing_%26_Observability-000000?style=flat-square)](https://smith.langchain.com/)
[![Tailwind CSS](https://img.shields.io/badge/Tailwind_CSS-3.4-38BDF8?style=flat-square&logo=tailwindcss)](https://tailwindcss.com/)

---

## 🌟 Overview

**StockSense** is an end-to-end investment research platform engineered for retail investors navigating the Indian stock market (NSE / BSE). It integrates **Retrieval-Augmented Generation (RAG)**, asynchronous background PDF processing, SerpApi Google Finance fundamentals, autonomous web research, structured thesis evaluation, decision journaling, and real-time market data into a single modern dashboard.

Retail investors face massive information overload from hundred-page annual reports, quarterly filings, and earnings transcripts. StockSense transforms dense financial documentation into an interactive, cited conversational experience while offering quantitative and qualitative tools to ground investment decisions in empirical data.

---

## 🚀 Key Features

- 📄 **RAG-Powered Document Intelligence**: Upload company annual reports or investor presentations. Ask natural language questions and receive precise, cited answers linked directly to document source pages.
- ⚡ **Asynchronous Background Processing**: PDF uploads hand off heavy parsing, sliding-window chunking, and vector embedding to a Redis-backed `arq` worker, preventing HTTP server blocking and request timeouts.
- 🤖 **Autonomous Auto-Research Pipeline**: Trigger web search and document discovery to automatically discover investor presentations, download PDFs safely, parse, chunk, embed, and ingest them into vector storage.
- 💡 **Investment Thesis Builder & AI Reviewer**: Formulate structured investment hypotheses with confidence scores (1–10) and time horizons. Auto-draft initial theses from ingested docs or run automated AI evaluations comparing assumptions against fresh document/web evidence.
- 📝 **Freeform Research Notes**: Maintain dedicated, markdown-supported research notes per company to organize takeaways, management commentary, and qualitative notes.
- 📓 **Institutional Decision Journal**: Keep an immutable log of BUY/SELL decisions detailing execution prices, quantities, investment logic, and identified risks to mitigate behavioral cognitive biases.
- 📊 **Real-Time Market & Financial Fundamentals**: Track stocks with live NSE market prices (via a dedicated Node.js microservice) alongside cached financial statements, ratios (P/E, ROE, Debt/Equity, Profit Margin), and recent news via SerpApi Google Finance.
- 🔐 **Enterprise-Grade Security & Isolation**: Features Supabase Auth JWT verification (supporting ES256/HS256 algorithms), server-side derived user scoping (preventing IDOR), and strict SSRF safeguards on web research downloads.

---

## 🏗️ System Architecture

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                           React 18 + Vite 5 Frontend                            │
│                           (Port 5173 / AppShell UI)                             │
└───────────────────────┬─────────────────────────────────┬───────────────────────┘
                        │ REST (Bearer JWT)               │ Direct (Anon Key)
                        ▼                                 ▼
┌──────────────────────────────────────────┐   ┌──────────────────────────────────┐
│              FastAPI Backend             │   │          Supabase Cloud          │
│           (Python 3.x, Port 8000)        │   │ (Auth + Postgres + pgvector      │
│ - JWT Auth Verification (ES256/HS256)    │   │  + Storage "raw-uploads")        │
│ - LangSmith Tracing & Observability      │   │ RLS Enabled on All Tables        │
│ - Token-Bucket Rate Limiter (Redis Lua) │   └────────────────▲─────────────────┘
└──────┬─────────────┬─────────────┬───────┘                    │
       │             │             │ Enqueue Job                │ Storage/DB
       │ HTTP        │ HTTP        ▼                            │
       │        ┌────┴───┐ ┌───────────────┐                    │
       │        │SerpApi │ │ Upstash Redis │                    │
       │        └────────┘ │ (arq Queue)   │                    │
       ▼                   └───────┬───────┘                    │
┌──────────────┐                   ▼                            │
│ NSE Service  │         ┌───────────────────┐                  │
│ (Node.js/3000)         │    Arq Worker     ├──────────────────┘
└──────────────┘         │ (Async Ingestion) │
                         └───────────────────┘
```

### RAG Pipeline & Ingestion Flow

```
PDF Upload ──► Save Raw PDF to Supabase Storage ("raw-uploads")
                   │
                   ▼ (Async arq Worker)
PyMuPDF Text Extraction ──► Sliding Window Chunking (500 tokens / 50 overlap)
                                      │
                                      ▼
Supabase pgvector ◄── HNSW Index ◄── Mistral mistral-embed (1024-dim, Rate-Limited)
       │
       ▼
User Question ──► Hybrid Search (Reciprocal Rank Fusion / RRF: Cosine + GIN Full-Text)
                        │
                        ▼
Top-5 Chunks + History ──► Gemini 2.5 Flash LLM ──► Cited Answer (Page Numbers)
```

---

## 🛠️ Tech Stack

### Frontend
- **Framework**: React 18 + Vite 5
- **Routing**: React Router DOM v6
- **Styling**: Tailwind CSS 3 with dark mode custom design tokens & glassmorphism
- **Graphics**: Three.js (Liquid background animation)
- **HTTP Client**: Axios with JWT authorization interceptor
- **Icons & UI**: Lucide React, React Hot Toast

### Backend
- **Framework**: FastAPI 0.111 + Uvicorn
- **Language**: Python 3.x
- **Job Queue & Caching**: Upstash Redis + `arq` background worker
- **Rate Limiting**: Redis-backed token bucket algorithm with atomic Lua scripts
- **Observability**: LangSmith tracing (`@traceable`)
- **PDF Extraction**: PyMuPDF (`fitz`)
- **Tokenization**: `tiktoken` (`cl100k_base`)
- **AI Models & Frameworks**:
  - **LLM**: Google Gemini 2.5 Flash (`gemini-2.5-flash` via `langchain_google_genai`) with structured output (`with_structured_output`)
  - **Embeddings**: Mistral AI (`mistral-embed` for 1024-dim vectors via `langchain_mistralai`)
- **Web Search**: `duckduckgo-search` (lite backend with SSRF protection)
- **Auth**: `python-jose` (ES256 JWKS public key & HS256 secret verification)

### Market & Fundamentals Services
- **NSE Market Microservice**: Express (Node.js) server proxying `stock-nse-india` API (Port 3000)
- **Financial Fundamentals**: SerpApi Google Finance engine (price, stats, company info, ratios, quarterly/annual series, news) with `yfinance` fallback

### Database & Vector Store
- **Database**: Supabase PostgreSQL with `pgvector` extension
- **Indexes**:
  - `HNSW` index on `chunks.embedding` using `vector_cosine_ops`
  - `GIN` index on `chunks.content` using PostgreSQL full-text search (`to_tsvector`)
  - `RLS` policies on user tables + explicit server-side user filtering
- **Search Method**: Hybrid Search using Reciprocal Rank Fusion (`match_chunks` RPC)

---

## 📂 Directory Structure

```
stocksense/
├── backend/
│   ├── app/
│   │   ├── main.py                   # FastAPI application lifecycle, middleware & router setup
│   │   ├── worker.py                 # Arq background worker (PDF download → parse → chunk → embed → store)
│   │   ├── config.py                 # Pydantic-settings configuration (Supabase, Gemini, Mistral, Redis)
│   │   ├── dependencies.py           # JWT Authentication & user verification
│   │   ├── db/
│   │   │   ├── supabase.py           # Supabase client factory (service-role key)
│   │   │   └── redis_client.py       # Sync Redis client singleton
│   │   ├── models/
│   │   │   └── schemas.py            # Pydantic request, response & structured output schemas
│   │   ├── routers/
│   │   │   ├── chat.py               # RAG chat & session history endpoints
│   │   │   ├── companies.py          # Watchlist, search, fundamentals, price refresh, auto-research
│   │   │   ├── thesis.py             # Thesis CRUD, AI thesis drafting & assumption review
│   │   │   ├── journal.py            # Investment decision journal endpoints
│   │   │   ├── notes.py              # Freeform research notes management
│   │   │   └── upload.py             # Document upload validation & arq worker queueing
│   │   ├── services/
│   │   │   ├── llm.py                # Gemini 2.5 Flash RAG answer, thesis review & draft generation
│   │   │   ├── retriever.py          # Hybrid RRF search wrapper calling match_chunks RPC
│   │   │   ├── embedder.py           # Mistral embeddings service (1024 dimensions, rate-limited)
│   │   │   ├── chunker.py            # Sliding window text chunker (500 tokens, 50 overlap)
│   │   │   ├── pdf_parser.py         # PyMuPDF text extraction pipeline
│   │   │   ├── storage.py            # Supabase Storage helper (raw-uploads bucket)
│   │   │   ├── rate_limiter.py       # Redis token bucket rate limiter (Lua script)
│   │   │   ├── market_data.py        # yfinance integration & NSE proxy client
│   │   │   ├── market_data_serp.py   # SerpApi Google Finance fundamentals, stats & news
│   │   │   ├── web_researcher.py     # DuckDuckGo search & SSRF-safe PDF downloader
│   │   │   └── auto_research_agent.py# Sequential research agent pipeline
│   │   └── utils/
│   │       └── logger.py             # Rotating file logger
│   ├── market-service/
│   │   ├── index.js                  # Express proxy for NSE real-time data (Port 3000)
│   │   └── package.json
│   ├── requirements.txt
│   └── .env.example
├── frontend/
│   ├── src/
│   │   ├── App.jsx                   # Layout routing & protected route wrappers
│   │   ├── main.jsx                  # React DOM entrypoint
│   │   ├── hooks/useAuth.js          # Supabase auth context & state hook
│   │   ├── lib/
│   │   │   ├── api.js                # Axios client with JWT interceptor
│   │   │   └── supabase.js           # Public Supabase client instance
│   │   ├── pages/
│   │   │   ├── Auth.jsx              # Login / Sign up page
│   │   │   ├── Dashboard.jsx         # User overview & market summary
│   │   │   ├── Company.jsx           # Company research hub (charts, chat, thesis, notes, docs)
│   │   │   ├── Watchlist.jsx         # Real-time stock watchlist
│   │   │   ├── Journal.jsx           # Investment decision journal
│   │   │   └── ThesisReview.jsx      # Thesis review & comparative analysis UI
│   │   └── components/
│   │       ├── layout/               # Sidebar & Topbar navigation
│   │       ├── chat/                 # RAG Chat interface components
│   │       ├── thesis/               # Thesis form & confidence score gauge
│   │       └── ui/                   # Liquid background & markdown renderers
│   ├── package.json
│   ├── vite.config.js
│   └── tailwind.config.js
└── supabase/
    ├── schema.sql                    # Database schema, HNSW/GIN indexes, RPC functions & RLS
    └── nifty50_seed.sql              # Pre-seeded Nifty 50 companies data
```

---

## ⚡ Getting Started

### Prerequisites

Ensure you have the following installed on your machine:
- **Node.js**: v18.x or higher
- **Python**: v3.10 or higher
- **Redis Instance**: Upstash Redis URL
- **Supabase Account**: A hosted Supabase project with `vector` extension enabled
- **API Keys**:
  - Google Gemini API Key (`GEMINI_API_KEY`)
  - Mistral AI API Key (`MISTRAL_API_KEY`)
  - SerpApi Key (`SERPAPI_KEY`)

---

### Step 1: Database Setup (Supabase)

1. Log into your **Supabase Dashboard** and open the **SQL Editor**.
2. Run [`supabase/schema.sql`](file:///home/mihir_p_a/Documents/project/stocksense/supabase/schema.sql) to enable the `vector` extension, create database tables, set up RLS policies, and create the `match_chunks` RPC hybrid search function.
3. Create a private bucket named `raw-uploads` in Supabase Storage.
4. (Optional) Run [`supabase/nifty50_seed.sql`](file:///home/mihir_p_a/Documents/project/stocksense/supabase/nifty50_seed.sql) to pre-seed Indian companies into the `companies` table.

---

### Step 2: Configure Environment Variables

#### Backend Configuration (`backend/.env`)

```ini
SUPABASE_URL=https://your-project-id.supabase.co
SUPABASE_SERVICE_KEY=your-supabase-service-role-key
SUPABASE_JWT_SECRET=your-supabase-jwt-secret
GEMINI_API_KEY=your-gemini-api-key
MISTRAL_API_KEY=your-mistral-api-key
SERPAPI_KEY=your-serpapi-key
REDIS_URL=rediss://default:your-password@your-redis-host:6379
LANGSMITH_TRACING=true
LANGSMITH_API_KEY=your-langsmith-api-key
LANGSMITH_PROJECT=stocksense
FRONTEND_URL=http://localhost:5173
```

#### Frontend Configuration (`frontend/.env`)

```ini
VITE_SUPABASE_URL=https://your-project-id.supabase.co
VITE_SUPABASE_ANON_KEY=your-supabase-anon-key
VITE_API_URL=http://localhost:8000
```

---

### Step 3: Run the Application Services

StockSense consists of **four processes**:

#### 1. NSE Market Microservice (Port 3000)
```bash
cd backend/market-service
npm install
node index.js
```

#### 2. Background PDF Ingestion Worker (arq)
```bash
cd backend
source .venv/bin/activate
arq app.worker.WorkerSettings
```

#### 3. FastAPI Backend Server (Port 8000)
```bash
cd backend
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

#### 4. React Frontend Application (Port 5173)
```bash
cd frontend
npm install
npm run dev
```

Navigate to **`http://localhost:5173`** in your browser.

---

## 📡 API Endpoint Overview

| Method | Endpoint | Description | Auth Required |
| :--- | :--- | :--- | :---: |
| `GET` | `/health` | Health check status | ❌ |
| `POST` | `/api/upload/` | Upload PDF file & queue background worker ingestion | ✅ |
| `POST` | `/api/chat/` | Query RAG pipeline & generate cited response | ✅ |
| `GET` | `/api/chat/{company_id}/sessions` | List active chat threads for a company | ✅ |
| `GET` | `/api/chat/session/{session_id}` | Retrieve chat message history for a session | ✅ |
| `POST` | `/api/thesis/` | Create or update an investment thesis | ✅ |
| `GET` | `/api/thesis/{company_id}` | Retrieve investment thesis for a company | ✅ |
| `POST` | `/api/thesis/{company_id}/draft` | Auto-draft thesis from docs & web search | ✅ |
| `POST` | `/api/thesis/{thesis_id}/review` | Trigger AI review of thesis against document/web | ✅ |
| `GET` | `/api/notes/{company_id}` | Fetch user's research notes for a company | ✅ |
| `POST` | `/api/notes/` | Save or update a research note | ✅ |
| `POST` | `/api/journal/` | Add a new investment decision log entry | ✅ |
| `GET` | `/api/journal/` | Fetch list of decision journal entries | ✅ |
| `GET` | `/api/companies/search` | Search companies by ticker or name | ❌ |
| `GET` | `/api/companies/watchlist` | Get current user's tracked watchlist | ✅ |
| `POST` | `/api/companies/watchlist/{id}` | Add company to user watchlist | ✅ |
| `DELETE` | `/api/companies/watchlist/{id}` | Remove company from user watchlist | ✅ |
| `POST` | `/api/companies/{id}/auto-research` | Launch autonomous web research agent | ✅ |

---

## 🔒 Engineering Highlights & Security Best Practices

- **Asynchronous Task Processing**: High-latency PDF parsing and vector embedding are decoupled from the FastAPI HTTP thread pool using an `arq` Redis queue.
- **Strict JWT Verification**: User context is derived exclusively from Supabase Auth tokens passed in the `Authorization` header. `user_id` is never accepted as input in request payloads, eliminating IDOR vulnerabilities.
- **Distributed Rate Limiting**: Outbound API rates for LLMs and embedding generators are governed by a Redis-backed token bucket algorithm with Lua script atomicity.
- **SSRF Safeguards**: Web research agent enforces URL validation (`is_safe_url()`), blocking loopback IP addresses, private subnets, non-HTTP/HTTPS schemes, and validating magic bytes.
- **Hybrid Search Optimization**: Blends vector similarity (pgvector HNSW) and keyword search (PostgreSQL GIN) via Reciprocal Rank Fusion (RRF) for optimal financial document retrieval.

---


