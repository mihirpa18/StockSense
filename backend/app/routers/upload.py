import asyncio
from fastapi import APIRouter, UploadFile, File, Form, HTTPException, Depends
from app.services.pdf_parser import extract_text_by_page
from app.services.chunker import chunk_page_texts
from app.services.embedder import get_embedding, get_embeddings_batch
from app.db.supabase import get_supabase
from app.dependencies import get_current_user_id
from app.models.schemas import UploadResponse, DocType
import uuid

router = APIRouter()

@router.post("/", response_model=UploadResponse)
async def upload_document(
    file: UploadFile = File(...),
    company_id: str = Form(...),
    doc_type: str = Form(default="annual_report"),
    fiscal_year: str = Form(default="FY24"),
    user_id: str = Depends(get_current_user_id)   # ← derived from verified JWT, not a Form field
):
    # Validate file type
    if not file.filename.endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are accepted")

    # Read file bytes
    pdf_bytes = await file.read()

    # Guard against very large files (50MB limit)
    if len(pdf_bytes) > 50 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="File too large. Maximum 50MB.")

    supabase = get_supabase()

    # Check if PDF already exists
    existing_docs = supabase.table("documents").select("id").eq("company_id", company_id).eq("user_id", user_id).eq("filename", file.filename).execute()
    if existing_docs and getattr(existing_docs, "data", None):
        raise HTTPException(status_code=400, detail="PDF already exists for this company.")

    # Step 1: Create document record (status = processing)
    doc_id = str(uuid.uuid4())
    supabase.table("documents").insert({
        "id":          doc_id,
        "user_id":     user_id,
        "company_id":  company_id,
        "filename":    file.filename,
        "file_size":   len(pdf_bytes),
        "doc_type":    doc_type,
        "fiscal_year": fiscal_year,
        "status":      "processing"
    }).execute()

    try:
        # Step 2: Parse PDF into pages (CPU-bound; runs in a thread so it doesn't block
        # other requests being served by this worker while a large PDF is parsed)
        pages = await asyncio.to_thread(extract_text_by_page, pdf_bytes)

        # Step 3: Chunk the pages (also CPU-bound — tokenization over the whole document)
        chunks = await asyncio.to_thread(chunk_page_texts, pages)

        # Step 4: Embed each chunk and store
        # Batch into groups of 100 to avoid Mistral RPM limits
        chunk_rows = []
        batch_size = 100
        for i in range(0, len(chunks), batch_size):
            batch_chunks = chunks[i:i + batch_size]
            batch_texts = [c["content"] for c in batch_chunks]

            # Get embeddings for the whole batch in one API call.
            # get_embeddings_batch is a blocking network call — run it in a thread so it
            # doesn't stall the event loop (and therefore every other in-flight request)
            # for however long the Mistral call takes.
            embeddings = await asyncio.to_thread(get_embeddings_batch, batch_texts)
            
            for chunk, embedding in zip(batch_chunks, embeddings):
                chunk_rows.append({
                    "document_id": doc_id,
                    "company_id":  company_id,
                    "user_id":     user_id,
                    "chunk_index": chunk["chunk_index"],
                    "page_number": chunk["page_number"],
                    "content":     chunk["content"],
                    "token_count": chunk["token_count"],
                    "embedding":   embedding
                })
            
            # Sleep 2 seconds between batches to avoid Tokens-Per-Minute (TPM) limits
            if i + batch_size < len(chunks):
                await asyncio.sleep(2)
        # Batch insert in groups of 50 to avoid payload limits
        batch_size = 50
        for i in range(0, len(chunk_rows), batch_size):
            batch = chunk_rows[i:i + batch_size]
            supabase.table("chunks").insert(batch).execute()

        # Step 5: Update document status and page count
        supabase.table("documents").update({
            "status":     "ready",
            "page_count": len(pages)
        }).eq("id", doc_id).execute()

        return UploadResponse(
            document_id=doc_id,
            filename=file.filename,
            page_count=len(pages),
            chunk_count=len(chunks),
            status="ready"
        )

    except Exception as e:
        # Mark document as failed
        supabase.table("documents").update({"status": "failed"}).eq("id", doc_id).execute()
        raise HTTPException(status_code=500, detail=f"Processing failed: {str(e)}")
