"""
ViaChart Agent - مغز اصلی
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
DAILY_FILE = "state/daily_count.json"
os.makedirs("state", exist_ok=True)

MIN_SCORE = 65
MAX_DAILY_SIGNALS = 3
COOLDOWN_HOURS = 24
TOP_SCAN = 30
INTERVAL = "4h"
KLINE_LIMIT = 200


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


def load_daily_count():
    if os.path.exists(DAILY_FILE):
        try:
            with open(DAILY_FILE, "r") as f:
                data = json.load(f)
                today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
                if data.get("date") == today:
                    return data
        except Exception:
            pass
    return {
        "date": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
        "count": 0
    }


def save_daily_count(data):
    with open(DAILY_FILE, "w") as f:
        json.dump(data, f, indent=2)


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


def analyze_all(limit=TOP_SCAN):
    log.info(f"📊 تحلیل {limit} ارز برتر...")

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

            analysis = analyze_coin(symbol, cg_id, df, coin)

            if passes_filters(analysis):
                results.append(analysis)

            if i % 10 == 0:
                log.info(f"   ... {i}/{len(symbols)}")

            time.sleep(0.1)

        except Exception as e:
            log.warning(f"   ⚠️ {symbol}: {str(e)[:60]}")
            continue

    log.info(f"✅ {len(results)} ارز از فیلترها گذشت")
    return results


async def run():
    log.info("=" * 50)
    log.info("🚀 ViaChart Agent")
    log.info("=" * 50)

    daily = load_daily_count()
    log.info(f"📊 سیگنال‌های امروز: {daily['count']}/{MAX_DAILY_SIGNALS}")

    if daily["count"] >= MAX_DAILY_SIGNALS:
        log.info("✋ به سقف روزانه رسیدیم. سیگنال جدید ارسال نمیشه.")
        return

    state = load_state()

    results = analyze_all()
    if not results:
        log.warning("⚠️ هیچ ارزی شرایط نداشت")
        return

    tier1 = [r for r in results if r["score"] >= MIN_SCORE]

    if not tier1:
        log.info(f"😐 هیچ سیگنال قوی‌ای (امتیاز ≥ {MIN_SCORE}) پیدا نشد")
        return

    tier1.sort(key=lambda x: x["score"], reverse=True)

    log.info(f"\n🏆 {len(tier1)} سیگنال TIER 1:")
    for r in tier1[:5]:
        log.info(f"   • {r['symbol']} — {r['score']}/100")

    sent = 0
    for pick in tier1:
        if daily["count"] + sent >= MAX_DAILY_SIGNALS:
            log.info("✋ سقف روزانه پر شد")
            break

        if is_on_cooldown(state, pick["symbol"]):
            log.info(f"   ⏳ {pick['symbol']} در cooldown")
            continue

        symbol = pick["symbol"]
        log.info(f"\n📤 ارسال {symbol} (امتیاز {pick['score']})...")

        try:
            chart = generate_chart(symbol, INTERVAL, 150, score_data=pick)
            ok = await post_signal(pick, chart)

            if ok:
                mark_sent(state, symbol)
                save_state(state)
                sent += 1
                log.info(f"   ✅ ارسال موفق")

                if sent < MAX_DAILY_SIGNALS:
                    await asyncio.sleep(30)
        except Exception as e:
            log.error(f"   ❌ {symbol}: {e}")

    if sent > 0:
        daily["count"] += sent
        save_daily_count(daily)
        log.info(f"\n📊 سیگنال‌های امروز: {daily['count']}/{MAX_DAILY_SIGNALS}")

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