"""
Background worker for document uploads. Run as a separate process from the
web server:

    arq app.worker.WorkerSettings

The web process (upload.py) only validates the file, persists it to Storage,
creates the `documents` row, and enqueues a job here — it returns to the
client immediately. This process is what actually does the (potentially
slow) parse -> chunk -> embed -> insert work.
"""
import asyncio
from urllib.parse import urlparse

from arq.connections import RedisSettings

from app.config import settings
from app.services.pdf_parser import extract_text_by_page
from app.services.chunker import chunk_page_texts
from app.services.embedder import get_embeddings_batch
from app.services.storage import download_raw_pdf, delete_raw_pdf
from app.db.supabase import get_supabase
from app.utils.logger import logger


def _redis_settings_from_url(url: str) -> RedisSettings:
    """arq wants host/port/password/ssl as separate fields, not a single
    connection string — parsing the same REDIS_URL every other Redis
    consumer in this app already uses, so there's exactly one place
    (.env) that defines where Redis lives."""
    parsed = urlparse(url)
    return RedisSettings(
        host=parsed.hostname,
        port=parsed.port or 6379,
        password=parsed.password,
        ssl=parsed.scheme == "rediss",
    )


async def process_document_upload(
    ctx, doc_id: str, company_id: str, user_id: str, filename: str, storage_path: str
):
    """
    The pipeline previously inlined in upload.py's request handler, moved
    here so a large PDF can't block (or time out) the HTTP request that
    uploaded it.

    Still uses asyncio.to_thread for the CPU-bound steps (PDF parsing,
    chunking) even though this whole function already runs inside arq's
    own event loop — arq runs multiple jobs concurrently (see max_jobs in
    WorkerSettings below), and a blocking call here would stall every
    other job this worker is running, not just this one.
    """
    supabase = get_supabase()

    try:
        pdf_bytes = await asyncio.to_thread(download_raw_pdf, storage_path)

        pages = await asyncio.to_thread(extract_text_by_page, pdf_bytes)
        chunks = await asyncio.to_thread(chunk_page_texts, pages)

        if len(chunks) == 0:
            # A PDF that produced zero extractable chunks — likely scanned/
            # image-only pages, or pages under pdf_parser's minimum text
            # threshold. Reporting this as "ready" would be actively
            # misleading: the document exists in the DB but nothing about
            # it is searchable, and the chat feature will silently never
            # find anything for it. Treat it as a failure with a message
            # that actually tells the user what happened.
            raise ValueError(
                "No extractable text found in this PDF — it may be scanned "
                "images rather than text, or too short to process."
            )

        chunk_rows = []
        batch_size = 100
        for i in range(0, len(chunks), batch_size):
            batch_chunks = chunks[i : i + batch_size]
            batch_texts = [c["content"] for c in batch_chunks]

            # get_embeddings_batch already calls the Redis rate limiter
            # (acquire("mistral_embed", ...)) internally — nothing extra
            # needed here for that.
            embeddings = await asyncio.to_thread(get_embeddings_batch, batch_texts)

            for chunk, embedding in zip(batch_chunks, embeddings):
                chunk_rows.append({
                    "document_id": doc_id,
                    "company_id": company_id,
                    "user_id": user_id,
                    "chunk_index": chunk["chunk_index"],
                    "page_number": chunk["page_number"],
                    "content": chunk["content"],
                    "token_count": chunk["token_count"],
                    "embedding": embedding,
                })

            if i + batch_size < len(chunks):
                await asyncio.sleep(2)

        insert_batch_size = 50
        for i in range(0, len(chunk_rows), insert_batch_size):
            batch = chunk_rows[i : i + insert_batch_size]
            await asyncio.to_thread(
                lambda b=batch: supabase.table("chunks").insert(b).execute()
            )

        await asyncio.to_thread(
            lambda: supabase.table("documents").update({
                "status": "ready",
                "page_count": len(pages),
            }).eq("id", doc_id).execute()
        )

        await asyncio.to_thread(delete_raw_pdf, storage_path)

        logger.info(
            f"Document {doc_id} ({filename}) processed: {len(pages)} pages, {len(chunks)} chunks"
        )

    except Exception as e:
        logger.exception(f"Background processing failed for document {doc_id} ({filename}): {e}")
        await asyncio.to_thread(
            lambda: supabase.table("documents").update({
                "status": "failed",
            }).eq("id", doc_id).execute()
        )
        # Deliberately NOT re-raised. If it were, arq's default max_tries=5
        # would silently re-run this whole function — including re-spending
        # real Mistral embedding calls — against a document that's already
        # genuinely broken (corrupt PDF, malformed content, etc). The raw
        # PDF is left in Storage (delete_raw_pdf is only called on the
        # success path above) so a failed doc can be inspected or manually
        # reprocessed later without asking the user to re-upload.


class WorkerSettings:
    functions = [process_document_upload]
    redis_settings = _redis_settings_from_url(settings.redis_url)
    max_jobs = 5        # how many uploads this worker processes concurrently
    job_timeout = 600   # 10 min ceiling — generous for a large annual report