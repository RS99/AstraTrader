from polygon import RESTClient
from dotenv import load_dotenv
import os
from datetime import datetime, timezone
import random
from database import write_market, read_market
from functools import lru_cache
import yfinance as yf
import re

load_dotenv(override=True)

polygon_api_key = os.getenv("POLYGON_API_KEY")
polygon_plan = os.getenv("POLYGON_PLAN")

is_paid_polygon = polygon_plan == "paid"
is_realtime_polygon = polygon_plan == "realtime"


def normalize_symbol(symbol: str) -> str:
    """
    Normalize user-entered tickers to canonical forms used by data sources.

    Examples:
      "L&T.NS"  -> "LT.NS"
      "lt.ns"   -> "LT.NS"
      "NSE:LT"  -> "LT.NS"
      "NSE/RELIANCE" -> "RELIANCE.NS"
      "reliance" -> "RELIANCE"
      "BSE:500325" -> "500325.BO"  (note: BSE support not implemented later)
    """
    if not symbol or not isinstance(symbol, str):
        return symbol

    s = symbol.strip()

    # handle common prefixes like "NSE:" or "BSE:" or "nse/"
    s = re.sub(r'^(NSE[:/])', '', s, flags=re.IGNORECASE)
    s = re.sub(r'^(BSE[:/])', '', s, flags=re.IGNORECASE)

    # replace common separators with nothing
    s = s.replace(' ', '').replace('-', '').replace('/', '').replace('\\', '')

    # remove ampersands and other punctuation that break tickers (L&T -> LT)
    s = re.sub(r'[&@#\(\)\[\]\']', '', s)

    # Some tickers may include a '.' already (e.g., .NS). Keep that part.
    # Upper-case the ticker part before any suffix
    if '.' in s:
        parts = s.split('.')
        main = parts[0].upper()
        suffix = '.'.join(parts[1:]).upper()
        s = f"{main}.{suffix}"
    else:
        s = s.upper()

    # Common convenience: if user gave a plain NSE name and it's not numeric, attach .NS
    if not re.search(r'\.(NS|BO|BSE|OE|NC|MX|US)$', s, flags=re.IGNORECASE):
        # If the symbol contains letters and looks like an Indian equity name, treat as NSE by default
        if re.search(r'[A-Z]', s) and not re.search(r'\d', s):
            # or if the environment variable suggests India focus. To be helpful by default, append .NS
            # only if it contains more than 3 letters (many US tickers are 1-4 letters).
            if len(s) > 4:
                s = f"{s}.NS"

    return s


# -----------------------------
# Market Status (Polygon Only)
# -----------------------------
def is_market_open() -> bool:
    if not polygon_api_key:
        return True  # Assume open if polygon not used
    try:
        client = RESTClient(polygon_api_key)
        market_status = client.get_market_status()
        return market_status.market == "open"
    except Exception:
        return True


# -----------------------------
#  Yahoo Finance Support (For India NSE)
# -----------------------------
def get_share_price_yahoo(symbol) -> float:
    """Fetch price using Yahoo Finance if ticker ends with .NS or non-US."""
    try:
        ticker = yf.Ticker(symbol)
        data = ticker.history(period="1d")
        if data.empty:
            # Try a slightly longer range for tickers that might have holidays
            data = ticker.history(period="5d")
            if data.empty:
                raise Exception("No Yahoo Finance data")
        return float(data["Close"].iloc[-1])
    except Exception as e:
        print(f"Yahoo error for {symbol}: {e}")
        return 0.0


# -----------------------------
# Polygon End-of-Day
# -----------------------------
def get_all_share_prices_polygon_eod() -> dict[str, float]:
    client = RESTClient(polygon_api_key)
    probe = client.get_previous_close_agg("SPY")[0]
    last_close = datetime.fromtimestamp(probe.timestamp / 1000, tz=timezone.utc).date()

    results = client.get_grouped_daily_aggs(last_close, adjusted=True, include_otc=False)
    return {result.ticker: result.close for result in results}


@lru_cache(maxsize=2)
def get_market_for_prior_date(today):
    market_data = read_market(today)
    if not market_data:
        market_data = get_all_share_prices_polygon_eod()
        write_market(today, market_data)
    return market_data


def get_share_price_polygon_eod(symbol) -> float:
    today = datetime.now().date().strftime("%Y-%m-%d")
    market_data = get_market_for_prior_date(today)
    return market_data.get(symbol, 0.0)


# -----------------------------
# Polygon Minute-Level (15 min delayed)
# -----------------------------
def get_share_price_polygon_min(symbol) -> float:
    client = RESTClient(polygon_api_key)
    result = client.get_snapshot_ticker("stocks", symbol)
    # result.min or result.last_trade may be None; handle gracefully
    try:
        return float(result.min.close or result.prev_day.close or 0.0)
    except Exception:
        return 0.0


def get_share_price_polygon(symbol) -> float:
    try:
        if is_paid_polygon:
            return get_share_price_polygon_min(symbol)
        else:
            return get_share_price_polygon_eod(symbol)
    except Exception as e:
        print(f"Polygon error for {symbol}: {e}")
        return 0.0


# -----------------------------
# MASTER PRICE FUNCTION
# -----------------------------
def get_share_price(symbol) -> float:
    """
    MAIN PRICE FUNCTION:
    • Normalize symbol first (normalize_symbol)
    • If ticker ends with .NS → use Yahoo Finance (India/NSE)
    • Else use Polygon (US)
    • If all fail → return 0.0 (no random numbers)
    """
    if not symbol:
        return 0.0

    try:
        symbol = normalize_symbol(symbol)
    except Exception:
        # If normalization fails, continue with original symbol
        symbol = symbol

    # --- India NSE symbols ---
    if isinstance(symbol, str) and symbol.endswith(".NS"):
        price = get_share_price_yahoo(symbol)
        if price > 0:
            return price
        return 0.0

    # --- US Stocks via Polygon ---
    if polygon_api_key:
        price = get_share_price_polygon(symbol)
        if price > 0:
            return price

    # Final fallback (no random numbers, but keep a deterministic random for dev if absolutely needed)
    return 0.0
