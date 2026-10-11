"""
ViaChart Agent - مغز اصلی
- هر ارزی که امتیاز ≥ 50 بگیره → سیگنال
- Cooldown 24h (هر ارز یک بار در روز)
- بدون سقف روزانه
"""
import os
import sys
import json
import time
import asyncio
import logging
from datetime import datetime, timezone, timedelta

from data_fetcher import get_top_symbols, get_klines
from pump_detector import (
    candles_to_df, analyze_coin, passes_filters, get_signal_tier
)
from chart_generator import generate_chart
from telegram_poster import post_signal

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')
log = logging.getLogger(__name__)

STATE_FILE = "state/last_sent.json"
os.makedirs("state", exist_ok=True)

# تنظیمات
MIN_SCORE = 50           # آستانه سیگنال
COOLDOWN_HOURS = 24      # هر ارز ۲۴ ساعت یک بار
TOP_SCAN = 100           # ۱۰۰ ارز برتر
INTERVAL = "4h"
KLINE_LIMIT = 200
SEND_DELAY = 20          # تاخیر بین ارسال‌ها


# ============================================================
# State Management
# ============================================================

def load_state():
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE, "r") as f:
                return json.load(f)
        except Exception:
            pass
    return {"last_sent": {}}


def save_state(state):
    with open(STATE_FILE, "w") as f:
        json.dump(state, f, indent=2)


def is_on_cooldown(state, symbol):
    last_time = state["last_sent"].get(symbol)
    if not last_time:
        return False
    try:
        last_dt = datetime.fromisoformat(last_time)
        if datetime.now(timezone.utc) - last_dt < timedelta(hours=COOLDOWN_HOURS):
            return True
    except Exception:
        pass
    return False


def mark_sent(state, symbol):
    state["last_sent"][symbol] = datetime.now(timezone.utc).isoformat()


# ============================================================
# تحلیل
# ============================================================

def analyze_all(limit=TOP_SCAN):
    log.info(f"📊 تحلیل {limit} ارز...")

    # BTC برای RS
    btc_candles = get_klines("BTCUSDT", INTERVAL, KLINE_LIMIT)
    btc_df = candles_to_df(btc_candles) if btc_candles else None

    symbols = get_top_symbols(limit=limit)
    if not symbols:
        log.error("❌ هیچ ارزی دریافت نشد")
        return []

    results = []
    for i, coin in enumerate(symbols, 1):
        symbol = coin["symbol"]
        try:
            candles = get_klines(symbol, INTERVAL, KLINE_LIMIT)
            if not candles or len(candles) < 60:
                continue

            df = candles_to_df(candles)
            cg_id = symbol.replace("USDT", "").lower()

            analysis = analyze_coin(symbol, cg_id, df, coin, btc_df=btc_df)
            results.append(analysis)

            if i % 20 == 0:
                log.info(f"   ... {i}/{len(symbols)}")

            time.sleep(0.08)

        except Exception as e:
            log.warning(f"   ⚠️ {symbol}: {str(e)[:60]}")
            continue

    return results


# ============================================================
# اجرا
# ============================================================

async def run():
    log.info("=" * 50)
    log.info("🚀 ViaChart Agent")
    log.info("=" * 50)

    state = load_state()

    # تحلیل همه ارزها
    all_results = analyze_all()
    if not all_results:
        log.warning("⚠️ هیچ ارزی تحلیل نشد")
        return

    # فیلترها
    passed = [r for r in all_results if passes_filters(r)]
    log.info(f"✅ {len(passed)} ارز از فیلترها گذشت")

    # امتیاز ≥ MIN_SCORE
    candidates = [r for r in passed if r["score"] >= MIN_SCORE]
    candidates.sort(key=lambda x: x["score"], reverse=True)

    log.info(f"🎯 {len(candidates)} ارز امتیاز ≥ {MIN_SCORE}")

    if not candidates:
        log.info(f"😐 هیچ سیگنالی نبود")
        return

    # نمایش ۱۰ تای برتر
    log.info(f"\n🏆 بهترین‌ها:")
    for r in candidates[:10]:
        log.info(f"   • {r['symbol']:12s} — {r['score']:3d}/100")

    # ========= ارسال =========
    sent = 0
    for pick in candidates:
        # چک cooldown
        if is_on_cooldown(state, pick["symbol"]):
            log.info(f"   ⏳ {pick['symbol']} در cooldown")
            continue

        symbol = pick["symbol"]
        score = pick["score"]
        log.info(f"\n📤 ارسال {symbol} ({score}/100)...")

        try:
            chart = generate_chart(symbol, INTERVAL, 150, score_data=pick)
            ok = await post_signal(pick, chart)

            if ok:
                mark_sent(state, symbol)
                save_state(state)
                sent += 1
                log.info(f"   ✅ ارسال موفق")

                # تاخیر بین ارسال‌ها
                await asyncio.sleep(SEND_DELAY)
        except Exception as e:
            log.error(f"   ❌ {symbol}: {e}")

    log.info(f"\n✅ {sent} سیگنال ارسال شد")


def main():
    log.info("🎬 ViaChart Agent")

    try:
        asyncio.run(run())
        log.info("🎉 اجرا تمام شد")
    except Exception as e:
        log.error(f"❌ خطای کلی: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()