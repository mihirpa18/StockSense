"""
StockSense Test Suite: Multi-Document Background Queue Pipeline
================================================================

Tests background document processing queue and worker ingestion (app/worker.py)
under concurrent load with multiple synthetic PDF files.

Key checks:
1. Multi-file upload & storage persistence (raw-uploads bucket).
2. Asynchronous document ingestion via worker pipeline.
3. Database status transition verification (processing -> ready).
4. Chunk extraction and 1024-dim vector embedding insertion into pgvector.
5. Automatic cleanup of test artifacts.

Run from backend directory:
    .venv/bin/python test/test_queue_pipeline_concurrency.py
"""

import os
import sys
import time
import uuid
import asyncio
import fitz  # PyMuPDF

# Ensure backend directory is in python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()

from app.services.storage import upload_raw_pdf, delete_raw_pdf
from app.worker import process_document_upload
from app.db.supabase import get_supabase


def create_synthetic_pdf(title: str, pages_count: int = 3) -> bytes:
    """Generates a valid in-memory PDF document using PyMuPDF."""
    doc = fitz.open()
    for page_num in range(1, pages_count + 1):
        page = doc.new_page()
        text = (
            f"{title} - Fiscal Year 2024 Report\n"
            f"Page {page_num} of {pages_count}\n\n"
            f"Financial Highlights: Executive summary for {title}. "
            f"Revenue increased by 15% year-over-year. Operating margin expanded to 22%.\n"
            f"Strategic Priorities: Accelerating cloud migration, AI research integration, and market expansion.\n"
            f"Key Risks: Foreign exchange volatility, supply chain disruptions, and regulatory shifts.\n"
        )
        page.insert_text((50, 50), text, fontsize=11)
    
    pdf_bytes = doc.tobytes()
    doc.close()
    return pdf_bytes


async def test_multi_document_queue_pipeline():
    print("\n" + "="*70)
    print("TEST: Multi-Document Background Queue Pipeline")
    print("="*70)

    supabase = get_supabase()

    # 1. Fetch or create a test company
    comp_res = supabase.table("companies").select("id, ticker").limit(1).execute()
    if comp_res.data and len(comp_res.data) > 0:
        company_id = comp_res.data[0]["id"]
        ticker = comp_res.data[0]["ticker"]
    else:
        c_insert = supabase.table("companies").insert({
            "name": "Test Queue Corp",
            "ticker": "TESTQUEUE",
            "exchange": "NSE"
        }).execute()
        company_id = c_insert.data[0]["id"]
        ticker = "TESTQUEUE"

    # Get test user ID from profiles
    prof_res = supabase.table("profiles").select("id").limit(1).execute()
    if prof_res.data and len(prof_res.data) > 0:
        user_id = prof_res.data[0]["id"]
    else:
        user_id = str(uuid.uuid4())

    print(f"Using Test Context: Company ID = {company_id} ({ticker}), User ID = {user_id}")

    # 2. Generate 3 synthetic PDF annual reports
    sample_files = [
        {"name": f"TEST_Report_Q1_{uuid.uuid4().hex[:4]}.pdf", "pages": 2},
        {"name": f"TEST_Report_Q2_{uuid.uuid4().hex[:4]}.pdf", "pages": 3},
        {"name": f"TEST_Report_Q3_{uuid.uuid4().hex[:4]}.pdf", "pages": 2},
    ]

    documents_to_clean = []

    print(f"\nGenerating and uploading {len(sample_files)} synthetic PDF files...")

    # Stage 1: Upload PDFs & Create 'processing' DB stubs
    doc_tasks = []
    for file_info in sample_files:
        doc_id = str(uuid.uuid4())
        filename = file_info["name"]
        pdf_bytes = create_synthetic_pdf(filename.replace(".pdf", ""), pages_count=file_info["pages"])

        # Upload to Storage
        storage_path = upload_raw_pdf(user_id, doc_id, pdf_bytes)

        # Create DB entry with status = 'processing'
        supabase.table("documents").insert({
            "id": doc_id,
            "user_id": user_id,
            "company_id": company_id,
            "filename": filename,
            "file_size": len(pdf_bytes),
            "doc_type": "annual_report",
            "fiscal_year": "FY24",
            "status": "processing"
        }).execute()

        documents_to_clean.append({"doc_id": doc_id, "storage_path": storage_path})
        doc_tasks.append((doc_id, company_id, user_id, filename, storage_path))
        print(f"  [Created Stub] {filename} (ID: {doc_id[:8]}...) -> status: processing")

    # Stage 2: Process jobs concurrently using worker pipeline
    print(f"\nExecuting {len(doc_tasks)} background worker jobs concurrently...")
    start_time = time.time()

    async def run_worker_job(task_info):
        doc_id, comp_id, u_id, fname, s_path = task_info
        await process_document_upload(None, doc_id, comp_id, u_id, fname, s_path)

    # Run all worker ingestion jobs in parallel
    await asyncio.gather(*[run_worker_job(t) for t in doc_tasks])
    total_duration = time.time() - start_time
    print(f"All worker jobs completed in {total_duration:.2f} seconds.")

    # Stage 3: Verification & Assertions
    print("\nVerifying database results...")
    for item in documents_to_clean:
        d_id = item["doc_id"]
        
        # Verify Document Status
        doc_res = supabase.table("documents").select("filename, status, page_count").eq("id", d_id).single().execute()
        doc_data = doc_res.data
        print(f"  [Doc Verification] {doc_data['filename']} -> Status: {doc_data['status']}, Pages: {doc_data['page_count']}")
        
        assert doc_data["status"] == "ready", f"Document {d_id} failed to transition to status 'ready'!"
        assert doc_data["page_count"] is not None and doc_data["page_count"] > 0, "page_count was not updated!"

        # Verify Vector Chunks in pgvector
        chunks_res = supabase.table("chunks").select("id, page_number, token_count").eq("document_id", d_id).execute()
        chunk_count = len(chunks_res.data or [])
        print(f"  [Chunks Verification] {doc_data['filename']} -> Inserted {chunk_count} vector chunks into pgvector.")
        assert chunk_count > 0, f"No chunks were inserted into pgvector table for document {d_id}!"

    # Stage 4: Clean up test documents & chunks from database
    print("\nCleaning up test artifacts from Supabase...")
    for item in documents_to_clean:
        supabase.table("documents").delete().eq("id", item["doc_id"]).execute()
        try:
            delete_raw_pdf(item["storage_path"])
        except Exception:
            pass
    print("Cleaned up test documents and storage files.")

    print("\n" + "="*70)
    print("🎉 SUCCESS: Multi-Document Background Queue Pipeline Passed!")
    print("="*70 + "\n")


if __name__ == "__main__":
    asyncio.run(test_multi_document_queue_pipeline())
