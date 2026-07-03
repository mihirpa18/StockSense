import asyncio
from fastapi import APIRouter, HTTPException, Depends
from app.services.retriever import retrieve_relevant_chunks
from app.services.llm import get_rag_answer
from app.db.supabase import get_supabase
from app.dependencies import get_current_user_id
from app.models.schemas import ChatRequest, ChatResponse, Citation
import uuid
from langsmith import traceable

router = APIRouter()

@router.post("/", response_model=ChatResponse)
@traceable(name="RAG Chat Pipeline", run_type="chain")
async def chat(request: ChatRequest, user_id: str = Depends(get_current_user_id)):
    if not request.question.strip():
        raise HTTPException(status_code=400, detail="Question cannot be empty")

    supabase = get_supabase()

    # Generate (or reuse) the session_id FIRST. Every return path below must
    # include it — ChatResponse.session_id has no default, so a return that
    # omits it raises a Pydantic validation error, not a clean response.
    session_id = request.session_id
    if session_id:
        existing = supabase.table("chat_history").select("company_id").eq("session_id", session_id).limit(1).execute()
        if existing.data and existing.data[0]["company_id"] != request.company_id:
            # Session exists but belongs to a different company (due to frontend state leak).
            # Generate a new session_id to prevent database thread corruption.
            session_id = str(uuid.uuid4())
    else:
        session_id = str(uuid.uuid4())

    # Step 1: Retrieve relevant chunks via cosine similarity
    # If document_id is provided, scope search to that document only.
    # This prevents cross-document contamination when multiple reports are uploaded.
    chunks = await asyncio.to_thread(
        retrieve_relevant_chunks,
        question=request.question,
        company_id=request.company_id,
        user_id=user_id,
        document_id=request.document_id
    )

    if not chunks:
        # BUG FIX: this early return previously omitted session_id, which
        # ChatResponse requires — that raised a validation error on the very
        # first message a new user sends to a company with no documents yet.
        return ChatResponse(
            answer="No documents have been uploaded for this company yet. Please upload an annual report or earnings call transcript first.",
            citations=[],
            session_id=session_id
        )

    # Step 2: Get AI answer from Mistral using retrieved chunks and sliding window history
    answer = await asyncio.to_thread(get_rag_answer, request.question, chunks, request.conversation_history)

    # Step 3: Build citation objects from retrieved chunks
    citations = [
        Citation(
            chunk_id=str(chunk["id"]),
            page_number=chunk.get("page_number", 0),
            snippet=chunk["content"][:150] + "...",
            document_name=chunk.get("document_name", "Doc")
        )
        for chunk in chunks
    ]

    # Step 4: Save to chat history
    supabase.table("chat_history").insert([
        {
            "session_id": session_id,
            "user_id":    user_id,
            "company_id": request.company_id,
            "role":       "user",
            "content":    request.question,
            "citations":  None
        },
        {
            "session_id": session_id,
            "user_id":    user_id,
            "company_id": request.company_id,
            "role":       "assistant",
            "content":    answer,
            "citations":  [c.dict() for c in citations]
        }
    ]).execute()

    # We return the session_id so the frontend can append it to future requests in this thread
    return ChatResponse(answer=answer, citations=citations, session_id=session_id)

@router.get("/{company_id}/sessions")
async def get_chat_sessions(company_id: str, user_id: str = Depends(get_current_user_id)):
    """
    Get a list of all chat sessions (threads) for the AUTHENTICATED user and
    a company, ordered by the most recently updated.
    """
    supabase = get_supabase()
    result = supabase.table("chat_history")\
        .select("session_id, content, created_at")\
        .eq("user_id", user_id)\
        .eq("company_id", company_id)\
        .eq("role", "user")\
        .order("created_at", desc=True)\
        .execute()
    
    if not result.data:
        return []
        
    # Group by session_id to return unique sessions with their first question as title
    sessions = []
    seen = set()
    for row in result.data:
        sid = row["session_id"]
        if sid not in seen:
            seen.add(sid)
            sessions.append({
                "session_id": sid,
                "title": row["content"][:50] + "..." if len(row["content"]) > 50 else row["content"],
                "last_active": row["created_at"]
            })
            
    return sessions

@router.get("/session/{session_id}")
async def get_chat_history(session_id: str, user_id: str = Depends(get_current_user_id)):
    """
    Get all messages for a specific chat session thread.

    The .eq("user_id", user_id) filter ensures the session must belong to the
    caller, preventing IDOR (Insecure Direct Object Reference) attacks.
    """
    supabase = get_supabase()
    result = supabase.table("chat_history")\
        .select("*")\
        .eq("session_id", session_id)\
        .eq("user_id", user_id)\
        .order("created_at")\
        .execute()

    if not result.data:
        raise HTTPException(status_code=404, detail="Session not found")

    return result.data
