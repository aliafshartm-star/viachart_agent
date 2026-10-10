"""
تحلیل تکنیکال با استراتژی‌های:
- AMD (Accumulation → Manipulation → Distribution)
- Liquidity Sweeps
- Liquidity Sessions (Asia/London/NY)
- Volume Profile (POC, VAH, VAL)
- Support/Resistance خودکار
- اندیکاتورهای RSI, MACD, EMA, ATR
"""
import logging
from datetime import datetime, timezone

import numpy as np
import pandas as pd

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')
log = logging.getLogger(__name__)


# ============================================================
# ابزارهای پایه
# ============================================================

def candles_to_df(candles):
    """تبدیل لیست کندل به DataFrame"""
    df = pd.DataFrame(candles)
    df["time"] = pd.to_datetime(df["time"], unit="ms", utc=True)
    df = df.set_index("time")
    return df


# ============================================================
# اندیکاتورهای کلاسیک
# ============================================================

def rsi(series, period=14):
    delta = series.diff()
    gain = delta.where(delta > 0, 0).rolling(period).mean()
    loss = -delta.where(delta < 0, 0).rolling(period).mean()
    rs = gain / loss.replace(0, np.nan)
    return 100 - (100 / (1 + rs))


def ema(series, period):
    return series.ewm(span=period, adjust=False).mean()


def macd(series, fast=12, slow=26, signal=9):
    ema_fast = ema(series, fast)
    ema_slow = ema(series, slow)
    macd_line = ema_fast - ema_slow
    signal_line = ema(macd_line, signal)
    histogram = macd_line - signal_line
    return macd_line, signal_line, histogram


def atr(df, period=14):
    high, low, close = df["high"], df["low"], df["close"]
    tr = pd.concat([
        high - low,
        (high - close.shift()).abs(),
        (low - close.shift()).abs(),
    ], axis=1).max(axis=1)
    return tr.rolling(period).mean()


# ============================================================
# تشخیص سطوح (Swing Highs / Lows)
# ============================================================

def find_swing_points(df, lookback=5):
    """تشخیص سقف و کف‌های محلی (swing)"""
    highs, lows = [], []
    h, l = df["high"].values, df["low"].values

    for i in range(lookback, len(df) - lookback):
        if h[i] == max(h[i - lookback:i + lookback + 1]):
            highs.append({"index": i, "price": h[i], "time": df.index[i]})
        if l[i] == min(l[i - lookback:i + lookback + 1]):
            lows.append({"index": i, "price": l[i], "time": df.index[i]})
    return highs, lows


def key_levels(df, n_recent=3):
    """سطوح کلیدی حمایت و مقاومت"""
    highs, lows = find_swing_points(df)
    resistances = sorted([h["price"] for h in highs[-n_recent * 3:]], reverse=True)
    supports = sorted([l["price"] for l in lows[-n_recent * 3:]])

    # حذف سطوح نزدیک به هم
    def dedupe(levels, threshold=0.005):
        result = []
        for lv in levels:
            if not result or abs(lv - result[-1]) / result[-1] > threshold:
                result.append(lv)
        return result

    return {
        "resistances": dedupe(resistances)[:n_recent],
        "supports": dedupe(supports)[::-1][:n_recent],
    }


# ============================================================
# Volume Profile
# ============================================================

def volume_profile(df, bins=50):
    """
    Volume Profile:
    - POC (Point of Control): قیمتی که بیشترین حجم رو داره
    - VAH / VAL: مرزهای Value Area (70% حجم)
    """
    price_min, price_max = df["low"].min(), df["high"].max()
    if price_max == price_min:
        return {"poc": price_min, "vah": price_max, "val": price_min, "levels": []}

    edges = np.linspace(price_min, price_max, bins + 1)
    vol_by_bin = np.zeros(bins)

    for _, row in df.iterrows():
        # حجم بین کندل‌ها بر اساس هم‌پوشانی قیمت تقسیم میشه
        for i in range(bins):
            low_edge, high_edge = edges[i], edges[i + 1]
            overlap_low = max(row["low"], low_edge)
            overlap_high = min(row["high"], high_edge)
            if overlap_high > overlap_low:
                candle_range = row["high"] - row["low"] or 1e-9
                vol_by_bin[i] += row["volume"] * (overlap_high - overlap_low) / candle_range

    poc_idx = int(np.argmax(vol_by_bin))
    poc_price = (edges[poc_idx] + edges[poc_idx + 1]) / 2

    # Value Area (70% حجم)
    total_vol = vol_by_bin.sum()
    target = total_vol * 0.70
    sorted_idx = np.argsort(vol_by_bin)[::-1]
    selected, cum = [], 0
    for i in sorted_idx:
        selected.append(i)
        cum += vol_by_bin[i]
        if cum >= target:
            break

    val_price = edges[min(selected)]
    vah_price = edges[max(selected) + 1]

    return {
        "poc": round(poc_price, 6),
        "vah": round(vah_price, 6),
        "val": round(val_price, 6),
    }


# ============================================================
# Liquidity Sweeps
# ============================================================

def detect_liquidity_sweeps(df, lookback=20):
    """
    تشخیص جارو شدن نقدینگی:
    کندلی که سقف/کف قبلی رو می‌شکنه ولی داخل رنج برمی‌گرده
    """
    recent_high = df["high"].rolling(lookback).max().shift(1)
    recent_low = df["low"].rolling(lookback).min().shift(1)

    sweeps = []
    for i in range(lookback, len(df)):
        row = df.iloc[i]
        # Bearish sweep (جاروی سقف، برگشت به پایین)
        if row["high"] > recent_high.iloc[i] and row["close"] < recent_high.iloc[i]:
            sweeps.append({
                "type": "bearish_sweep",
                "time": df.index[i].isoformat(),
                "level": float(recent_high.iloc[i]),
                "close": float(row["close"]),
            })
        # Bullish sweep (جاروی کف، برگشت به بالا)
        elif row["low"] < recent_low.iloc[i] and row["close"] > recent_low.iloc[i]:
            sweeps.append({
                "type": "bullish_sweep",
                "time": df.index[i].isoformat(),
                "level": float(recent_low.iloc[i]),
                "close": float(row["close"]),
            })

    return sweeps[-5:]  # ۵ تای آخر


# ============================================================
# سشن‌های نقدینگی
# ============================================================

def session_liquidity(df):
    """
    سطوح High/Low سشن‌های Asia, London, NY در ۲۴ ساعت اخیر
    """
    now = datetime.now(timezone.utc)
    day_ago = now - pd.Timedelta(hours=24)
    df_24 = df[df.index >= day_ago]

    def _range(start_utc, end_utc):
        mask = (df_24.index.hour >= start_utc) & (df_24.index.hour < end_utc)
        sub = df_24[mask]
        if sub.empty:
            return None
        return {"high": float(sub["high"].max()), "low": float(sub["low"].min())}

    return {
        "asia": _range(0, 8),      # 00:00 - 08:00 UTC
        "london": _range(7, 16),   # 07:00 - 16:00 UTC
        "ny": _range(12, 21),      # 12:00 - 21:00 UTC
    }


# ============================================================
# AMD (Accumulation → Manipulation → Distribution)
# ============================================================

def detect_amd_phase(df, window=30):
    """
    تشخیص فاز AMD:
    - Accumulation: نوسان کم، کندل‌های کوچک
    - Manipulation: شکست ناگهانی + جارو
    - Distribution: حرکت روندی پس از جارو
    """
    if len(df) < window + 5:
        return {"phase": "unknown", "reason": "کندل کافی نیست"}

    recent = df.tail(window)
    range_size = recent["high"].max() - recent["low"].min()
    avg_candle = (recent["high"] - recent["low"]).mean()
    volatility_ratio = avg_candle / range_size if range_size else 0

    # Accumulation: نوسان پایین
    if volatility_ratio < 0.15:
        return {
            "phase": "accumulation",
            "reason": "نوسان کم و رنج فشرده — احتمال آماده‌شدن برای حرکت",
        }

    # جستجوی Manipulation در ۱۰ کندل آخر
    sweeps = detect_liquidity_sweeps(df, lookback=20)
    if sweeps:
        last_sweep = sweeps[-1]
        sweep_idx = df.index.get_loc(pd.Timestamp(last_sweep["time"]))
        candles_since = len(df) - sweep_idx - 1

        if candles_since <= 5:
            return {
                "phase": "manipulation",
                "reason": f"جاروی نقدینگی {candles_since} کندل پیش — احتمال شروع Distribution",
                "sweep": last_sweep,
            }
        elif candles_since <= 15:
            direction = "bullish" if last_sweep["type"] == "bullish_sweep" else "bearish"
            return {
                "phase": "distribution",
                "reason": f"حرکت {direction} پس از جاروی {candles_since} کندل پیش",
                "sweep": last_sweep,
            }

    return {"phase": "ranging", "reason": "فاز مشخصی تشخیص داده نشد"}


# ============================================================
# امتیازدهی نهایی
# ============================================================

def score_coin(df, symbol, price_info):
    """
    امتیاز 0-100 به هر ارز بر اساس ترکیب همه استراتژی‌ها
    """
    if len(df) < 60:
        return {"symbol": symbol, "score": 0, "reason": "کندل کافی نیست"}

    score = 0
    reasons = []

    # --- RSI ---
    rsi_val = rsi(df["close"]).iloc[-1]
    if rsi_val < 30:
        score += 15
        reasons.append(f"RSI اشباع فروش ({rsi_val:.1f})")
    elif rsi_val < 45:
        score += 8
        reasons.append(f"RSI پایین ({rsi_val:.1f})")
    elif rsi_val > 70:
        score -= 5

    # --- MACD ---
    _, _, hist = macd(df["close"])
    if hist.iloc[-1] > 0 and hist.iloc[-2] < 0:
        score += 15
        reasons.append("MACD کراس صعودی")
    elif hist.iloc[-1] > 0:
        score += 5

    # --- روند EMA ---
    e20 = ema(df["close"], 20).iloc[-1]
    e50 = ema(df["close"], 50).iloc[-1]
    price = df["close"].iloc[-1]
    if price > e20 > e50:
        score += 10
        reasons.append("روند صعودی (EMA)")
    elif price < e20 < e50:
        score -= 5

    # --- Volume Profile ---
    vp = volume_profile(df)
    if price > vp["vah"]:
        score += 12
        reasons.append(f"عبور از VAH ({vp['vah']})")
    elif vp["val"] <= price <= vp["vah"]:
        score += 3
    elif price < vp["val"]:
        score += 5  # پتانسیل بازگشت به POC

    # --- AMD ---
    amd = detect_amd_phase(df)
    if amd["phase"] == "distribution":
        score += 20
        reasons.append(f"AMD: {amd['reason']}")
    elif amd["phase"] == "manipulation":
        score += 15
        reasons.append(f"AMD: {amd['reason']}")

    # --- Liquidity Sweeps ---
    sweeps = detect_liquidity_sweeps(df)
    if sweeps:
        last = sweeps[-1]
        if last["type"] == "bullish_sweep":
            score += 12
            reasons.append(f"جاروی نقدینگی صعودی در {last['level']}")
        else:
            score -= 8

    # --- ATR برای حد ضرر ---
    atr_val = atr(df).iloc[-1]
    stop_loss_long = price - 1.5 * atr_val

    # --- سطوح کلیدی ---
    levels = key_levels(df)

    return {
        "symbol": symbol,
        "score": min(100, max(0, score)),
        "price": float(price),
        "change_24h": price_info.get("change_24h", 0),
        "volume_24h": price_info.get("volume_24h", 0),
        "rsi": round(float(rsi_val), 2),
        "ema20": round(float(e20), 6),
        "ema50": round(float(e50), 6),
        "atr": round(float(atr_val), 6),
        "stop_loss": round(float(stop_loss_long), 6),
        "volume_profile": vp,
        "amd": amd,
        "sweeps": sweeps,
        "levels": levels,
        "reasons": reasons,
    }


# ============================================================
# تست سریع
# ============================================================

if __name__ == "__main__":
    from data_fetcher import get_klines

    print("\n🧪 تست analysis.py روی BTCUSDT...\n")
    candles = get_klines("BTCUSDT", "4h", 200)
    df = candles_to_df(candles)

    result = score_coin(df, "BTCUSDT", {"change_24h": 0, "volume_24h": 0})

    print(f"💰 قیمت: ${result['price']:,.2f}")
    print(f"⭐ امتیاز: {result['score']}/100")
    print(f"📊 RSI: {result['rsi']}")
    print(f"🎯 حد ضرر پیشنهادی: ${result['stop_loss']:,.2f}")
    print(f"\n📈 دلایل:")
    for r in result["reasons"]:
        print(f"   - {r}")
    print(f"\n🔍 فاز AMD: {result['amd']['phase']} — {result['amd']['reason']}")
    print(f"\n📊 Volume Profile:")
    print(f"   POC: ${result['volume_profile']['poc']:,.2f}")
    print(f"   VAH: ${result['volume_profile']['vah']:,.2f}")
    print(f"   VAL: ${result['volume_profile']['val']:,.2f}")
    print()