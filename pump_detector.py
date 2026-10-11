"""
Pump Detector v2 — تشخیص ارزهای آماده رشد
۵ نیروی بازسازی‌شده:
  ۱. Volume Accumulation (0-20)
  ۲. Trend Strength / RS vs BTC (0-20)
  ۳. News + Trending (0-20)
  ۴. Momentum & Squeeze (0-20)
  ۵. Market Regime (0-20)
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


# ============================================================
# ابزارها
# ============================================================

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
# کش‌ها
# ============================================================

_cache = {
    "sectors": {"data": None, "time": 0},
    "news": {"data": None, "time": 0},
    "trending": {"data": None, "time": 0},
    "btc": {"data": None, "time": 0},
    "fng": {"data": None, "time": 0},
}


# ============================================================
# نیرو ۱: Volume Accumulation (0-20)
# ============================================================

def detect_volume_accumulation(df):
    score = 0
    reasons = []

    if len(df) < 60:
        return 0, reasons

    # Relative Volume
    vol_7d = df["volume"].tail(42).mean()
    vol_30d = df["volume"].tail(180).mean()
    if vol_30d > 0:
        vol_ratio = vol_7d / vol_30d
        if vol_ratio > 1.5:
            score += 8
            reasons.append(f"حجم ۷ روزه {vol_ratio:.1f}x میانگین")
        elif vol_ratio > 1.2:
            score += 5
            reasons.append(f"حجم در حال افزایش ({vol_ratio:.1f}x)")
        elif vol_ratio > 1.0:
            score += 3

    # Higher Lows
    swing_lows = find_swing_lows(df, lookback=5)
    if len(swing_lows) >= 3:
        last_3 = swing_lows[-3:]
        if last_3[0]["price"] < last_3[1]["price"] < last_3[2]["price"]:
            score += 7
            reasons.append("Higher Lows صعودی")

    # کف‌های بالاتر
    recent_low = df["low"].tail(5).min()
    prev_low = df["low"].tail(30).head(25).min()
    if prev_low > 0 and recent_low > prev_low * 1.01:
        score += 5
        reasons.append("کف‌ها بالاتر از قبل")

    return min(20, score), reasons


# ============================================================
# نیرو ۲: Trend Strength / RS vs BTC (0-20)
# ============================================================

def detect_trend_strength(df, symbol, btc_df=None):
    """
    روند صعودی + قوی‌تر از BTC
    """
    score = 0
    reasons = []

    if len(df) < 60:
        return 0, reasons

    price = df["close"].iloc[-1]
    e20 = ema(df["close"], 20).iloc[-1]
    e50 = ema(df["close"], 50).iloc[-1]

    # روند EMA
    if price > e20 > e50:
        score += 8
        reasons.append("روند صعودی (EMA20 > EMA50)")
    elif price > e20:
        score += 4
        reasons.append("قیمت بالای EMA20")

    # Momentum 7 روزه
    if len(df) >= 42:
        change_7d = (df["close"].iloc[-1] / df["close"].iloc[-42]) - 1
        if change_7d > 0.10:
            score += 6
            reasons.append(f"رشد ۷ روزه +{change_7d*100:.1f}%")
        elif change_7d > 0.03:
            score += 4
            reasons.append(f"رشد ۷ روزه +{change_7d*100:.1f}%")
        elif change_7d > 0:
            score += 2

    # RS vs BTC (اگه BTC دیتا موجوده)
    if btc_df is not None and len(btc_df) >= 42:
        try:
            btc_change = (btc_df["close"].iloc[-1] / btc_df["close"].iloc[-42]) - 1
            coin_change = (df["close"].iloc[-1] / df["close"].iloc[-42]) - 1
            rs = coin_change - btc_change
            if rs > 0.05:
                score += 6
                reasons.append(f"RS vs BTC: +{rs*100:.1f}%")
            elif rs > 0.02:
                score += 3
        except Exception:
            pass

    return min(20, score), reasons


# ============================================================
# نیرو ۳: News + Trending (0-20)
# ============================================================

def get_trending_coins():
    """کوین‌های ترند CoinGecko"""
    now = time.time()
    if _cache["trending"]["data"] and (now - _cache["trending"]["time"]) < 1800:
        return _cache["trending"]["data"]

    try:
        r = requests.get(f"{COINGECKO_API}/search/trending", timeout=10)
        if r.status_code != 200:
            return []
        data = r.json()
        result = [c["item"]["symbol"].upper() for c in data.get("coins", [])]
        _cache["trending"]["data"] = result
        _cache["trending"]["time"] = now
        return result
    except Exception:
        return []


def get_news():
    now = time.time()
    if _cache["news"]["data"] and (now - _cache["news"]["time"]) < 600:
        return _cache["news"]["data"]

    try:
        import xml.etree.ElementTree as ET
        url = "https://www.coindesk.com/arc/outboundfeeds/rss/"
        r = requests.get(url, timeout=15)
        r.raise_for_status()
        root = ET.fromstring(r.content)
        items = root.findall(".//item")[:20]
        news = [{"title": i.findtext("title", "")} for i in items]
        _cache["news"]["data"] = news
        _cache["news"]["time"] = now
        return news
    except Exception:
        return []


def detect_news_sentiment(symbol):
    """ترند + خبر"""
    score = 0
    reasons = []

    coin = symbol.replace("USDT", "").upper()

    # Trending
    trending = get_trending_coins()
    if coin in trending:
        score += 12
        reasons.append("ترند CoinGecko 🔥")

    # خبر
    news = get_news()
    if news:
        matches = 0
        name_map = {
            "BTC": "bitcoin", "ETH": "ethereum", "SOL": "solana",
            "BNB": "binance", "XRP": "ripple", "ADA": "cardano",
            "DOGE": "dogecoin", "AVAX": "avalanche", "DOT": "polkadot",
            "LINK": "chainlink", "MATIC": "polygon", "ARB": "arbitrum",
            "OP": "optimism", "APT": "aptos", "INJ": "injective",
            "SUI": "sui", "SEI": "sei", "TIA": "celestia",
        }
        search_terms = [coin.lower(), name_map.get(coin, "").lower()]
        search_terms = [t for t in search_terms if t]

        for n in news:
            title_lower = n["title"].lower()
            if any(t in title_lower for t in search_terms):
                matches += 1

        if matches >= 2:
            score += 8
            reasons.append(f"خبر مرتبط ({matches} مورد)")

    return min(20, score), reasons


# ============================================================
# نیرو ۴: Momentum & Squeeze (0-20)
# ============================================================

def get_funding_rate(symbol):
    try:
        url = f"{BINANCE_FUTURES}/premiumIndex"
        r = requests.get(url, params={"symbol": symbol}, timeout=8)
        if r.status_code != 200:
            return None
        data = r.json()
        return float(data.get("lastFundingRate", 0))
    except Exception:
        return None


def detect_momentum_squeeze(df, symbol):
    """Funding + RSI + نزدیکی به مقاومت"""
    score = 0
    reasons = []

    # Funding Rate (5 امتیاز پایه)
    fr = get_funding_rate(symbol)
    if fr is not None:
        fr_pct = fr * 100
        if fr_pct < -0.03:
            score += 8
            reasons.append(f"Funding منفی ({fr_pct:.3f}%)")
        elif fr_pct < -0.01:
            score += 5
            reasons.append(f"Funding کم ({fr_pct:.3f}%)")
        else:
            score += 3
    else:
        score += 3

    # RSI (5 امتیاز)
    if len(df) >= 15:
        delta = df["close"].diff()
        gain = delta.where(delta > 0, 0).rolling(14).mean()
        loss = -delta.where(delta < 0, 0).rolling(14).mean()
        rs = gain / loss.replace(0, np.nan)
        rsi = 100 - (100 / (1 + rs))
        rsi_val = rsi.iloc[-1]

        if 40 <= rsi_val <= 60:
            score += 5
            reasons.append(f"RSI متعادل ({rsi_val:.0f})")
        elif 30 <= rsi_val < 40:
            score += 7
            reasons.append(f"RSI پایین — فرصت ({rsi_val:.0f})")

    # نزدیکی به مقاومت (5 امتیاز)
    if len(df) >= 20:
        recent_high = df["high"].tail(20).max()
        price = df["close"].iloc[-1]
        dist_to_high = (recent_high - price) / price

        if dist_to_high < 0.02:
            score += 5
            reasons.append("نزدیک مقاومت — آماده شکست")

    return min(20, score), reasons


# ============================================================
# نیرو ۵: Market Regime (0-20)
# ============================================================

def get_btc_regime():
    now = time.time()
    if _cache["btc"]["data"] and (now - _cache["btc"]["time"]) < 300:
        return _cache["btc"]["data"]

    try:
        url = f"{BINANCE_API}/ticker/24hr"
        r = requests.get(url, params={"symbol": "BTCUSDT"}, timeout=10)
        if r.status_code != 200:
            return {"change": 0, "price": 0}
        data = r.json()
        result = {
            "change": float(data["priceChangePercent"]),
            "price": float(data["lastPrice"]),
        }
        _cache["btc"]["data"] = result
        _cache["btc"]["time"] = now
        return result
    except Exception:
        return {"change": 0, "price": 0}


def get_fng():
    now = time.time()
    if _cache["fng"]["data"] and (now - _cache["fng"]["time"]) < 1800:
        return _cache["fng"]["data"]

    try:
        r = requests.get("https://api.alternative.me/fng/", timeout=10)
        data = r.json()
        result = int(data["data"][0]["value"])
        _cache["fng"]["data"] = result
        _cache["fng"]["time"] = now
        return result
    except Exception:
        return 50


def detect_market_regime():
    score = 0
    reasons = []

    btc = get_btc_regime()
    change = btc["change"]

    if change > 1:
        score += 8
        reasons.append(f"BTC مثبت ({change:+.1f}%)")
    elif change > -1:
        score += 6
        reasons.append(f"BTC پایدار ({change:+.1f}%)")
    elif change > -3:
        score += 3
    else:
        score -= 5
        reasons.append(f"BTC نزولی ({change:+.1f}%)")

    fng = get_fng()
    if 25 <= fng <= 65:
        score += 7
        reasons.append(f"Fear & Greed: {fng}")
    elif fng < 25:
        score += 10
        reasons.append(f"Fear & Greed: {fng} (فرصت)")
    elif fng > 80:
        score -= 3
    else:
        score += 4

    return max(0, min(20, score)), reasons


# ============================================================
# تحلیل کامل
# ============================================================

def analyze_coin(symbol, cg_id, df, ticker_info, btc_df=None):
    forces = {}
    all_reasons = []

    s1, r1 = detect_volume_accumulation(df)
    forces["volume"] = s1
    all_reasons.extend(r1)

    s2, r2 = detect_trend_strength(df, symbol, btc_df)
    forces["trend"] = s2
    all_reasons.extend(r2)

    s3, r3 = detect_news_sentiment(symbol)
    forces["news"] = s3
    all_reasons.extend(r3)

    s4, r4 = detect_momentum_squeeze(df, symbol)
    forces["momentum"] = s4
    all_reasons.extend(r4)

    s5, r5 = detect_market_regime()
    forces["regime"] = s5
    all_reasons.extend(r5)

    total = sum(forces.values())

    price = df["close"].iloc[-1]
    atr_val = atr(df).iloc[-1]

    entry_low = price * 0.995
    entry_high = price * 1.005
    stop = price * 0.95
    tp1 = price * 1.075
    tp2 = price * 1.15
    tp3 = price * 1.30

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
    if coin["volume_24h"] < 15_000_000:
        return False
    if coin["change_24h"] > 10:
        return False
    if coin["change_24h"] < -15:
        return False

    entry_mid = (coin["entry_low"] + coin["entry_high"]) / 2
    risk = (entry_mid - coin["stop"]) / entry_mid
    reward = (coin["tp1"] - entry_mid) / entry_mid
    if risk > 0 and (reward / risk) < 1.3:
        return False

    return True


def get_signal_tier(score):
    if score >= 65:
        return "TIER 1"
    elif score >= 50:
        return "TIER 2"
    elif score >= 40:
        return "TIER 3"
    return "NO SIGNAL"


# ============================================================
# تست
# ============================================================

if __name__ == "__main__":
    from data_fetcher import get_top_symbols, get_klines

    print("\n🧪 تست pump_detector v2...\n")

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
            print(f"      Forces: {analysis['forces']}")
        else:
            print(f"   ❌ رد شد (امتیاز: {analysis['score']})")

        time.sleep(0.5)

    print(f"\n📊 {len(results)} ارز از فیلترها گذشت")