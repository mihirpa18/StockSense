import requests
import yfinance as yf
import time
from typing import Dict, Optional

# The Node.js microservice runs locally on port 3000
MARKET_SERVICE_URL = "http://localhost:3000"

# yfinance retry config
YF_MAX_RETRIES = 2
YF_BACKOFF_SECONDS = [5, 10]  # wait 5s after 1st fail, 10s after 2nd

def get_nse_symbol(ticker: str) -> str:
    """Clean the ticker by removing .NS or .BO for the NSE service."""
    return ticker.replace(".NS", "").replace(".BO", "")

def get_yf_symbol(ticker: str, exchange: str = "NSE") -> str:
    """Convert ticker to Yahoo Finance format based on exchange."""
    base = get_nse_symbol(ticker)
    if exchange == "NSE":
        return f"{base}.NS"
    elif exchange == "BSE":
        return f"{base}.BO"
    return base

def _fetch_yf_info(ticker: str, exchange: str = "NSE") -> Dict:
    """
    Fetch yfinance .info with retry on 429 Too Many Requests.
    Returns the info dict or empty dict if all retries fail.
    """
    yf_symbol = get_yf_symbol(ticker, exchange)
    
    for attempt in range(YF_MAX_RETRIES + 1):
        try:
            stock = yf.Ticker(yf_symbol)
            info = stock.info
            # yfinance returns {'trailingPegRatio': None} on 429 sometimes
            if info and len(info) > 5:
                return info
            else:
                print(f"yfinance returned sparse data for {yf_symbol}, attempt {attempt + 1}")
        except Exception as e:
            err_str = str(e)
            if "429" in err_str or "Too Many Requests" in err_str:
                if attempt < YF_MAX_RETRIES:
                    wait = YF_BACKOFF_SECONDS[attempt]
                    print(f"yfinance 429 for {yf_symbol}, retrying in {wait}s (attempt {attempt + 1}/{YF_MAX_RETRIES + 1})")
                    time.sleep(wait)
                    continue
                else:
                    print(f"yfinance 429 for {yf_symbol}, all retries exhausted")
                    return {}
            else:
                print(f"yfinance error for {yf_symbol}: {e}")
                return {}
    
    return {}

def fetch_fundamentals(ticker: str, exchange: str = "NSE") -> Dict:
    """
    Fetches key details for a given ticker. 
    Combines live price from the microservice with fundamentals from yfinance.
    yfinance calls use retry-with-backoff to handle 429 rate limits.
    """
    result = {}
    
    # 1. Fetch live price/sector data from our NSE microservice
    try:
        if exchange in ["NSE", "BSE"]:
            symbol = get_nse_symbol(ticker)
            response = requests.get(f"{MARKET_SERVICE_URL}/quote/{symbol}", timeout=10)
            if response.status_code == 200:
                data = response.json()
                price_info = data.get("priceInfo", {})
                industry_info = data.get("industryInfo", {})
                week_high_low = price_info.get("weekHighLow", {})
                
                result.update({
                    "current_price":      price_info.get("lastPrice"),
                    "previous_close":     price_info.get("previousClose"),
                    "open":               price_info.get("open"),
                    "pChange":            price_info.get("pChange"),
                    "fifty_two_week_high": week_high_low.get("max"),
                    "fifty_two_week_low":  week_high_low.get("min"),
                    "description":        data.get("info", {}).get("companyName"),
                    "sector":             industry_info.get("sector"),
                    "industry":           industry_info.get("industry"),
                })
    except Exception as e:
        print(f"Market service error for {ticker}: {e}")

    # 2. Fetch deep fundamentals from yfinance (with retry on 429)
    info = _fetch_yf_info(ticker, exchange)
    
    if info:
        # Merge yfinance fundamentals into the result
        # (We use dict.setdefault so we don't overwrite the live prices if they exist)
        result.setdefault("current_price", info.get("currentPrice"))
        result.setdefault("previous_close", info.get("previousClose"))
        result.setdefault("open", info.get("open"))
        result.setdefault("fifty_two_week_high", info.get("fiftyTwoWeekHigh"))
        result.setdefault("fifty_two_week_low", info.get("fiftyTwoWeekLow"))
        result.setdefault("sector", info.get("sector"))
        result.setdefault("industry", info.get("industry"))
        result.setdefault("description", info.get("longBusinessSummary"))
        
        # Calculate pChange if missing
        if result.get("current_price") and result.get("previous_close"):
            change = result["current_price"] - result["previous_close"]
            result.setdefault("pChange", round((change / result["previous_close"]) * 100, 2))
        else:
            result.setdefault("pChange", 0)
        
        # Add the fundamentals that NSE doesn't provide
        result.update({
            "market_cap":         info.get("marketCap"),
            "pe_ratio":           info.get("trailingPE"),
            "forward_pe":         info.get("forwardPE"),
            "roe":                info.get("returnOnEquity"),
            "debt_to_equity":     info.get("debtToEquity"),
            "profit_margin":      info.get("profitMargins"),
            "revenue_growth":     info.get("revenueGrowth"),
            "earnings_growth":    info.get("earningsGrowth"),
        })
    else:
        # yfinance completely failed — ensure keys exist so frontend doesn't crash
        for key in ["market_cap", "pe_ratio", "forward_pe", "roe", "debt_to_equity", "profit_margin", "revenue_growth", "earnings_growth"]:
            result.setdefault(key, None)

    return result

def fetch_price_only(ticker: str, exchange: str = "NSE") -> Dict:
    """
    Lightweight price-only fetch — hits NSE node service ONLY.
    Never calls yfinance. Returns current_price, previous_close, open, pChange.
    If node service is down, returns empty dict (frontend shows cached data).
    """
    result = {}

    try:
        if exchange in ["NSE", "BSE"]:
            symbol = get_nse_symbol(ticker)
            response = requests.get(f"{MARKET_SERVICE_URL}/quote/{symbol}", timeout=10)
            if response.status_code == 200:
                data = response.json()
                price_info = data.get("priceInfo", {})
                result = {
                    "current_price":  price_info.get("lastPrice"),
                    "previous_close": price_info.get("previousClose"),
                    "open":           price_info.get("open"),
                    "pChange":        price_info.get("pChange"),
                }
    except Exception as e:
        print(f"Price fetch error for {ticker}: {e}")

    return result
