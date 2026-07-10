"""
Fundamentals via SerpApi's Google Finance engine.

WHY: yfinance scrapes Yahoo directly and is prone to the crumb/cookie
poisoning + 429 issues documented in market_data.py's history. SerpApi is
also technically scraping (Google Finance, in this case) but the scraping
and proxy/anti-bot headache is SerpApi's problem to solve, not ours — we
just pay per call. One call here replaces yfinance's separate
.info / .financials / .balance_sheet / .cashflow round-trips.

SCOPE: this module only replaces the *fundamentals* path. Live price
refreshes keep using the free NSE Node microservice (see market_data.py) —
no reason to spend a paid SerpApi call on something that's already free,
fast, and working.

NOTE ON FIELD MAPPING: SerpApi's Google Finance JSON isn't a stable,
versioned schema — it's a structured scrape of a page Google can change
at will. Every lookup below is defensive (substring-matched against
labels, wrapped in .get() chains) rather than assuming exact keys exist.
If a field comes back None that you expected to see, check the raw
response logged at DEBUG level (`logger.debug`) and adjust the label
list in _find_stat / _find_financial_line — that's almost always the fix.
"""

import requests
from typing import Dict, List, Optional

from app.config import settings
from app.utils.logger import logger
from app.services.market_data import get_nse_symbol

SERPAPI_URL = "https://serpapi.com/search?engine=google_finance"


def _to_serp_query(ticker: str, exchange: str = "NSE") -> str:
    """SerpApi's Google Finance engine expects TICKER:EXCHANGE, e.g. 'MARUTI:NSE'."""
    base = get_nse_symbol(ticker)
    return f"{base}:{exchange}"


def _parse_number(val) -> Optional[float]:
    """SerpApi often returns numeric fields as formatted strings (commas, %, currency symbols)."""
    if val is None:
        return None
    if isinstance(val, (int, float)):
        return float(val)
    s = str(val).replace(",", "").replace("%", "").replace("₹", "").replace("$", "").strip()
    if not s or s.upper() in ("N/A", "-", "--"):
        return None
    try:
        return float(s)
    except ValueError:
        return None


def _find_stat(stats: List[Dict], *labels: str) -> Optional[str]:
    """Case-insensitive substring match against knowledge_graph.key_stats.stats labels."""
    for stat in stats or []:
        label = (stat.get("label") or "").lower()
        if any(l.lower() in label for l in labels):
            return stat.get("value")
    return None


def _find_financial_line(table: List[Dict], *labels: str) -> Optional[float]:
    """Case-insensitive substring match against a financial statement's line-item titles."""
    for row in table or []:
        title = (row.get("title") or "").lower()
        if any(l.lower() in title for l in labels):
            return _parse_number(row.get("value"))
    return None


def _find_financial_row(table: List[Dict], *labels: str) -> Optional[Dict]:
    for row in table or []:
        title = (row.get("title") or "").lower()
        if any(l.lower() in title for l in labels):
            return row
    return None


def _latest_period(results: List[Dict], period_type: str = "Annual") -> Optional[Dict]:
    """Most recent period of a given type from a financials statement's 'results' list."""
    if not results:
        return None
    matches = [r for r in results if (r.get("period_type") or "").lower() == period_type.lower()]
    pool = matches or results
    return pool[0] if pool else None


def _summarize_financials(financials_raw: List[Dict]) -> Dict:
    """
    Reduces SerpApi's nested income-statement/balance-sheet/cash-flow blocks into:
      - ratios: roe, debt_to_equity, profit_margin, revenue_growth, earnings_growth
                (none of these are given directly by Google Finance — derived here)
      - series: compact annual + quarterly revenue/net_income history for display
    """
    income_stmt = next((f for f in financials_raw if "income" in (f.get("title") or "").lower()), None)
    balance_sheet = next((f for f in financials_raw if "balance" in (f.get("title") or "").lower()), None)

    ratios: Dict = {}
    series: Dict = {"annual": [], "quarterly": []}

    if income_stmt:
        for period in income_stmt.get("results", []):
            table = period.get("table", [])
            entry = {
                "date": period.get("date"),
                "period_type": period.get("period_type"),
                "revenue": _find_financial_line(table, "revenue"),
                "net_income": _find_financial_line(table, "net income"),
            }
            bucket = "annual" if (period.get("period_type") or "").lower() == "annual" else "quarterly"
            series[bucket].append(entry)

        latest_income = _latest_period(income_stmt.get("results", []), "Annual")
        if latest_income:
            table = latest_income.get("table", [])
            revenue = _find_financial_line(table, "revenue")
            net_income = _find_financial_line(table, "net income")

            if revenue and net_income is not None:
                ratios["profit_margin"] = round(net_income / revenue, 4)

            revenue_row = _find_financial_row(table, "revenue")
            if revenue_row and revenue_row.get("change") is not None:
                pct = _parse_number(revenue_row["change"])
                ratios["revenue_growth"] = round(pct / 100, 4) if pct is not None else None

            net_income_row = _find_financial_row(table, "net income")
            if net_income_row and net_income_row.get("change") is not None:
                pct = _parse_number(net_income_row["change"])
                ratios["earnings_growth"] = round(pct / 100, 4) if pct is not None else None

            if balance_sheet and net_income is not None:
                bs_latest = _latest_period(balance_sheet.get("results", []), "Annual")
                if bs_latest:
                    equity = _find_financial_line(
                        bs_latest.get("table", []), "total equity", "shareholders equity", "stockholders equity"
                    )
                    if equity:
                        ratios["roe"] = round(net_income / equity, 4)

    if balance_sheet:
        bs_latest = _latest_period(balance_sheet.get("results", []), "Annual")
        if bs_latest:
            table = bs_latest.get("table", [])
            liabilities = _find_financial_line(table, "total liabilities")
            equity = _find_financial_line(table, "total equity", "shareholders equity", "stockholders equity")
            if liabilities is not None and equity:
                ratios["debt_to_equity"] = round(liabilities / equity, 2)

    return {"ratios": ratios, "series": series}


def fetch_fundamentals_serp(ticker: str, exchange: str = "NSE") -> Dict:
    """
    Fetches price, key stats, company "about" info, financial-statement-derived
    ratios, and recent news for a ticker — one SerpApi call, replacing yfinance's
    multiple separate lookups.

    Returns {} on any failure (missing key, network error, non-success response)
    so callers can fall back to cached data the same way they already do today.
    """
    if not settings.serpapi_key:
        logger.error("SERPAPI_KEY not configured — skipping SerpApi fundamentals fetch")
        return {}

    query = _to_serp_query(ticker, exchange)
    params = {
        "engine": "google_finance",
        "q": query,
        "api_key": settings.serpapi_key,
    }

    try:
        response = requests.get(SERPAPI_URL, params=params, timeout=15)
        response.raise_for_status()
        data = response.json()
    except requests.exceptions.RequestException as e:
        logger.error(f"SerpApi request failed for {query}: {e}")
        return {}
    except ValueError as e:
        logger.error(f"SerpApi returned non-JSON response for {query}: {e}")
        return {}

    if data.get("search_metadata", {}).get("status") != "Success":
        logger.error(f"SerpApi non-success status for {query}: {data.get('search_metadata')}")
        return {}

    logger.debug(f"SerpApi top-level keys for {query}: {list(data.keys())}")

    result: Dict = {}
    summary = data.get("summary", {}) or {}
    kg = data.get("knowledge_graph", {}) or {}

    logger.info(f"SerpApi kg keys for {query}: {list(kg.keys())}")
    logger.info(f"SerpApi summary keys for {query}: {list(summary.keys())}")
    if kg.get("key_stats"):
        logger.info(f"SerpApi key_stats: {kg['key_stats']}")

    # ── Live-ish price (fallback only — NSE node service is the primary source) ──
    price = summary.get("price", kg.get("price"))
    movement = summary.get("price_movement") or kg.get("price_movement") or {}
    result["current_price"] = _parse_number(price)
    if movement:
        pct = _parse_number(movement.get("percentage"))
        if pct is not None:
            result["pChange"] = -pct if (movement.get("movement") or "").lower() == "down" else pct

    # ── Key stats panel ──────────────────────────────────────────────────────
    stats = (kg.get("key_stats") or {}).get("stats", [])
    result["previous_close"] = _parse_number(_find_stat(stats, "previous close"))
    result["open"] = _parse_number(_find_stat(stats, "open"))
    result["market_cap"] = _parse_number(_find_stat(stats, "market cap"))
    result["pe_ratio"] = _parse_number(_find_stat(stats, "p/e ratio", "pe ratio"))

    year_range = _find_stat(stats, "year range")
    if year_range and "-" in str(year_range):
        lo, hi = str(year_range).split("-", 1)
        result["fifty_two_week_low"] = _parse_number(lo)
        result["fifty_two_week_high"] = _parse_number(hi)

    if "pChange" not in result and result.get("current_price") and result.get("previous_close"):
        change = result["current_price"] - result["previous_close"]
        result["pChange"] = round((change / result["previous_close"]) * 100, 2)

    # ── About / knowledge graph info ─────────────────────────────────────────
    # SerpApi's `about` field can be a dict {"snippet": "..."} or a list
    # [{"snippet": "...", ...}] depending on the ticker / page layout.
    about_raw = kg.get("about")
    if isinstance(about_raw, dict):
        about_block = about_raw
    elif isinstance(about_raw, list) and about_raw:
        about_block = about_raw[0] if isinstance(about_raw[0], dict) else {}
    else:
        about_block = {}

    info_raw = kg.get("info")
    if isinstance(info_raw, list):
        info_list = info_raw
    else:
        info_list = []
    info = {item.get("label", "").lower(): item.get("value") for item in info_list if isinstance(item, dict) and item.get("label")}

    result["description"] = about_block.get("snippet") if isinstance(about_block, dict) else None
    result["sector"] = info.get("sector")
    result["industry"] = info.get("industry")
    result["about"] = {
        "ceo": info.get("ceo"),
        "employees": info.get("employees"),
        "founded": info.get("founded"),
        "headquarters": info.get("headquarters"),
        "website": info.get("website"),
    }

    # ── Financial statements → derived ratios + compact series ──────────────
    financials_raw = data.get("financials", []) or []
    if financials_raw:
        summarized = _summarize_financials(financials_raw)
        result.update(summarized["ratios"])
        result["financials"] = summarized["series"]

    for key in ["roe", "debt_to_equity", "profit_margin", "revenue_growth", "earnings_growth"]:
        result.setdefault(key, None)

    # ── Recent news ───────────────────────────────────────────────────────────
    news_raw = data.get("news_results", []) or []
    result["news"] = [
        {
            "headline": n.get("snippet") or n.get("title"),
            "source": n.get("source"),
            "date": n.get("date"),
            "link": n.get("link"),
        }
        for n in news_raw[:5]
    ]

    return result
