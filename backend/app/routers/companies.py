import asyncio
from fastapi import APIRouter, HTTPException, Query, Depends, Request
from app.models.schemas import CompanyCreate
from app.db.supabase import get_supabase
from app.dependencies import get_current_user_id
from app.services.market_data import fetch_price_only
from app.services.market_data_serp import fetch_fundamentals_serp as fetch_fundamentals
from app.services.auto_research_agent import run_auto_research
from app.utils.logger import logger
from pydantic import BaseModel as PydanticBaseModel
from typing import List, Optional
from datetime import datetime, timezone, timedelta

router = APIRouter()

# NOTE ON ROUTE ORDER: /search and /watchlist must be registered BEFORE /{company_id}.
# FastAPI matches routes in registration order, and literal paths would otherwise be
# swallowed by the dynamic /{company_id} route.

@router.get("/search")
async def search_companies(q: str = Query(..., min_length=1)):
    """Search companies by name or ticker (case-insensitive)."""
    supabase = get_supabase()
    result = supabase.table("companies")\
        .select("*")\
        .or_(f"name.ilike.%{q}%,ticker.ilike.%{q}%")\
        .limit(10)\
        .execute()
    return result.data or []

@router.get("/watchlist")
async def get_watchlist(user_id: str = Depends(get_current_user_id)):
    supabase = get_supabase()
    result = supabase.table("watchlist")\
        .select("*, companies(*)")\
        .eq("user_id", user_id)\
        .execute()
    return result.data or []

@router.post("/watchlist/{company_id}")
async def add_to_watchlist(company_id: str, user_id: str = Depends(get_current_user_id)):
    supabase = get_supabase()
    result = supabase.table("watchlist")\
        .upsert({"user_id": user_id, "company_id": company_id})\
        .execute()
    return {"status": "added"}

@router.delete("/watchlist/{company_id}")
async def remove_from_watchlist(company_id: str, user_id: str = Depends(get_current_user_id)):
    supabase = get_supabase()
    supabase.table("watchlist")\
        .delete()\
        .eq("user_id", user_id)\
        .eq("company_id", company_id)\
        .execute()
    return {"status": "removed"}

@router.post("/")
async def create_company(company: CompanyCreate):
    """Create a new company record. Used when a user adds a company not yet in DB."""
    supabase = get_supabase()
    result = supabase.table("companies")\
        .upsert(company.dict(), on_conflict="ticker,exchange")\
        .execute()
    return result.data[0]

# ─── Bulk price refresh for watchlist ──────────────────────────────────────
# NOTE: This MUST be registered before /{company_id} to avoid path collision.

class BulkPriceRefreshReq(PydanticBaseModel):
    company_ids: List[str]

@router.post("/refresh-prices")
async def refresh_prices_bulk(req: BulkPriceRefreshReq, user_id: str = Depends(get_current_user_id)):
    """
    Bulk price refresh for multiple companies at once.
    Only fetches price data (NSE node), no fundamentals.
    Returns a dict mapping company_id -> updated fundamentals_cache.
    """
    supabase = get_supabase()
    results = {}

    for cid in req.company_ids:
        try:
            row = supabase.table("companies").select("ticker, exchange, fundamentals_cache")\
                .eq("id", cid).maybe_single().execute()

            if not row or getattr(row, "data", None) is None:
                continue

            company = row.data
            price_data = await asyncio.to_thread(fetch_price_only, company["ticker"], company.get("exchange", "NSE"))

            if price_data.get("current_price") is not None:
                existing_cache = company.get("fundamentals_cache") or {}
                existing_cache.update(price_data)

                supabase.table("companies").update({
                    "fundamentals_cache": existing_cache,
                    "cache_updated_at":   datetime.now(timezone.utc).isoformat()
                }).eq("id", cid).execute()

                results[cid] = existing_cache
            else:
                results[cid] = company.get("fundamentals_cache") or {}
        except Exception as e:
            logger.error(f"Bulk price refresh error for {cid}: {e}")
            results[cid] = {}

    return results


@router.get("/{company_id}")
async def get_company(company_id: str):
    supabase = get_supabase()
    result = supabase.table("companies")\
        .select("*")\
        .eq("id", company_id)\
        .maybe_single()\
        .execute()
    if not result or getattr(result, "data", None) is None:
        raise HTTPException(status_code=404, detail="Company not found")
    return result.data

# ─── ADDENDUM A.3: Fundamentals endpoint ──────────────────────────────────
@router.get("/{company_id}/fundamentals")
async def get_fundamentals(company_id: str):
    """
    Fetches live fundamentals from yfinance for a given company.
    Falls back to cached values in DB if yfinance fails.
    """
    supabase = get_supabase()

    # Get ticker from DB
    result = supabase.table("companies").select("ticker, exchange, fundamentals_cache, cache_updated_at")\
        .eq("id", company_id).maybe_single().execute()

    if not result or getattr(result, "data", None) is None:
        raise HTTPException(status_code=404, detail="Company not found")

    company = result.data
    ticker  = company["ticker"]
    exchange = company.get("exchange", "NSE")

    # Check cache — refresh if older than 72 hours (fundamentals rarely change daily)
    cache_age_ok = False
    if company.get("cache_updated_at"):
        cached_at = datetime.fromisoformat(company["cache_updated_at"].replace("Z", "+00:00"))
        cache_age_ok = (datetime.now(timezone.utc) - cached_at) < timedelta(hours=72)

    fundamentals_cache = company.get("fundamentals_cache")
    if cache_age_ok and fundamentals_cache and fundamentals_cache.get("current_price") is not None:
        return fundamentals_cache

    # Fetch fresh data
    fundamentals = await asyncio.to_thread(fetch_fundamentals, ticker, exchange)

    if fundamentals and fundamentals.get("current_price") is not None:
        # Cache in DB
        supabase.table("companies").update({
            "fundamentals_cache": fundamentals,
            "cache_updated_at":   datetime.now(timezone.utc).isoformat()
        }).eq("id", company_id).execute()

    return fundamentals if fundamentals.get("current_price") is not None else (company.get("fundamentals_cache") or {})

# ─── Price refresh (lightweight, no yfinance) ─────────────────────────────

@router.post("/{company_id}/refresh-price")
async def refresh_price(company_id: str):
    """
    Lightweight price refresh — only hits NSE node service.
    Merges fresh price fields into the existing fundamentals_cache
    so cached fundamentals (PE, ROE etc.) are preserved.
    """
    supabase = get_supabase()
    result = supabase.table("companies").select("ticker, exchange, fundamentals_cache")\
        .eq("id", company_id).maybe_single().execute()

    if not result or getattr(result, "data", None) is None:
        raise HTTPException(status_code=404, detail="Company not found")

    company = result.data
    price_data = await asyncio.to_thread(fetch_price_only, company["ticker"], company.get("exchange", "NSE"))

    if price_data.get("current_price") is not None:
        # Merge price fields into existing cache (preserve fundamentals)
        existing_cache = company.get("fundamentals_cache") or {}
        existing_cache.update(price_data)

        supabase.table("companies").update({
            "fundamentals_cache": existing_cache,
            "cache_updated_at":   datetime.now(timezone.utc).isoformat()
        }).eq("id", company_id).execute()

        return existing_cache

    return company.get("fundamentals_cache") or {}


# ─── Force fundamentals refresh (manual only) ─────────────────────────────
@router.post("/{company_id}/refresh-fundamentals")
async def refresh_fundamentals(company_id: str):
    """
    Force-refresh all fundamentals from yfinance + NSE node.
    Ignores cache age — always fetches fresh data.
    Used only when user explicitly clicks 'Refresh Fundamentals'.
    """
    supabase = get_supabase()
    result = supabase.table("companies").select("ticker, exchange")\
        .eq("id", company_id).maybe_single().execute()

    if not result or getattr(result, "data", None) is None:
        raise HTTPException(status_code=404, detail="Company not found")

    company = result.data
    fundamentals = await asyncio.to_thread(fetch_fundamentals, company["ticker"], company.get("exchange", "NSE"))

    if fundamentals and fundamentals.get("current_price") is not None:
        supabase.table("companies").update({
            "fundamentals_cache": fundamentals,
            "cache_updated_at":   datetime.now(timezone.utc).isoformat()
        }).eq("id", company_id).execute()

    return fundamentals or {}


# ─── ADDENDUM B.4: Auto research endpoint ─────────────────────────────────
from pydantic import BaseModel
from typing import Optional

class AutoResearchReq(BaseModel):
    target_url: Optional[str] = None

@router.post("/{company_id}/auto-research")
async def auto_research(
    request: Request,
    company_id: str,
    req: AutoResearchReq = None,
    user_id: str = Depends(get_current_user_id)
):
    """
    Triggers the auto research agent for a company.
    user_id is derived from the verified JWT, not from client input.
    """
    supabase = get_supabase()
    company  = supabase.table("companies").select("name, ticker")\
        .eq("id", company_id).maybe_single().execute()

    if not company or getattr(company, "data", None) is None:
        raise HTTPException(status_code=404, detail="Company not found")

    target_url = req.target_url if req else None
    arq_pool = getattr(request.app.state, "arq_pool", None)

    result = await run_auto_research(
        company_id=company_id,
        company_name=company.data["name"],
        ticker=company.data["ticker"],
        user_id=user_id,
        target_url=target_url,
        arq_pool=arq_pool
    )
    return result
