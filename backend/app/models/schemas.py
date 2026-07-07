from pydantic import BaseModel, UUID4, Field
from typing import Optional, List, Literal
from datetime import datetime, date
from enum import Enum

class DocType(str, Enum):
    annual_report  = "annual_report"
    quarterly_report = "quarterly_report"
    earnings_call  = "earnings_call"
    investor_deck  = "investor_deck"

class Horizon(str, Enum):
    six_months = "6M"
    one_year   = "1Y"
    three_years = "3Y"
    five_years = "5Y"

class UploadResponse(BaseModel):
    document_id: str
    filename: str
    page_count: int
    chunk_count: int
    status: str

# NOTE: user_id is intentionally ABSENT from every *Create/*Request model below.
# It used to be a plain client-supplied field, which meant any caller could
# write any user_id and read/write someone else's data (the backend uses the
# Supabase SERVICE ROLE key, which bypasses RLS, so nothing else was checking).
# user_id is now derived server-side from the verified JWT via
# Depends(get_current_user_id) in each router (see TASK 2.6) and is never
# accepted as request input.

class ChatRequest(BaseModel):
    company_id: str
    question: str
    session_id: Optional[str] = None         # ID of the current chat thread
    document_id: Optional[str] = None        # if set, scope retrieval to this document only
    conversation_history: Optional[List[dict]] = []  # [{role, content}]

class Citation(BaseModel):
    chunk_id: str
    page_number: int
    snippet: str           # first 150 chars of the chunk
    document_name: Optional[str] = "Doc"

class ChatResponse(BaseModel):
    answer: str
    citations: List[Citation]
    session_id: str                          # Return session_id so frontend can track it
    # IMPORTANT: session_id has no default, so EVERY return path in chat.py
    # (including the "no documents uploaded yet" early-exit) must supply one.
    # Forgetting this on an early return raises a Pydantic validation error,
    # not a clean 4xx — see the warning in TASK 2.14.

class ThesisCreate(BaseModel):
    company_id: str
    source_document_id: Optional[str] = None  # which document this thesis is based on
    why_interested: str
    key_risks: str
    expected_outcomes: str
    confidence: int         # 1-10
    horizon: Horizon

class ThesisResponse(ThesisCreate):
    id: str
    user_id: str            # included in the response for transparency, but
                             # never accepted as input on ThesisCreate
    created_at: datetime
    updated_at: datetime

class JournalCreate(BaseModel):
    company_id: str
    stock_name: str
    ticker: str
    action: str = "BUY"
    price: float
    quantity: Optional[int] = None
    purchase_date: date
    reason: str
    risks_identified: str
    confidence: int
    horizon: Horizon

class JournalResponse(JournalCreate):
    id: str
    user_id: str
    created_at: datetime

class CompanyCreate(BaseModel):
    name: str
    ticker: str
    exchange: str = "NSE"
    sector: Optional[str] = None
    industry: Optional[str] = None
    description: Optional[str] = None

class AssumptionReview(BaseModel):
    assumption: str = Field(description="Brief label of the thesis assumption being evaluated")
    status: Literal["supported", "weakening", "invalidated"] = Field(
        description="'supported' if evidence confirms the assumption, 'weakening' if evidence is "
                    "partial/contradictory, 'invalidated' if evidence clearly contradicts it"
    )
    evidence: str = Field(description="Specific evidence from context, with page reference or web source title")
    source_page: Optional[int] = Field(default=None, description="Page number, or null if from web search")

class ReviewResult(BaseModel):
    """Structured output schema for LLM thesis-review calls (used with LangChain's with_structured_output)."""
    summary: str = Field(description="2-3 sentence overall thesis health assessment")
    assumptions: List[AssumptionReview]

class ThesisDraft(BaseModel):
    """Structured output schema for LLM auto-draft calls (used with LangChain's with_structured_output)."""
    why_interested: str = Field(
        description="Concise, bulleted points on why a retail investor should be interested: "
                     "competitive advantages, growth drivers, market position"
    )
    key_risks: str = Field(description="Concise, bulleted points on key risks, headwinds, and threats")
    expected_outcomes: str = Field(
        description="Concise, bulleted list of realistic milestones/indicators to track whether the thesis is playing out"
    )

class NoteCreate(BaseModel):
    company_id: str
    content: str
    id: Optional[str] = None  # If provided, updates this note. Otherwise creates a new one.

class NoteResponse(BaseModel):
    id: str
    company_id: str
    user_id: str
    content: str
    created_at: datetime
    updated_at: datetime
