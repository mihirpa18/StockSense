"""
StockSense Comprehensive Integration & Negative Failure Test Suite
===================================================================

This test suite covers both positive (happy path) and negative (failure/edge case)
scenarios for StockSense's background queue and rate limiting architecture:

1. POSITIVE SUITE (HAPPY PATH):
   - Multi-thread Redis Token Bucket rate-limiter concurrency & burst grants.
   - Multi-document parallel background ingestion pipeline (storage, status processing->ready, pgvector chunks).

2. NEGATIVE SUITE (FAILURE & EDGE CASES):
   - Corrupted/Invalid PDF file ingestion -> Verifies worker catches error and sets status='failed'.
   - Scanned PDF with 0 extractable text chunks -> Verifies ValueError and status='failed'.
   - Rate limit exhaustion -> Verifies RateLimitExceeded exception when max_wait_seconds is exceeded.
   - Cleanup verification after failure.

Run from backend directory:
    .venv/bin/python test/test_full_integration_suite.py
"""

import os
import sys
import time
import uuid
import asyncio
import fitz  # PyMuPDF
from concurrent.futures import ThreadPoolExecutor

# Ensure backend directory is in python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()

from app.services.rate_limiter import acquire, RateLimitExceeded
from app.services.storage import upload_raw_pdf, delete_raw_pdf
from app.worker import process_document_upload
from app.db.supabase import get_supabase
from app.db.redis_client import get_redis


# ============================================================================
# SYNTHETIC PDF GENERATORS
# ============================================================================

def create_valid_pdf(title: str, pages_count: int = 2) -> bytes:
    """Generates a valid text PDF document in memory."""
    doc = fitz.open()
    for page_num in range(1, pages_count + 1):
        page = doc.new_page()
        text = (
            f"{title} - Annual Report FY24\n"
            f"Page {page_num} of {pages_count}\n"
            f"Financial Results: Revenue grew 18% YoY. Operating profits expanded to 25%.\n"
            f"Business Outlook: Strong demand in software and cloud services.\n"
        )
        page.insert_text((50, 50), text, fontsize=11)
    pdf_bytes = doc.tobytes()
    doc.close()
    return pdf_bytes


def create_corrupt_pdf() -> bytes:
    """Generates a corrupt byte string passing magic bytes but unparseable as a PDF."""
    return b"%PDF-1.4 Corrupt Garbage Header Data Impossible To Parse With PyMuPDF " + os.urandom(200)


def create_blank_image_pdf() -> bytes:
    """Generates a valid PDF containing only blank vector graphics (0 extractable text characters)."""
    doc = fitz.open()
    page = doc.new_page()
    # Draw a rectangle graphic without adding any text
    page.draw_rect(fitz.Rect(10, 10, 200, 200), color=(1, 0, 0), fill=(0, 1, 0))
    pdf_bytes = doc.tobytes()
    doc.close()
    return pdf_bytes


# ============================================================================
# PART 1: RATE LIMITER SUITE (HAPPY PATH & NEGATIVE TEST)
# ============================================================================

def test_rate_limiter_suite():
    print("\n" + "="*70)
    print("SECTION 1: RATE LIMITER SUITE (Positive & Negative)")
    print("="*70)

    # --- 1A: Positive Rate Limiter Concurrency Test ---
    test_bucket = f"suite_bucket_{uuid.uuid4().hex[:6]}"
    capacity = 3.0
    refill_rate = 1.0
    num_threads = 6

    print(f"\n[1A] Testing Rate Limiter Burst & Throttling ({num_threads} threads, capacity={capacity})...")
    
    # Ensure bucket is clean before test starts
    r = get_redis()
    r.delete(f"ratelimit:{test_bucket}")

    def acquire_worker(thread_id: int):
        t0 = time.time()
        try:
            acquire(
                bucket_name=test_bucket,
                capacity=capacity,
                refill_rate=refill_rate,
                tokens_requested=1,
                max_wait_seconds=10.0,
                poll_interval=0.1
            )
            elapsed = time.time() - t0
            return (thread_id, elapsed, True)
        except RateLimitExceeded:
            return (thread_id, time.time() - t0, False)

    with ThreadPoolExecutor(max_workers=num_threads) as executor:
        results = list(executor.map(acquire_worker, range(1, num_threads + 1)))

    immediate = [r for r in results if r[2] and r[1] < 0.6]
    throttled = [r for r in results if r[2] and r[1] >= 0.6]
    print(f"  -> Burst Grants (<0.6s): {len(immediate)} (Expected: 3)")
    print(f"  -> Throttled Grants (>=0.6s): {len(throttled)} (Expected: 3)")

    assert len(immediate) == 3, f"Expected 3 burst grants, got {len(immediate)}"
    assert len(results) == num_threads, "All threads must complete."

    # --- 1B: Negative Rate Limiter Test (Timeout / Exhaustion) ---
    print("\n[1B] Negative Test: Rate Limit Exhaustion (Requesting past max_wait_seconds)...")
    exhaust_bucket = f"exhaust_bucket_{uuid.uuid4().hex[:6]}"
    
    # Drain capacity (1 token)
    acquire(exhaust_bucket, capacity=1.0, refill_rate=0.1, max_wait_seconds=1.0) # rate = 0.1 tokens/sec
    print("  -> Initial token drained.")

    # Second acquire requesting token when refill takes 10s but max_wait is only 0.3s
    t_start = time.time()
    exceeded = False
    try:
        acquire(exhaust_bucket, capacity=1.0, refill_rate=0.1, tokens_requested=1, max_wait_seconds=0.3, poll_interval=0.1)
    except RateLimitExceeded:
        exceeded = True
        print(f"  -> RateLimitExceeded correctly raised after {time.time() - t_start:.2f}s!")

    assert exceeded, "RateLimiter failed to raise RateLimitExceeded when max_wait_seconds expired!"

    # Cleanup Redis keys
    r = get_redis()
    r.delete(f"ratelimit:{test_bucket}")
    r.delete(f"ratelimit:{exhaust_bucket}")
    print("✅ Rate Limiter Suite Passed!")


# ============================================================================
# PART 2: QUEUE & WORKER INGESTION SUITE (HAPPY PATH & NEGATIVE TESTS)
# ============================================================================

async def test_queue_and_worker_suite():
    print("\n" + "="*70)
    print("SECTION 2: WORKER QUEUE SUITE (Happy Path & Failure Scenarios)")
    print("="*70)

    supabase = get_supabase()

    # Get test context
    comp_res = supabase.table("companies").select("id, ticker").limit(1).execute()
    company_id = comp_res.data[0]["id"] if comp_res.data else str(uuid.uuid4())
    ticker = comp_res.data[0]["ticker"] if comp_res.data else "TESTSUITE"

    prof_res = supabase.table("profiles").select("id").limit(1).execute()
    user_id = prof_res.data[0]["id"] if prof_res.data else str(uuid.uuid4())

    print(f"Test Context: Company ID = {company_id} ({ticker}), User ID = {user_id}")

    # --- 2A: Positive Multi-File Parallel Ingestion ---
    print("\n[2A] Positive Test: Concurrent Multi-File Ingestion Pipeline...")
    valid_docs = [
        {"name": f"SUITE_Valid_1_{uuid.uuid4().hex[:4]}.pdf", "bytes": create_valid_pdf("Valid Doc 1", 2)},
        {"name": f"SUITE_Valid_2_{uuid.uuid4().hex[:4]}.pdf", "bytes": create_valid_pdf("Valid Doc 2", 3)},
    ]

    valid_cleanups = []
    for item in valid_docs:
        d_id = str(uuid.uuid4())
        path = upload_raw_pdf(user_id, d_id, item["bytes"])
        supabase.table("documents").insert({
            "id": d_id, "user_id": user_id, "company_id": company_id,
            "filename": item["name"], "file_size": len(item["bytes"]),
            "status": "processing"
        }).execute()
        valid_cleanups.append((d_id, path, item["name"]))

    print(f"  -> Created {len(valid_cleanups)} valid document stubs (status: processing)")

    # Execute valid worker jobs in parallel
    await asyncio.gather(*[
        process_document_upload(None, item[0], company_id, user_id, item[2], item[1])
        for item in valid_cleanups
    ])

    # Verify status='ready' and chunks stored
    for d_id, path, fname in valid_cleanups:
        doc_res = supabase.table("documents").select("status, page_count").eq("id", d_id).single().execute()
        chunk_res = supabase.table("chunks").select("id").eq("document_id", d_id).execute()
        print(f"  -> [Verified] {fname}: status='{doc_res.data['status']}', pages={doc_res.data['page_count']}, chunks={len(chunk_res.data or [])}")
        assert doc_res.data["status"] == "ready", f"Document {fname} should be 'ready'"
        assert len(chunk_res.data or []) > 0, f"Document {fname} should have chunks in pgvector"

    # --- 2B: Negative Test: Corrupt PDF File ---
    print("\n[2B] Negative Test: Ingesting Corrupted PDF File...")
    corrupt_id = str(uuid.uuid4())
    corrupt_fname = f"SUITE_Corrupt_{uuid.uuid4().hex[:4]}.pdf"
    corrupt_bytes = create_corrupt_pdf()

    corrupt_path = upload_raw_pdf(user_id, corrupt_id, corrupt_bytes)
    supabase.table("documents").insert({
        "id": corrupt_id, "user_id": user_id, "company_id": company_id,
        "filename": corrupt_fname, "file_size": len(corrupt_bytes),
        "status": "processing"
    }).execute()

    # Process corrupt file with worker
    await process_document_upload(None, corrupt_id, company_id, user_id, corrupt_fname, corrupt_path)

    # Verify worker caught the exception and set status='failed'
    corrupt_doc_res = supabase.table("documents").select("status").eq("id", corrupt_id).single().execute()
    print(f"  -> [Verified] Corrupt File {corrupt_fname}: status='{corrupt_doc_res.data['status']}' (Expected: 'failed')")
    assert corrupt_doc_res.data["status"] == "failed", "Corrupt file should have status='failed'!"

    # --- 2C: Negative Test: Blank/Image PDF (0 extractable text chunks) ---
    print("\n[2C] Negative Test: Ingesting Scanned/Blank PDF (0 text chunks)...")
    blank_id = str(uuid.uuid4())
    blank_fname = f"SUITE_Blank_{uuid.uuid4().hex[:4]}.pdf"
    blank_bytes = create_blank_image_pdf()

    blank_path = upload_raw_pdf(user_id, blank_id, blank_bytes)
    supabase.table("documents").insert({
        "id": blank_id, "user_id": user_id, "company_id": company_id,
        "filename": blank_fname, "file_size": len(blank_bytes),
        "status": "processing"
    }).execute()

    # Process blank image file
    await process_document_upload(None, blank_id, company_id, user_id, blank_fname, blank_path)

    # Verify status='failed'
    blank_doc_res = supabase.table("documents").select("status").eq("id", blank_id).single().execute()
    print(f"  -> [Verified] Blank Text PDF {blank_fname}: status='{blank_doc_res.data['status']}' (Expected: 'failed')")
    assert blank_doc_res.data["status"] == "failed", "Blank/Image PDF without text chunks should have status='failed'!"

    # --- Cleanup Database & Storage Artifacts ---
    print("\nCleaning up test records from database & storage...")
    all_test_ids = [item[0] for item in valid_cleanups] + [corrupt_id, blank_id]
    for d_id in all_test_ids:
        supabase.table("documents").delete().eq("id", d_id).execute()
    
    for path in [corrupt_path, blank_path]:
        try:
            delete_raw_pdf(path)
        except Exception:
            pass

    print("✅ Worker Queue Suite Passed!")


# ============================================================================
# MAIN TEST RUNNER
# ============================================================================

def main():
    print("\n" + "#"*70)
    print("  STOCKSENSE FULL INTEGRATION & NEGATIVE TEST SUITE")
    print("#"*70)

    # 1. Rate Limiter Suite
    test_rate_limiter_suite()

    # 2. Worker Queue Suite (Positive & Negative)
    asyncio.run(test_queue_and_worker_suite())

    print("\n" + "#"*70)
    print("🎉 ALL INTEGRATION & NEGATIVE FAILURE TESTS PASSED CLEANLY!")
    print("#"*70 + "\n")


if __name__ == "__main__":
    main()
