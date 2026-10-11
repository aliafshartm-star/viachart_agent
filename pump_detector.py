"""
Pump Detector — تشخیص ارزهای آماده رشد
۵ نیرو:
  ۱. Volume Accumulation + Higher Lows
  ۲. Sector Rotation (سکتور داغ + laggard)
  ۳. News & Sentiment
  ۴. Short Squeeze (Funding Rate)
  ۵. Market Regime (BTC)
"""
import os
import logging
import time
from datetime import datetime, timezone

import requests
import numpy as np
import pandas as pd

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')
log = logging.getLogger(__name__)

BINANCE_API = "https://data-api.binance.vision/api/v3"
BINANCE_FUTURES = "https://fapi.binance.com/fapi/v1"
COINGECKO_API = "https://api.coingecko.com/api/v3"


def candles_to_df(candles):
    df = pd.DataFrame(candles)
    df["time"] = pd.to_datetime(df["time"], unit="ms", utc=True)
    df = df.set_index("time")
    return df


def ema(series, period):
    return series.ewm(span=period, adjust=False).mean()


def atr(df, period=14):
    h, l, c = df["high"], df["low"], df["close"]
    tr = pd.concat([
        h - l,
        (h - c.shift()).abs(),
        (l - c.shift()).abs(),
    ], axis=1).max(axis=1)
    return tr.rolling(period).mean()


def find_swing_lows(df, lookback=5):
    lows = []
    l = df["low"].values
    for i in range(lookback, len(df) - lookback):
        if l[i] == min(l[i - lookback:i + lookback + 1]):
            lows.append({"index": i, "price": l[i]})
    return lows


# ============================================================
# نیرو ۱: Volume Accumulation (0-20)
# ============================================================

def detect_volume_accumulation(df):
    score = 0
    reasons = []

    if len(df) < 60:
        return 0, reasons

    vol_7d = df["volume"].tail(42).mean()
    vol_30d = df["volume"].tail(180).mean()
    if vol_30d > 0:
        vol_ratio = vol_7d / vol_30d
        if vol_ratio > 1.5:
            score += 7
            reasons.append(f"حجم ۷ روزه {vol_ratio:.1f}x بیشتر از میانگین")
        elif vol_ratio > 1.2:
            score += 4
            reasons.append(f"حجم در حال افزایش ({vol_ratio:.1f}x)")

    swing_lows = find_swing_lows(df, lookback=5)
    if len(swing_lows) >= 3:
        last_3 = swing_lows[-3:]
        if last_3[0]["price"] < last_3[1]["price"] < last_3[2]["price"]:
            score += 8
            reasons.append("ساختار Higher Lows صعودی")

    recent_low = df["low"].tail(5).min()
    prev_low = df["low"].tail(30).head(25).min()
    if recent_low > prev_low * 1.01:
        score += 5
        reasons.append("کف‌های اخیر بالاتر از گذشته")

    return min(20, score), reasons


# ============================================================
# نیرو ۲: Sector Rotation (0-20)
# ============================================================

_sector_cache = {"data": None, "time": 0}


def get_sector_performance():
    now = time.time()
    if _sector_cache["data"] and (now - _sector_cache["time"]) < 3600:
        return _sector_cache["data"]

    try:
        url = f"{COINGECKO_API}/coins/categories"
        r = requests.get(url, timeout=15)
        if r.status_code != 200:
            return {}

        cats = r.json()
        result = {}
        for cat in cats[:40]:
            name = cat.get("name", "").lower()
            change = cat.get("market_cap_change_24h") or 0
            if name and change:
                try:
                    result[name] = float(change)
                except Exception:
                    pass

        _sector_cache["data"] = result
        _sector_cache["time"] = now
        return result
    except Exception as e:
        log.warning(f"خطا در سکتورها: {e}")
        return {}


def detect_sector_rotation(df, cg_id):
    score = 0
    reasons = []

    sectors = get_sector_performance()
    if not sectors or not cg_id:
        return 0, reasons

    hot_sectors = {k: v for k, v in sectors.items() if v > 5}
    if not hot_sectors:
        return 0, reasons

    coin_sectors = {
        "btc": ["bitcoin", "layer 1"],
        "eth": ["ethereum", "smart contract", "layer 1"],
        "sol": ["solana", "layer 1"],
        "bnb": ["bnb", "exchange"],
        "ada": ["cardano", "layer 1"],
        "avax": ["avalanche", "layer 1"],
        "dot": ["polkadot", "layer 1"],
        "matic": ["polygon", "layer 2"],
        "arb": ["arbitrum", "layer 2"],
        "op": ["optimism", "layer 2"],
        "link": ["chainlink", "oracle", "defi"],
        "uni": ["uniswap", "defi", "dex"],
        "aave": ["aave", "defi"],
        "doge": ["dogecoin", "meme"],
        "shib": ["shiba", "meme"],
        "pepe": ["pepe", "meme"],
        "wif": ["dogwifhat", "meme"],
        "inj": ["injective", "defi"],
        "near": ["near", "ai", "layer 1"],
        "fet": ["fetch", "ai"],
        "rndr": ["render", "ai"],
        "tao": ["bittensor", "ai"],
        "grt": ["graph", "ai", "infrastructure"],
        "atom": ["cosmos", "layer 1"],
        "xrp": ["ripple", "payments"],
        "ltc": ["litecoin", "payments"],
        "ton": ["toncoin", "layer 1"],
        "sui": ["sui", "layer 1"],
        "apt": ["aptos", "layer 1"],
        "sei": ["sei", "layer 1"],
        "tia": ["celestia", "modular"],
    }

    for sector_name, sector_change in hot_sectors.items():
        coin_sector_list = coin_sectors.get(cg_id, [])

        match = False
        for cs in coin_sector_list:
            if cs in sector_name or sector_name in cs:
                match = True
                break

        if cg_id in sector_name or sector_name in cg_id:
            match = True

        if match:
            coin_change = (df["close"].iloc[-1] / df["close"].iloc[-7]) - 1
            coin_change_pct = coin_change * 100
            gap = sector_change - coin_change_pct

            if gap > 10:
                score += 15
                reasons.append(f"سکتور داغ (+{sector_change:.0f}%) ولی کوین lag کرده")
            elif gap > 5:
                score += 10
                reasons.append(f"سکتور {sector_name} فعال (+{sector_change:.0f}%)")
            else:
                score += 5
            break

    return min(20, score), reasons


# ============================================================
# نیرو ۳: News & Sentiment (0-20)
# ============================================================

_news_cache = {"data": None, "time": 0}


def get_news():
    now = time.time()
    if _news_cache["data"] and (now - _news_cache["time"]) < 600:
        return _news_cache["data"]

    try:
        import xml.etree.ElementTree as ET
        url = "https://www.coindesk.com/arc/outboundfeeds/rss/"
        r = requests.get(url, timeout=15)
        r.raise_for_status()
        root = ET.fromstring(r.content)
        items = root.findall(".//item")[:20]
        news = [{"title": i.findtext("title", "")} for i in items]
        _news_cache["data"] = news
        _news_cache["time"] = now
        return news
    except Exception as e:
        log.warning(f"خطا در اخبار: {e}")
        return []


def detect_news_sentiment(symbol):
    score = 0
    reasons = []

    news = get_news()
    if not news:
        return 0, reasons

    coin = symbol.replace("USDT", "").upper()

    keywords = {
        "BTC": ["bitcoin", "btc"],
        "ETH": ["ethereum", "eth"],
        "SOL": ["solana", "sol"],
        "BNB": ["binance", "bnb"],
        "XRP": ["ripple", "xrp"],
    }

    name_map = {
        "ARB": ["arbitrum"], "OP": ["optimism"], "APT": ["aptos"],
        "INJ": ["injective"], "SUI": ["sui"], "SEI": ["sei"],
        "TIA": ["celestia"], "NEAR": ["near"], "AVAX": ["avalanche"],
        "DOT": ["polkadot"], "LINK": ["chainlink"], "MATIC": ["polygon"],
        "DOGE": ["dogecoin"], "ADA": ["cardano"],
    }

    search_terms = keywords.get(coin, [coin.lower()]) + name_map.get(coin, [])

    matches = 0
    for n in news:
        title_lower = n["title"].lower()
        if any(term in title_lower for term in search_terms):
            matches += 1

    if matches >= 3:
        score += 15
        reasons.append(f"اخبار داغ: {matches} خبر مرتبط")
    elif matches >= 1:
        score += 8
        reasons.append(f"خبر مرتبط: {matches} مورد")

    hot_words = ["etf", "listing", "partnership", "upgrade", "launch"]
    for n in news[:5]:
        title_lower = n["title"].lower()
        if any(w in title_lower for w in hot_words):
            score += 3
            break

    return min(20, score), reasons


# ============================================================
# نیرو ۴: Short Squeeze (0-20)
# ============================================================

def get_funding_rate(symbol):
    try:
        url = f"{BINANCE_FUTURES}/premiumIndex"
        r = requests.get(url, params={"symbol": symbol}, timeout=10)
        if r.status_code != 200:
            return None
        data = r.json()
        return float(data.get("lastFundingRate", 0))
    except Exception:
        return None


def detect_short_squeeze(symbol):
    score = 0
    reasons = []

    fr = get_funding_rate(symbol)
    if fr is None:
        return 0, reasons

    fr_pct = fr * 100

    if fr_pct < -0.05:
        score += 15
        reasons.append(f"Funding خیلی منفی ({fr_pct:.3f}%)")
    elif fr_pct < -0.01:
        score += 10
        reasons.append(f"Funding منفی ({fr_pct:.3f}%)")
    elif fr_pct < 0:
        score += 5

    return min(20, score), reasons


# ============================================================
# نیرو ۵: Market Regime (0-20)
# ============================================================

def get_btc_regime():
    try:
        url = f"{BINANCE_API}/ticker/24hr"
        r = requests.get(url, params={"symbol": "BTCUSDT"}, timeout=10)
        if r.status_code != 200:
            return {"change": 0, "price": 0}
        data = r.json()
        return {
            "change": float(data["priceChangePercent"]),
            "price": float(data["lastPrice"]),
        }
    except Exception:
        return {"change": 0, "price": 0}


def detect_market_regime():
    score = 0
    reasons = []

    btc = get_btc_regime()
    change = btc["change"]

    if change > 2:
        score += 10
        reasons.append(f"BTC مثبت ({change:+.1f}%)")
    elif change > -1:
        score += 8
        reasons.append(f"BTC پایدار ({change:+.1f}%)")
    elif change > -3:
        score += 4
    else:
        score -= 5
        reasons.append(f"BTC نزولی ({change:+.1f}%)")

    try:
        r = requests.get("https://api.alternative.me/fng/", timeout=10)
        data = r.json()
        fng = int(data["data"][0]["value"])
        if 25 <= fng <= 65:
            score += 8
            reasons.append(f"Fear & Greed: {fng} (تعادل)")
        elif fng < 25:
            score += 10
            reasons.append(f"Fear & Greed: {fng} (فرصت خرید)")
        elif fng > 80:
            score -= 5
    except Exception:
        pass

    return max(0, min(20, score)), reasons


# ============================================================
# تحلیل کامل
# ============================================================

def analyze_coin(symbol, cg_id, df, ticker_info):
    forces = {}
    all_reasons = []

    s1, r1 = detect_volume_accumulation(df)
    forces["volume_accumulation"] = s1
    all_reasons.extend(r1)

    s2, r2 = detect_sector_rotation(df, cg_id)
    forces["sector_rotation"] = s2
    all_reasons.extend(r2)

    s3, r3 = detect_news_sentiment(symbol)
    forces["news_sentiment"] = s3
    all_reasons.extend(r3)

    s4, r4 = detect_short_squeeze(symbol)
    forces["short_squeeze"] = s4
    all_reasons.extend(r4)

    s5, r5 = detect_market_regime()
    forces["market_regime"] = s5
    all_reasons.extend(r5)

    total = sum(forces.values())

    price = df["close"].iloc[-1]
    atr_val = atr(df).iloc[-1]

    # سطوح جدید (R:R بهتر)
    entry_low = price * 0.995
    entry_high = price * 1.005
    stop = price * 0.95           # -5%
    tp1 = price * 1.075           # +7.5%
    tp2 = price * 1.15            # +15%
    tp3 = price * 1.30            # +30%

    return {
        "symbol": symbol,
        "cg_id": cg_id,
        "price": float(price),
        "change_24h": ticker_info.get("change_24h", 0),
        "volume_24h": ticker_info.get("volume_24h", 0),
        "score": total,
        "forces": forces,
        "reasons": all_reasons,
        "entry_low": round(entry_low, 6),
        "entry_high": round(entry_high, 6),
        "stop": round(stop, 6),
        "tp1": round(tp1, 6),
        "tp2": round(tp2, 6),
        "tp3": round(tp3, 6),
        "atr": float(atr_val),
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


# ============================================================
# فیلترها
# ============================================================

def passes_filters(coin):
    if coin["volume_24h"] < 20_000_000:
        return False
    if coin["change_24h"] > 8:
        return False
    if coin["change_24h"] < -15:
        return False

    entry_mid = (coin["entry_low"] + coin["entry_high"]) / 2
    risk = (entry_mid - coin["stop"]) / entry_mid
    reward = (coin["tp1"] - entry_mid) / entry_mid
    if risk > 0 and (reward / risk) < 1.4:
        return False

    return True


def get_signal_tier(score):
    if score >= 70:
        return "TIER 1"
    elif score >= 55:
        return "TIER 2"
    elif score >= 40:
        return "TIER 3"
    return "NO SIGNAL"


# ============================================================
# تست
# ============================================================

if __name__ == "__main__":
    from data_fetcher import get_top_symbols, get_klines

    print("\n🧪 تست pump_detector...\n")

    symbols = get_top_symbols(limit=10)
    print(f"دریافت {len(symbols)} ارز\n")

    results = []
    for i, s in enumerate(symbols[:5], 1):
        sym = s["symbol"]
        print(f"[{i}] تحلیل {sym}...")

        candles = get_klines(sym, "4h", 200)
        if not candles:
            continue

        df = candles_to_df(candles)
        cg_id = sym.replace("USDT", "").lower()

        analysis = analyze_coin(sym, cg_id, df, s)
        if passes_filters(analysis):
            results.append(analysis)
            print(f"   ✅ امتیاز: {analysis['score']}/100 — {get_signal_tier(analysis['score'])}")
            for r in analysis["reasons"]:
                print(f"      • {r}")
        else:
            print(f"   ❌ رد شد (امتیاز: {analysis['score']})")

        time.sleep(0.5)

    print(f"\n📊 {len(results)} ارز از فیلترها گذشت")