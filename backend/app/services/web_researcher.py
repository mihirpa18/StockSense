from duckduckgo_search import DDGS
from typing import List, Dict, Optional
import httpx
import asyncio
from urllib.parse import urlparse, urlunparse
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


# ─── TOOL 1b: Search with timeout + retry ──────────────────────────────────
DDGS_TIMEOUT_SECONDS = 8
MAX_SEARCH_RETRIES = 2

async def _search_with_retry(query: str, max_results: int = 5) -> List[Dict]:
    """
    Wraps search_web in asyncio.to_thread + a hard timeout, with backoff retries.

    search_web already catches exceptions internally and returns [], so the
    failure mode we're actually guarding against here is DDGS *hanging* — the
    lite backend occasionally stalls under rate limiting instead of raising,
    which would otherwise block the whole auto-research pipeline for a company.

    Note: asyncio.wait_for cancels our *await*, not the underlying thread —
    Python can't forcibly kill a blocking call inside a thread. So a timed-out
    call may still finish in the background; that's an accepted tradeoff over
    letting one bad query stall everything.
    """
    for attempt in range(MAX_SEARCH_RETRIES + 1):
        try:
            return await asyncio.wait_for(
                asyncio.to_thread(search_web, query, max_results),
                timeout=DDGS_TIMEOUT_SECONDS,
            )
        except asyncio.TimeoutError:
            logger.warning(f"DDGS timed out (attempt {attempt + 1}) for query: {query}")
        except Exception as e:
            logger.warning(f"DDGS search failed (attempt {attempt + 1}) for query '{query}': {e}")
        if attempt < MAX_SEARCH_RETRIES:
            await asyncio.sleep(1.5 * (attempt + 1))
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
    queries = [
        f"{company_name} {ticker} stock latest news earnings 2025"
    ]

    all_results = []
    for i, query in enumerate(queries):
        if i > 0:
            await asyncio.sleep(2.0)  # Avoid DDG rate limiting
        results = await _search_with_retry(query, max_results=5)
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
EXCLUDE_KEYWORDS = {
    "presentation", "slides", "press-release", "pressrelease", "transcript",
    "factsheet", "summary", "brief", "investor-presentation", "concall",
    "notice", "agm-notice", "proxy",
}

# Path/domain signals used to rank candidates once we have several
POSITIVE_HINTS = {
    "annual-report": 5, "annualreport": 5, "annual_report": 5,
    "integrated-report": 3, "integratedreport": 3,
    "ar-2026": 4, "ar2026": 4, "ar-2025": 3, "ar2025": 3,
    "2026": 2, "2025": 1,
}
NEGATIVE_DOMAINS = ("moneycontrol", "screener.in", "scribd", "slideshare")


def _normalize_url(url: str) -> str:
    """Strip fragment/trailing slash so http/https or #page= variants of the
    same PDF dedupe correctly instead of both landing in the result set."""
    parsed = urlparse(url)
    return urlunparse(parsed._replace(fragment="")).rstrip("/")


def _score_url(url: str) -> int:
    url_lower = url.lower()
    score = sum(w for hint, w in POSITIVE_HINTS.items() if hint in url_lower)
    if any(dom in url_lower for dom in NEGATIVE_DOMAINS):
        score -= 3  # aggregator reposts are less trustworthy than the primary filing
    if url_lower.endswith(".pdf"):
        score += 1  # stronger signal than merely containing "pdf" in a query string
    return score


def _passes_filters(url: str) -> bool:
    url_lower = url.lower()
    if not (url_lower.endswith(".pdf") or "pdf" in url_lower):
        return False
    if any(k in url_lower for k in EXCLUDE_KEYWORDS):
        return False
    return True


async def find_annual_report_links(company_name: str, ticker: str) -> List[str]:
    """
    Finds direct downloadable PDF links for the latest annual report,
    ranked best-first by how likely each is to be the actual report
    (vs. a presentation, transcript, or aggregator repost).
    """
    search_queries = [
        f'"{company_name}" "{ticker}" annual report 2026 OR FY26 filetype:pdf',
        f'"{company_name}" "{ticker}" annual report 2025 OR FY25 filetype:pdf',
        f'"{ticker}" investor relations annual report pdf',
    ]

    candidates: Dict[str, str] = {}  # normalized_url -> original_url

    for i, query in enumerate(search_queries):
        if i > 0:
            await asyncio.sleep(1.5)
        results = await _search_with_retry(query, max_results=6)
        for result in results:
            url = result.get("url", "")
            if url and _passes_filters(url):
                candidates.setdefault(_normalize_url(url), url)

        if len(candidates) >= 5:
            break  # enough good candidates — stop burning DDGS calls / risking rate limits

    # Fallback if the strict queries find nothing — same filters apply here too
    # (the original bug: this branch skipped exclude_keywords entirely)
    if not candidates:
        await asyncio.sleep(1.0)
        results = await _search_with_retry(
            f'"{company_name}" {ticker} financial report filetype:pdf', max_results=4
        )
        for result in results:
            url = result.get("url", "")
            if url and _passes_filters(url):
                candidates.setdefault(_normalize_url(url), url)

    return sorted(candidates.values(), key=_score_url, reverse=True)