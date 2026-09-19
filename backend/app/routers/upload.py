from fastapi import APIRouter, UploadFile, File, Form, HTTPException, Depends, Request
import fitz  # PyMuPDF
from app.db.supabase import get_supabase
from app.services.storage import upload_raw_pdf
from app.dependencies import get_current_user_id
from app.models.schemas import UploadResponse
from app.utils.logger import logger
import uuid
import asyncio

router = APIRouter()

MAX_UPLOAD_SIZE = 50 * 1024 * 1024  # 50MB


@router.post("/", response_model=UploadResponse)
async def upload_document(
    request: Request,
    file: UploadFile = File(...),
    company_id: str = Form(...),
    doc_type: str = Form(default="annual_report"),
    fiscal_year: str = Form(default="FY24"),
    user_id: str = Depends(get_current_user_id)   # ← derived from verified JWT, not a Form field
):
    if not file.filename.endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are accepted")

    # Stream the read with a running size check, instead of buffering the
    # whole file into memory first and rejecting after the fact — several
    # large concurrent uploads could otherwise exhaust memory before any
    # of them get checked.
    content = bytearray()
    while chunk := await file.read(1024 * 1024):
        content.extend(chunk)
        if len(content) > MAX_UPLOAD_SIZE:
            raise HTTPException(status_code=400, detail="File too large. Maximum 50MB.")
    pdf_bytes = bytes(content)

    # Magic-byte check — same pattern already used in web_researcher.py's
    # download_pdf_from_url for auto-downloaded PDFs, now applied here too.
    if len(pdf_bytes) < 4 or pdf_bytes[:4] != b"%PDF":
        raise HTTPException(status_code=400, detail="File is not a valid PDF.")

    # Belt-and-suspenders beyond the magic bytes: actually try opening it.
    # Catches files that pass the 4-byte check but are truncated/corrupted
    # (e.g. an interrupted upload) before they ever reach the background
    # worker and waste an embedding batch on garbage.
    try:
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        doc.close()
    except Exception:
        raise HTTPException(status_code=400, detail="File could not be opened as a valid PDF.")

    supabase = get_supabase()

    existing_docs = (
        supabase.table("documents")
        .select("id")
        .eq("company_id", company_id)
        .eq("user_id", user_id)
        .eq("filename", file.filename)
        .execute()
    )
    if existing_docs and getattr(existing_docs, "data", None):
        raise HTTPException(status_code=400, detail="PDF already exists for this company.")

    doc_id = str(uuid.uuid4())

    # Persist the raw PDF *before* creating the documents row / enqueueing —
    # if this fails, we haven't created any DB state that would need to be
    # cleaned up.
    storage_path = upload_raw_pdf(user_id, doc_id, pdf_bytes)

    supabase.table("documents").insert({
        "id": doc_id,
        "user_id": user_id,
        "company_id": company_id,
        "filename": file.filename,
        "file_size": len(pdf_bytes),
        "doc_type": doc_type,
        "fiscal_year": fiscal_year,
        "status": "processing",
    }).execute()

    # Hand off to background processing (arq queue if active, or in-process task fallback)
    arq_pool = getattr(request.app.state, "arq_pool", None)
    if arq_pool:
        try:
            await arq_pool.enqueue_job(
                "process_document_upload", doc_id, company_id, user_id, file.filename, storage_path
            )
            logger.info(f"Upload: Enqueued manual upload {doc_id} ({file.filename}) to arq worker queue.")
        except Exception as e:
            logger.warning(f"Upload: arq enqueue failed ({e}), falling back to in-process background task.")
            from app.worker import process_document_upload
            asyncio.create_task(
                process_document_upload(None, doc_id, company_id, user_id, file.filename, storage_path)
            )
    else:
        from app.worker import process_document_upload
        asyncio.create_task(
            process_document_upload(None, doc_id, company_id, user_id, file.filename, storage_path)
        )
        logger.info(f"Upload: arq pool unavailable, started background task for {doc_id}.")

    return UploadResponse(
        document_id=doc_id,
        filename=file.filename,
        page_count=None,
        chunk_count=None,
        status="processing",
    )