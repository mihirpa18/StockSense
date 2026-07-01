-- Enable pgvector extension first
CREATE EXTENSION IF NOT EXISTS vector;

-- ─── USERS (managed by Supabase Auth, we extend it) ───────────────────────
-- Supabase creates auth.users automatically.
-- We create a public profile table that mirrors it.
CREATE TABLE public.profiles (
  id            UUID PRIMARY KEY REFERENCES auth.users(id) ON DELETE CASCADE,
  email         TEXT NOT NULL,
  full_name     TEXT,
  created_at    TIMESTAMPTZ DEFAULT NOW()
);

-- Auto-create profile when user signs up
CREATE OR REPLACE FUNCTION public.handle_new_user()
RETURNS TRIGGER AS $$
BEGIN
  INSERT INTO public.profiles (id, email, full_name)
  VALUES (NEW.id, NEW.email, NEW.raw_user_meta_data->>'full_name');
  RETURN NEW;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

CREATE TRIGGER on_auth_user_created
  AFTER INSERT ON auth.users
  FOR EACH ROW EXECUTE FUNCTION public.handle_new_user();

-- ─── COMPANIES (reference table — not user-specific) ──────────────────────
CREATE TABLE public.companies (
  id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  name          TEXT NOT NULL,               -- e.g. "Tata Motors Limited"
  ticker        TEXT NOT NULL,               -- e.g. "TATAMOTORS"
  exchange      TEXT DEFAULT 'NSE',          -- NSE or BSE
  sector        TEXT,                        -- e.g. "Automobiles"
  industry      TEXT,                        -- e.g. "Passenger Vehicles"
  description   TEXT,                        -- AI-generated or manual summary
  fundamentals_cache JSONB,                  -- cached yfinance data (ADDENDUM A.4)
  cache_updated_at   TIMESTAMPTZ,            -- when fundamentals_cache was last refreshed
  created_at    TIMESTAMPTZ DEFAULT NOW(),
  UNIQUE(ticker, exchange)
);

-- ─── WATCHLIST ────────────────────────────────────────────────────────────
CREATE TABLE public.watchlist (
  id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id       UUID NOT NULL REFERENCES public.profiles(id) ON DELETE CASCADE,
  company_id    UUID NOT NULL REFERENCES public.companies(id) ON DELETE CASCADE,
  added_at      TIMESTAMPTZ DEFAULT NOW(),
  UNIQUE(user_id, company_id)               -- prevent duplicate watchlist entries
);

-- ─── DOCUMENTS ────────────────────────────────────────────────────────────
CREATE TABLE public.documents (
  id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id       UUID NOT NULL REFERENCES public.profiles(id) ON DELETE CASCADE,
  company_id    UUID NOT NULL REFERENCES public.companies(id) ON DELETE CASCADE,
  filename      TEXT NOT NULL,               -- original uploaded filename
  file_size     INTEGER,                     -- in bytes
  page_count    INTEGER,                     -- total pages in PDF
  doc_type      TEXT DEFAULT 'annual_report',-- annual_report | quarterly_report | earnings_call | investor_deck
  fiscal_year   TEXT,                        -- e.g. "FY24" — user labels this on upload
  status        TEXT DEFAULT 'processing',   -- processing | ready | failed
  uploaded_at   TIMESTAMPTZ DEFAULT NOW()
);

-- ─── CHUNKS (this is the RAG vector store) ────────────────────────────────
CREATE TABLE public.chunks (
  id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  document_id   UUID NOT NULL REFERENCES public.documents(id) ON DELETE CASCADE,
  company_id    UUID NOT NULL REFERENCES public.companies(id),  -- denormalised for faster retrieval queries
  user_id       UUID NOT NULL REFERENCES public.profiles(id),   -- denormalised for RLS
  chunk_index   INTEGER NOT NULL,            -- position of this chunk in the document (0-based)
  page_number   INTEGER,                     -- which PDF page this chunk starts on
  content       TEXT NOT NULL,               -- the actual text of this chunk
  token_count   INTEGER,                     -- approximate token count of this chunk
  embedding     vector(1024),                -- Mistral mistral-embed produces 1024-dim vectors
  created_at    TIMESTAMPTZ DEFAULT NOW()
);

-- Create HNSW index for fast approximate nearest neighbour search
-- HNSW is better than IVFFlat for our scale (faster queries, no training needed)
CREATE INDEX ON public.chunks
  USING hnsw (embedding vector_cosine_ops)
  WITH (m = 16, ef_construction = 64);

-- Create GIN index for fast full-text keyword search (Hybrid Search)
CREATE INDEX ON public.chunks 
  USING gin (to_tsvector('english', content));

-- ─── RESEARCH NOTES ───────────────────────────────────────────────────────
CREATE TABLE public.notes (
  id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id       UUID NOT NULL REFERENCES public.profiles(id) ON DELETE CASCADE,
  company_id    UUID NOT NULL REFERENCES public.companies(id) ON DELETE CASCADE,
  content       TEXT NOT NULL,               -- freeform markdown text
  updated_at    TIMESTAMPTZ DEFAULT NOW(),
  created_at    TIMESTAMPTZ DEFAULT NOW()
);

-- ─── INVESTMENT THESES ────────────────────────────────────────────────────
CREATE TABLE public.theses (
  id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id          UUID NOT NULL REFERENCES public.profiles(id) ON DELETE CASCADE,
  company_id       UUID NOT NULL REFERENCES public.companies(id) ON DELETE CASCADE,
  source_document_id UUID REFERENCES public.documents(id) ON DELETE SET NULL,
                                             -- which document the thesis was based on
                                             -- used to prevent circular review (reviewing against the same doc)
  why_interested   TEXT NOT NULL,            -- free text: reason for interest
  key_risks        TEXT NOT NULL,            -- free text: identified risks
  expected_outcomes TEXT NOT NULL,           -- free text: measurable milestones
  confidence       INTEGER NOT NULL          -- 1 to 10
                   CHECK (confidence >= 1 AND confidence <= 10),
  horizon          TEXT NOT NULL             -- '6M' | '1Y' | '3Y' | '5Y'
                   CHECK (horizon IN ('6M', '1Y', '3Y', '5Y')),
  status           TEXT DEFAULT 'active'     -- active | archived
                   CHECK (status IN ('active', 'archived')),
  created_at       TIMESTAMPTZ DEFAULT NOW(),
  updated_at       TIMESTAMPTZ DEFAULT NOW(),
  UNIQUE(user_id, company_id)               -- one active thesis per company per user
);

-- ─── DECISION JOURNAL ─────────────────────────────────────────────────────
CREATE TABLE public.journal_entries (
  id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id          UUID NOT NULL REFERENCES public.profiles(id) ON DELETE CASCADE,
  company_id       UUID NOT NULL REFERENCES public.companies(id) ON DELETE CASCADE,
  stock_name       TEXT NOT NULL,            -- denormalised for quick display
  ticker           TEXT NOT NULL,            -- e.g. "TATAMOTORS"
  action           TEXT NOT NULL DEFAULT 'BUY'  -- 'BUY' | 'SELL' (future)
                   CHECK (action IN ('BUY', 'SELL')),
  price            NUMERIC(12, 2) NOT NULL,  -- entry price in INR
  quantity         INTEGER,                  -- number of shares (optional)
  purchase_date    DATE NOT NULL,
  reason           TEXT NOT NULL,            -- why I bought this
  risks_identified TEXT NOT NULL,            -- risks I saw at time of purchase
  confidence       INTEGER NOT NULL
                   CHECK (confidence >= 1 AND confidence <= 10),
  horizon          TEXT NOT NULL
                   CHECK (horizon IN ('6M', '1Y', '3Y', '5Y')),
  created_at       TIMESTAMPTZ DEFAULT NOW()
);

-- ─── THESIS REVIEW RESULTS ────────────────────────────────────────────────
CREATE TABLE public.thesis_reviews (
  id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id         UUID NOT NULL REFERENCES public.profiles(id) ON DELETE CASCADE,
  thesis_id       UUID NOT NULL REFERENCES public.theses(id) ON DELETE CASCADE,
  document_id     UUID NOT NULL REFERENCES public.documents(id), -- which doc was reviewed against
  review_result   JSONB NOT NULL,            -- structured JSON from AI (see format below)
  reviewed_at     TIMESTAMPTZ DEFAULT NOW()
);

-- review_result JSONB format:
-- {
--   "summary": "Overall thesis health summary string",
--   "assumptions": [
--     {
--       "assumption": "JLR margin recovery",
--       "status": "supported",          -- "supported" | "weakening" | "invalidated"
--       "evidence": "JLR EBIT margin reached 8.5% in Q4 FY24...",
--       "source_page": 61
--     }
--   ]
-- }

-- ─── CHAT HISTORY (optional but useful for UX) ────────────────────────────
CREATE TABLE public.chat_history (
  id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  session_id      UUID DEFAULT gen_random_uuid(), -- group messages into chat threads
  user_id         UUID NOT NULL REFERENCES public.profiles(id) ON DELETE CASCADE,
  company_id      UUID NOT NULL REFERENCES public.companies(id) ON DELETE CASCADE,
  role            TEXT NOT NULL CHECK (role IN ('user', 'assistant')),
  content         TEXT NOT NULL,
  citations       JSONB,                     -- [{chunk_id, page_number, snippet}]
  created_at      TIMESTAMPTZ DEFAULT NOW()
);

-- ─── ROW LEVEL SECURITY (CRITICAL — without this any user can read any data) ──
ALTER TABLE public.profiles        ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.watchlist       ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.documents       ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.chunks          ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.notes           ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.theses          ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.journal_entries ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.thesis_reviews  ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.chat_history    ENABLE ROW LEVEL SECURITY;

-- companies table is public (read-only for all authenticated users)
ALTER TABLE public.companies ENABLE ROW LEVEL SECURITY;
CREATE POLICY "Companies are viewable by all authenticated users"
  ON public.companies FOR SELECT
  TO authenticated USING (true);
CREATE POLICY "Only service role can insert companies"
  ON public.companies FOR INSERT
  TO service_role WITH CHECK (true);

-- Each user can only see their own data
CREATE POLICY "Users can manage own profile"
  ON public.profiles FOR ALL USING (auth.uid() = id);

CREATE POLICY "Users can manage own watchlist"
  ON public.watchlist FOR ALL USING (auth.uid() = user_id);

CREATE POLICY "Users can manage own documents"
  ON public.documents FOR ALL USING (auth.uid() = user_id);

CREATE POLICY "Users can manage own chunks"
  ON public.chunks FOR ALL USING (auth.uid() = user_id);

CREATE POLICY "Users can manage own notes"
  ON public.notes FOR ALL USING (auth.uid() = user_id);

CREATE POLICY "Users can manage own theses"
  ON public.theses FOR ALL USING (auth.uid() = user_id);

CREATE POLICY "Users can manage own journal entries"
  ON public.journal_entries FOR ALL USING (auth.uid() = user_id);

CREATE POLICY "Users can manage own thesis reviews"
  ON public.thesis_reviews FOR ALL USING (auth.uid() = user_id);

CREATE POLICY "Users can manage own chat history"
  ON public.chat_history FOR ALL USING (auth.uid() = user_id);

-- ─── HYBRID SEARCH FUNCTION (RRF — Reciprocal Rank Fusion) ───────────────
-- Called by backend/app/services/retriever.py via supabase.rpc("match_chunks", ...)
-- Combines pgvector cosine similarity (semantic) with GIN full-text (keyword) search
-- using Reciprocal Rank Fusion to get the best of both approaches.
-- Joins documents table to return document_name and fiscal_year for citation labeling.
CREATE OR REPLACE FUNCTION match_chunks(
  query_embedding    vector(1024),
  query_text         TEXT,
  company_id_filter  UUID,
  user_id_filter     UUID,
  match_count        INT DEFAULT 5,
  document_id_filter UUID DEFAULT NULL
)
RETURNS TABLE (
  id             UUID,
  document_id    UUID,
  content        TEXT,
  page_number    INT,
  chunk_index    INT,
  document_name  TEXT,
  fiscal_year    TEXT,
  similarity     FLOAT
)
LANGUAGE plpgsql STABLE AS $$
BEGIN
  RETURN QUERY
  WITH semantic_search AS (
    SELECT 
      c.id,
      ROW_NUMBER() OVER (ORDER BY c.embedding <=> query_embedding) as rank
    FROM public.chunks c
    WHERE c.company_id = company_id_filter
      AND c.user_id = user_id_filter
      AND (document_id_filter IS NULL OR c.document_id = document_id_filter)
    ORDER BY c.embedding <=> query_embedding
    LIMIT match_count * 2
  ),
  keyword_search AS (
    SELECT 
      c.id,
      ROW_NUMBER() OVER (ORDER BY ts_rank_cd(to_tsvector('english', c.content), plainto_tsquery('english', query_text)) DESC) as rank
    FROM public.chunks c
    WHERE c.company_id = company_id_filter
      AND c.user_id = user_id_filter
      AND (document_id_filter IS NULL OR c.document_id = document_id_filter)
      AND to_tsvector('english', c.content) @@ plainto_tsquery('english', query_text)
    ORDER BY ts_rank_cd(to_tsvector('english', c.content), plainto_tsquery('english', query_text)) DESC
    LIMIT match_count * 2
  )
  SELECT
    c.id,
    c.document_id,
    c.content,
    c.page_number,
    c.chunk_index,
    d.filename     AS document_name,
    d.fiscal_year,
    COALESCE(
      (1.0 / (60 + s.rank)) + (1.0 / (60 + k.rank)),
      (1.0 / (60 + s.rank)),
      (1.0 / (60 + k.rank))
    )::FLOAT AS similarity
  FROM public.chunks c
  JOIN public.documents d ON d.id = c.document_id
  LEFT JOIN semantic_search s ON c.id = s.id
  LEFT JOIN keyword_search k ON c.id = k.id
  WHERE s.id IS NOT NULL OR k.id IS NOT NULL
  ORDER BY similarity DESC
  LIMIT match_count;
END;
$$;
