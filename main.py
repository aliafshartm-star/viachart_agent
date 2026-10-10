"""
ViaChart Agent - مغز اصلی
- تحلیل ۱۰۰ ارز، انتخاب ۴ برتر، ارسال ۴ پست سیگنال
"""
import os
import sys
import json
import time
import asyncio
import logging
from datetime import datetime, timezone, timedelta

from data_fetcher import get_top_symbols, get_klines
from analysis import candles_to_df, score_coin
from chart_generator import generate_chart
from telegram_poster import post_signal

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')
log = logging.getLogger(__name__)

# فایل ذخیره وضعیت ارزهای ارسال‌شده
STATE_FILE = "state/last_sent.json"
os.makedirs("state", exist_ok=True)

# تنظیمات
MIN_SCORE = 40          # حداقل امتیاز برای انتخاب
TOP_N = 4               # تعداد ارزهای برتر
INTERVAL = "4h"         # تایم‌فریم
KLINE_LIMIT = 200       # تعداد کندل
COOLDOWN_HOURS = 6      # جلوگیری از تکرار یه ارز تا ۶ ساعت
SEND_DELAY = 20         # فاصله بین پست‌ها (ثانیه)


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
    """چک کن که آیا این ارز تازه ارسال شده"""
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

def analyze_top_coins(limit=100):
    """تحلیل کامل ۱۰۰ ارز و برگرداندن لیست رتبه‌بندی‌شده"""
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
            analysis = score_coin(df, symbol, coin)
            analysis["interval"] = INTERVAL.upper()

            results.append(analysis)

            if i % 10 == 0:
                log.info(f"   ... {i}/{len(symbols)} ارز تحلیل شد")

            time.sleep(0.15)

        except Exception as e:
            log.warning(f"   ⚠️ خطا در تحلیل {symbol}: {str(e)[:80]}")
            continue

    log.info(f"✅ {len(results)} ارز تحلیل شد")
    return results


def select_top_picks(results, state, top_n=TOP_N):
    """انتخاب بهترین ارزها با فیلتر امتیاز و cooldown"""
    candidates = [r for r in results if r["score"] >= MIN_SCORE]
    candidates = [r for r in candidates if not is_on_cooldown(state, r["symbol"])]
    candidates.sort(key=lambda x: x["score"], reverse=True)

    top_picks = candidates[:top_n]

    log.info(f"🎯 {len(top_picks)} ارز برتر انتخاب شد:")
    for p in top_picks:
        log.info(f"   • {p['symbol']} — امتیاز {p['score']}")

    return top_picks


# ============================================================
# اجرای دسته‌ای: پست‌های سیگنال
# ============================================================

async def run_signals():
    """تحلیل ۱۰۰ ارز و ارسال ۴ پست سیگنال"""
    log.info("=" * 50)
    log.info("🚀 شروع دسته سیگنال‌ها")
    log.info("=" * 50)

    state = load_state()

    results = analyze_top_coins(limit=100)
    if not results:
        log.error("❌ لیست تحلیل خالیه")
        return

    top_picks = select_top_picks(results, state, top_n=TOP_N)
    if not top_picks:
        log.warning("⚠️ هیچ ارزی شرایط انتخاب رو نداشت")
        return

    sent_count = 0
    for i, pick in enumerate(top_picks, 1):
        symbol = pick["symbol"]
        log.info(f"\n📤 [{i}/{len(top_picks)}] ارسال پست برای {symbol}...")

        try:
            chart_path = generate_chart(
                symbol, INTERVAL, 150, score_data=pick
            )
            if not chart_path:
                log.error(f"   ❌ چارت ساخته نشد")
                continue

            ok = await post_signal(pick, chart_path)
            if ok:
                mark_sent(state, symbol)
                save_state(state)
                sent_count += 1
                log.info(f"   ✅ ارسال موفق")

            if i < len(top_picks):
                log.info(f"   ⏳ انتظار {SEND_DELAY} ثانیه...")
                await asyncio.sleep(SEND_DELAY)

        except Exception as e:
            log.error(f"   ❌ خطا در {symbol}: {e}")
            continue

    log.info(f"\n✅ {sent_count} پست سیگنال ارسال شد")


# ============================================================
# نقطه ورود
# ============================================================

def main():
    mode = "signals"

    if len(sys.argv) > 1:
        mode = sys.argv[1].lower()

    log.info(f"🎬 ViaChart Agent — حالت: {mode}")

    try:
        if mode == "signals":
            asyncio.run(run_signals())
        else:
            log.error(f"❌ حالت نامعتبر: {mode}")
            log.info("استفاده: python main.py signals")
            sys.exit(1)

        log.info("🎉 اجرا با موفقیت تمام شد")

    except Exception as e:
        log.error(f"❌ خطای کلی: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()