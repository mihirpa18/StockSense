"""
Raw PDF storage — the actual bytes never go through Redis/arq. Only a
storage path (a short string) travels through the job queue.

Why: Upstash enforces a max request size and free-tier data caps. A 50MB
PDF as a job argument risks getting rejected outright, and would burn
through the 256MB free-tier storage budget fast if more than a couple are
in flight. Persisting to Supabase Storage first and passing a pointer is
also just the standard pattern for background file processing — it
survives a worker crash mid-job, where an in-memory-only queue payload
wouldn't.

Bucket: "raw-uploads" — private, not public. Must be created once via the
Supabase dashboard (Storage -> New bucket -> uncheck "Public bucket") before
this will work; this module doesn't create it automatically because bucket
creation is a one-time infra step, not something that should happen as a
side effect of a random upload request.
"""
from app.db.supabase import get_supabase

BUCKET = "raw-uploads"


def upload_raw_pdf(user_id: str, doc_id: str, pdf_bytes: bytes) -> str:
    """Uploads the PDF, returns the storage path to pass to the worker."""
    path = f"{user_id}/{doc_id}.pdf"
    supabase = get_supabase()
    supabase.storage.from_(BUCKET).upload(
        path,
        pdf_bytes,
        file_options={"content-type": "application/pdf", "upsert": "true"},
    )
    return path


def download_raw_pdf(path: str) -> bytes:
    supabase = get_supabase()
    return supabase.storage.from_(BUCKET).download(path)


def delete_raw_pdf(path: str) -> None:
    """Called after successful processing — no need to keep the raw PDF
    around once it's parsed, chunked, and embedded into Postgres. Left in
    place on failure, deliberately, so a failed document can be inspected
    or reprocessed without asking the user to re-upload."""
    supabase = get_supabase()
    supabase.storage.from_(BUCKET).remove([path])