"""
AUTO RESEARCH AGENT
===================
This is a single sequential agent — NOT multi-agent, NOT LangGraph.

Why not LangGraph?
LangGraph adds a state machine graph, node definitions, edge conditions,
and a compiled runner. Our pipeline is linear with no looping or
conditional branching — a simple async function is cleaner and faster.

The "agent" here means: a function that autonomously decides what to
search for, evaluates results, and takes actions (download, process)
without the user directing each step.

Interview talking point:
"I implemented a research agent using a sequential tool-calling pattern.
The agent autonomously searches for reports, evaluates URL quality,
downloads the best candidate, and feeds it into the existing RAG pipeline.
I chose this over a graph-based framework like LangGraph because the
workflow is deterministic and linear — no replanning needed."
"""

import asyncio
from typing import Dict
from app.services.web_researcher import (
    fetch_company_news,
    find_annual_report_links,
    download_pdf_from_url
)
from app.services.pdf_parser import extract_text_by_page
from app.services.chunker import chunk_page_texts
from app.services.embedder import get_embeddings_batch
from app.services.llm import llm, MODEL  
from app.db.supabase import get_supabase
from app.utils.logger import logger
import uuid
from langsmith import traceable

@traceable(name="Summarize News Snippets", run_type="chain")
def summarize_news(company_name: str, ticker: str, news_text: str) -> str:
    summary_prompt = f"""You are an investment research assistant.
Summarise the following recent news about {company_name} ({ticker}) for a retail investor.
Focus on: earnings results, strategic developments, risks mentioned, analyst sentiment.
Keep it to 4-5 bullet points. Be factual, no speculation.

NEWS SNIPPETS:
{news_text}

SUMMARY:"""
    response = llm.invoke(summary_prompt)
    return response.content

from app.services.storage import upload_raw_pdf

@traceable(name="Run Auto Research Agent", run_type="chain")
async def run_auto_research(
    company_id: str,
    company_name: str,
    ticker: str,
    user_id: str,
    target_url: str = None,
    arq_pool = None
) -> Dict:
    """
    Main agent function. Returns a status dict with what was accomplished.
    """

    result = {
        "status":        "partial",
        "news_summary":  None,
        "news_items":    [],
        "pdf_processed": False,
        "document_id":   None,
        "message":       ""
    }

    supabase = get_supabase()

    # ── STEP 1: Fetch news (always runs on first call) ─────────────────────────
    if not target_url:
        logger.info(f"Auto-Research: Fetching news for {company_name} ({ticker})...")
        news_items = await fetch_company_news(company_name, ticker)
        
        if news_items:
            result["news_items"] = news_items[:8]
            news_text = "\n\n".join([
                f"Source: {item['title']}\n{item['snippet']}"
                for item in news_items[:6]
            ])
            try:
                result["news_summary"] = await asyncio.to_thread(summarize_news, company_name, ticker, news_text)
            except Exception as e:
                logger.warning(f"Auto-Research: news summary generation failed: {e}")
                result["news_summary"] = "Could not generate news summary."

        logger.info(f"Auto-Research: Searching for annual report candidate PDFs...")
        candidate_urls = await find_annual_report_links(company_name, ticker)
        
        result["status"] = "pending_confirmation"
        result["candidate_urls"] = candidate_urls
        return result

    # ── STEP 2: Process confirmed PDF ────────────────────────────
    pdf_bytes = None
    logger.info(f"Auto-Research: Downloading confirmed PDF: {target_url}")
    pdf_bytes = await download_pdf_from_url(target_url)

    if pdf_bytes and len(pdf_bytes) > 10000 and pdf_bytes[:4] == b"%PDF":
        logger.info(f"Auto-Research: PDF downloaded ({len(pdf_bytes)} bytes). Persisting and enqueueing...")
        doc_id = str(uuid.uuid4())
        filename = f"{ticker}_auto_research.pdf"

        # 1. Upload raw PDF to Supabase Storage
        storage_path = upload_raw_pdf(user_id, doc_id, pdf_bytes)

        # 2. Insert document record with status = 'processing'
        supabase.table("documents").insert({
            "id":          doc_id,
            "user_id":     user_id,
            "company_id":  company_id,
            "filename":    filename,
            "file_size":   len(pdf_bytes),
            "doc_type":    "annual_report",
            "fiscal_year": "auto",
            "status":      "processing"
        }).execute()

        # 3. Hand off background processing to arq worker (or background task fallback)
        if arq_pool:
            await arq_pool.enqueue_job(
                "process_document_upload", doc_id, company_id, user_id, filename, storage_path
            )
            logger.info(f"Auto-Research: Enqueued PDF {doc_id} to arq worker queue.")
        else:
            from app.worker import process_document_upload
            asyncio.create_task(
                process_document_upload(None, doc_id, company_id, user_id, filename, storage_path)
            )
            logger.info(f"Auto-Research: arq pool unavailable, started background task for {doc_id}.")

        result["pdf_processed"] = True
        result["document_id"]   = doc_id
        result["status"]        = "processing"
        result["message"]       = "Annual report downloaded and enqueued for background processing."
    else:
        result["status"]  = "failed"
        result["message"] = "Downloaded PDF was empty or invalid."

    return result
