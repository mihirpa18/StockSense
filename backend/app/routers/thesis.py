from fastapi import APIRouter, HTTPException, Depends
from app.models.schemas import ThesisCreate, ThesisResponse
from app.db.supabase import get_supabase
from app.dependencies import get_current_user_id
from typing import Optional

router = APIRouter()

@router.post("/", response_model=ThesisResponse)
async def save_thesis(thesis: ThesisCreate, user_id: str = Depends(get_current_user_id)):
    import datetime
    supabase = get_supabase()
    data = thesis.dict()
    data["user_id"] = user_id   # set server-side, never trusted from the client
    data["updated_at"] = datetime.datetime.now(datetime.timezone.utc).isoformat()
    # upsert: update if thesis already exists for this user+company
    result = supabase.table("theses").upsert(data, on_conflict="user_id,company_id").execute()
    if not result.data:
        raise HTTPException(status_code=500, detail="Failed to save thesis")
    return result.data[0]

@router.get("/{company_id}", response_model=ThesisResponse)
async def get_thesis(company_id: str, user_id: str = Depends(get_current_user_id)):
    supabase = get_supabase()
    result = supabase.table("theses")\
        .select("*")\
        .eq("user_id", user_id)\
        .eq("company_id", company_id)\
        .maybe_single()\
        .execute()
    if not result or getattr(result, "data", None) is None:
        raise HTTPException(status_code=404, detail="No thesis found")
    return result.data

@router.post("/{thesis_id}/review")
async def review_thesis(
    thesis_id: str,
    mode: str = "document",
    document_id: Optional[str] = None,
    search_query: Optional[str] = None,
    user_id: str = Depends(get_current_user_id)
):
    """
    Compares saved thesis against a specific uploaded document and/or web search.
    Runs the thesis review engine.
    """
    if mode not in ["document", "hybrid", "web"]:
        raise HTTPException(status_code=400, detail="Invalid review mode. Must be document, hybrid, or web.")

    if mode in ["document", "hybrid"] and not document_id:
        raise HTTPException(status_code=400, detail="document_id is required for document or hybrid review modes.")

    if mode in ["web", "hybrid"] and (not search_query or not search_query.strip()):
        raise HTTPException(status_code=400, detail="search_query is required for web or hybrid review modes.")

    from app.services.retriever import retrieve_relevant_chunks
    from app.services.llm import get_thesis_review
    from app.services.web_researcher import search_web

    supabase = get_supabase()

    # Fetch the thesis
    thesis_result = supabase.table("theses").select("*").eq("id", thesis_id).maybe_single().execute()
    if not thesis_result or getattr(thesis_result, "data", None) is None:
        raise HTTPException(status_code=404, detail="Thesis not found")
    thesis = thesis_result.data

    # GUARD 0: Ownership check — the thesis must belong to the caller.
    if thesis["user_id"] != user_id:
        raise HTTPException(status_code=404, detail="Thesis not found")

    doc = None
    if document_id:
        # Fetch document info for company_id (and confirm it belongs to the caller too)
        doc_result = supabase.table("documents").select("*").eq("id", document_id).maybe_single().execute()
        if not doc_result or getattr(doc_result, "data", None) is None:
            raise HTTPException(status_code=404, detail="Document not found")
        doc = doc_result.data
        if doc["user_id"] != user_id:
            raise HTTPException(status_code=404, detail="Document not found")

        # GUARD 1: Prevent circular review — can't review against the source document
        if thesis.get("source_document_id") == document_id:
            raise HTTPException(
                status_code=400,
                detail="Cannot review a thesis against the same document it was based on. "
                       "Upload a newer report to review your thesis."
            )

        # GUARD 2: Prevent stale review — document must be newer than thesis
        from datetime import datetime
        thesis_date = datetime.fromisoformat(thesis["created_at"].replace("Z", "+00:00"))
        doc_date = datetime.fromisoformat(doc["uploaded_at"].replace("Z", "+00:00"))
        if doc_date < thesis_date:
            raise HTTPException(
                status_code=400,
                detail="This document was uploaded before the thesis was created. "
                       "Review requires a newer report to check if assumptions still hold."
            )

    chunks = []
    if mode in ["document", "hybrid"]:
        # Pull representative chunks from the SELECTED document ONLY
        review_query = f"{thesis['why_interested']} {thesis['expected_outcomes']}"
        chunks = retrieve_relevant_chunks(
            review_query,
            doc["company_id"],
            user_id,
            document_id=document_id       # ← scoped to this document only
        )

        if not chunks and mode == "document":
            raise HTTPException(
                status_code=400,
                detail="No processable content found in this document. "
                       "Make sure the document has been fully processed (status = ready)."
            )

    web_results = []
    if mode in ["web", "hybrid"]:
        web_results = search_web(search_query, max_results=5)

    # Get AI review
    review_result = get_thesis_review(thesis, chunks, web_results)

    # Save review result (skip for web-only mode)
    if mode != "web":
        supabase.table("thesis_reviews").insert({
            "user_id":       user_id,
            "thesis_id":     thesis_id,
            "document_id":   document_id,
            "review_result": review_result
        }).execute()

    return review_result

@router.post("/{company_id}/auto-draft")
async def auto_draft_thesis(
    company_id: str,
    document_id: str,
    user_id: str = Depends(get_current_user_id)
):
    """
    Auto-fills / drafts a thesis (why_interested, key_risks, expected_outcomes)
    based on a specific document (chunks) and best-effort web search.
    """
    supabase = get_supabase()
    
    # 1. Fetch company details
    comp_result = supabase.table("companies").select("name, ticker").eq("id", company_id).maybe_single().execute()
    if not comp_result or getattr(comp_result, "data", None) is None:
        raise HTTPException(status_code=404, detail="Company not found")
    company = comp_result.data
    name = company["name"]
    ticker = company["ticker"]
    
    # 2. Fetch document -> guard: exists, belongs to caller, company_id matches, status == ready
    doc_result = supabase.table("documents").select("*").eq("id", document_id).maybe_single().execute()
    if not doc_result or getattr(doc_result, "data", None) is None:
        raise HTTPException(status_code=404, detail="Document not found")
    doc = doc_result.data
    if doc["user_id"] != user_id:
        raise HTTPException(status_code=404, detail="Document not found")
    if doc["company_id"] != company_id:
        raise HTTPException(status_code=400, detail="Document does not match this company")
    if doc["status"] != "ready":
        raise HTTPException(status_code=400, detail="Document is not ready for research. Please wait until processing is complete.")
        
    # 3. Retrieve chunks scoped to THAT document_id — 3 targeted queries, merged + deduped:
    from app.services.retriever import retrieve_relevant_chunks
    
    queries = [
        "business model competitive advantages growth drivers market position",
        "key risks challenges threats headwinds regulatory",
        "financial performance revenue profit margin outlook future guidance"
    ]
    
    all_chunks = []
    seen_chunk_ids = set()
    
    for q in queries:
        chunks = retrieve_relevant_chunks(
            question=q,
            company_id=company_id,
            user_id=user_id,
            document_id=document_id
        )
        for chunk in chunks:
            if chunk["id"] not in seen_chunk_ids:
                seen_chunk_ids.add(chunk["id"])
                all_chunks.append(chunk)
                
    # 4. Web search (best-effort)
    from app.services.web_researcher import search_web
    web_results = []
    try:
        search_query = f"{name} {ticker} stock analysis growth risks outlook"
        web_results = search_web(search_query, max_results=5)
    except Exception as e:
        # best effort, ignore search failure
        print(f"Auto-draft web search ignored error: {e}")
        
    # 5. LLM draft -> returns {why_interested, key_risks, expected_outcomes}
    from app.services.llm import generate_thesis_draft
    draft = generate_thesis_draft(all_chunks, web_results, name, ticker)
    
    return draft

