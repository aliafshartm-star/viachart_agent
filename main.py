"""
ViaChart Agent - مغز اصلی
- تحلیل ۱۰۰ ارز با ۵ نیرو
- انتخاب بهترین ارز
- ارسال سیگنال به کانال
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
MIN_SCORE = 35              # حداقل امتیاز (کم شد)
TOP_N = 1                   # تعداد سیگنال در هر اجرا
INTERVAL = "4h"
KLINE_LIMIT = 200
COOLDOWN_HOURS = 12


# ============================================================
# مدیریت State
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
# تحلیل ۱۰۰ ارز
# ============================================================

def analyze_all(limit=100):
    """تحلیل همه ارزها"""
    log.info(f"📊 شروع تحلیل {limit} ارز...")

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

            # فقط ارزهایی که فیلترها رو پاس کردن
            if passes_filters(analysis):
                results.append(analysis)

            if i % 20 == 0:
                log.info(f"   ... {i}/{len(symbols)} تحلیل شد")

            time.sleep(0.12)

        except Exception as e:
            log.warning(f"   ⚠️ خطا در {symbol}: {str(e)[:80]}")
            continue

    log.info(f"✅ {len(results)} ارز از فیلترها گذشت")
    return results


def select_best(results, state):
    """انتخاب بهترین ارز"""
    candidates = [r for r in results if not is_on_cooldown(state, r["symbol"])]
    candidates.sort(key=lambda x: x["score"], reverse=True)

    if not candidates:
        return None

    top = candidates[0]
    log.info(f"🎯 ارز برتر: {top['symbol']} — امتیاز {top['score']}")
    return top


# ============================================================
# اجرا
# ============================================================

async def run():
    log.info("=" * 50)
    log.info("🚀 شروع ViaChart Agent")
    log.info("=" * 50)

    state = load_state()

    # تحلیل
    results = analyze_all(limit=100)
    if not results:
        log.warning("⚠️ هیچ ارزی شرایط نداشت")
        return

    # انتخاب برترین‌ها (مرتب‌شده)
    results.sort(key=lambda x: x["score"], reverse=True)

    log.info(f"\n🏆 ۵ ارز برتر:")
    for r in results[:5]:
        log.info(f"   • {r['symbol']} — {r['score']}/100 ({get_signal_tier(r['score'])})")

    # ارسال سیگنال‌ها
    sent = 0
    for pick in results:
        if sent >= TOP_N:
            break

        if is_on_cooldown(state, pick["symbol"]):
            log.info(f"   ⏳ {pick['symbol']} در cooldown")
            continue

        symbol = pick["symbol"]
        log.info(f"\n📤 ارسال سیگنال {symbol} (امتیاز {pick['score']})...")

        try:
            chart = generate_chart(symbol, INTERVAL, 150, score_data=pick)
            ok = await post_signal(pick, chart)

            if ok:
                mark_sent(state, symbol)
                save_state(state)
                sent += 1
                log.info(f"   ✅ ارسال موفق")
        except Exception as e:
            log.error(f"   ❌ خطا در {symbol}: {e}")

    log.info(f"\n✅ {sent} سیگنال ارسال شد")


def main():
    log.info("🎬 ViaChart Agent")

    try:
        asyncio.run(run())
        log.info("🎉 اجرا با موفقیت تمام شد")
    except Exception as e:
        log.error(f"❌ خطای کلی: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()