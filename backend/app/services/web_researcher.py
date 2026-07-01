from duckduckgo_search import DDGS
from typing import List, Dict, Optional
import httpx
import asyncio
from app.utils.logger import logger

# ─── TOOL 1: Web Search ───────────────────────────────────────────────────
def search_web(query: str, max_results: int = 5) -> List[Dict]:
    """
    Searches DuckDuckGo and returns list of:
    [{title, url, snippet}]

    Free, no API key. Rate limit: ~5 requests/second.
    Add asyncio.sleep(1) between calls if hitting limits.
    """
    try:
        # Using backend="lite" to bypass the aggressive JS/VQD rate limiting (202 Ratelimit)
        with DDGS() as ddgs:
            results = list(ddgs.text(query, max_results=max_results, backend="lite"))
            return [
                {
                    "title":   r.get("title", ""),
                    "url":     r.get("href", ""),
                    "snippet": r.get("body", "")
                }
                for r in results
            ]
    except Exception as e:
        logger.error(f"Search error for query '{query}': {e}")
        return []

import socket
from urllib.parse import urlparse
import ipaddress

def is_safe_url(url: str) -> bool:
    """
    Validates that a URL is safe to download from.
    1. Scheme must be HTTP or HTTPS.
    2. Hostname must be resolvable.
    3. Resolved IP must NOT be a private, loopback, or local IP (SSRF mitigation).
    """
    try:
        parsed = urlparse(url)
        if parsed.scheme not in ("http", "https"):
            return False
            
        hostname = parsed.hostname
        if not hostname:
            return False
            
        # Resolve hostname to IP address
        ip = socket.gethostbyname(hostname)
        ip_obj = ipaddress.ip_address(ip)
        
        # Block SSRF targets (private networks, localhost, metadata endpoints)
        if ip_obj.is_private or ip_obj.is_loopback or ip_obj.is_link_local:
            return False
            
        return True
    except Exception:
        return False

# ─── TOOL 2: PDF Downloader (Secure Version) ───────────────────────────────
async def download_pdf_from_url(url: str) -> Optional[bytes]:
    """
    Downloads a PDF from a given URL with strict security guardrails.
    Returns bytes or None if download/validation fails.
    
    SECURITY MEASURES:
    1. SSRF Mitigation: Blocks local, loopback, and private IP addresses.
    2. Size Limit: Aborts download if file exceeds 50MB (prevents DoS).
    3. Content Verification: Enforces PDF Content-Type and %PDF magic bytes check.
    """
    if not is_safe_url(url):
        logger.warning(f"Security Alert: Blocked download from unsafe URL: {url}")
        return None

    try:
        MAX_SIZE = 50 * 1024 * 1024 # 50 MB max limit
        
        async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            }
            
            # Download file in chunks to verify size mid-stream (prevents DoS)
            async with client.stream("GET", url, headers=headers) as response:
                if response.status_code != 200:
                    logger.warning(f"Failed to download PDF from {url} - Status Code: {response.status_code}")
                    return None
                    
                # Validate response headers
                content_type = response.headers.get("content-type", "")
                if "application/pdf" not in content_type and not url.lower().endswith(".pdf"):
                    logger.warning(f"Security Alert: Rejected invalid content type: {content_type} from URL: {url}")
                    return None
                    
                content_length = response.headers.get("content-length")
                if content_length and int(content_length) > MAX_SIZE:
                    logger.warning(f"Security Alert: File size header exceeds 50MB limit ({content_length} bytes) for URL: {url}")
                    return None
                
                content = bytearray()
                async for chunk in response.aiter_bytes(chunk_size=8192):
                    content.extend(chunk)
                    if len(content) > MAX_SIZE:
                        logger.warning(f"Security Alert: Aborted download. Content exceeded 50MB mid-stream for URL: {url}")
                        return None
                
                # Validate PDF magic bytes (%PDF) to prevent execution of malicious code/scripts
                if len(content) < 4 or content[:4] != b'%PDF':
                    logger.warning(f"Security Alert: Magic number mismatch. Downloaded file from {url} is not a valid PDF.")
                    return None
                    
                return bytes(content)
    except Exception as e:
        logger.error(f"Download error for {url}: {e}")
        return None

# ─── TOOL 3: News Fetcher ──────────────────────────────────────────────────
async def fetch_company_news(company_name: str, ticker: str) -> List[Dict]:
    """
    Returns recent news snippets for a company.
    These are used for the news summary section — NOT fed into the RAG pipeline.
    """
    # Optimized to a single, high-quality query to reduce rate limit hits
    queries = [
        f"{company_name} {ticker} stock latest news earnings 2024"
    ]

    all_results = []
    for i, query in enumerate(queries):
        if i > 0:
            await asyncio.sleep(2.0)  # Avoid DDG rate limiting
        results = search_web(query, max_results=5)
        all_results.extend(results)

    # Deduplicate by URL
    seen = set()
    unique = []
    for r in all_results:
        if r["url"] not in seen:
            seen.add(r["url"])
            unique.append(r)

    return unique[:8]

# ─── TOOL 4: PDF Link Finder ───────────────────────────────────────────────
async def find_annual_report_links(company_name: str, ticker: str) -> List[str]:
    """
    Tries to find direct downloadable PDF links for the latest annual report.
    Returns a list of candidate URLs, ordered by priority.
    """
    # Optimized to a single, highly-targeted filetype query to reduce DDG hits
    search_queries = [
        f"{company_name} {ticker} annual report latest year filetype:pdf site:bseindia.com OR site:nseindia.com"
    ]

    urls = []
    seen = set()
    for i, query in enumerate(search_queries):
        if i > 0:
            await asyncio.sleep(2.0)
        results = search_web(query, max_results=5)
        for result in results:
            url = result.get("url", "")
            if url and url not in seen:
                if url.endswith(".pdf") or "pdf" in url.lower():
                    seen.add(url)
                    urls.append(url)

    # Fallback if the strict query finds nothing, try a slightly broader one
    if not urls:
        await asyncio.sleep(2.0)
        results = search_web(f"{company_name} {ticker} annual report investor presentation filetype:pdf", max_results=3)
        for result in results:
            url = result.get("url", "")
            if url and url not in seen and (url.endswith(".pdf") or "pdf" in url.lower()):
                seen.add(url)
                urls.append(url)

    return urls
