"""
Signal Brain — مغز تصمیم‌گیرنده
- چک می‌کنه وضعیت آخرین سیگنال چیه
- اگه TP نخورده → دوباره نده
- اگه TP خورد یا Stop خورد → بررسی کن
"""
import logging
from datetime import datetime, timezone

log = logging.getLogger(__name__)


def should_send(symbol, current_analysis, history):
    """
    تصمیم می‌گیره دوباره سیگنال بده یا نه
    """

    # اگه هیچ سیگنال قبلی نیست → بده
    if not history or len(history) == 0:
        return {
            "decision": "SEND",
            "reason": f"اولین سیگنال {symbol} (امتیاز {current_analysis['score']})"
        }

    # آخرین سیگنال
    last = history[-1]
    last_price = last.get("price_at_signal", 0)
    last_score = last.get("score", 0)
    tp1 = last.get("tp1", 0)
    stop = last.get("stop", 0)
    last_result = last.get("result", "")

    current_price = current_analysis["price"]

    # ─────────────────────────────────
    # حالت ۱: آخرین سیگنال هنوز TP نخورده (OPEN)
    # → دوباره نده!
    # ─────────────────────────────────
    if not last_result or "OPEN" in last_result:
        # محاسبه سود فعلی
        if last_price > 0:
            change = ((current_price - last_price) / last_price) * 100
        else:
            change = 0

        return {
            "decision": "SKIP",
            "reason": f"{symbol} قبلاً سیگنال شده، هنوز TP نخورده (سود فعلی {change:+.1f}%)"
        }

    # ─────────────────────────────────
    # حالت ۲: TP خورد → بعد از مدتی دوباره می‌تونه
    # ─────────────────────────────────
    if "TP" in last_result:
        hours_ago = _hours_since(last.get("date"))
        if hours_ago >= 168:  # ۷ روز
            return {
                "decision": "SEND",
                "reason": f"سیگنال قبلی موفق بود، {hours_ago/24:.0f} روز گذشته"
            }
        return {
            "decision": "SKIP",
            "reason": f"سیگنال قبلی موفق بود ({last_result})، صبر تا ستاپ جدید"
        }

    # ─────────────────────────────────
    # حالت ۳: Stop خورد → بعد از مدتی
    # ─────────────────────────────────
    if "STOP" in last_result:
        hours_ago = _hours_since(last.get("date"))
        if hours_ago >= 168 and current_analysis["score"] >= 65:
            return {
                "decision": "SEND",
                "reason": f"سیگنال قبلی Stop خورد، {hours_ago/24:.0f} روز گذشته + امتیاز قوی"
            }
        return {
            "decision": "SKIP",
            "reason": "سیگنال قبلی ناموفق بود، صبر"
        }

    # ─────────────────────────────────
    # حالت ۴: نامشخص → محافظه‌کار
    # ─────────────────────────────────
    return {
        "decision": "SKIP",
        "reason": f"{symbol} قبلاً سیگنال شده"
    }


def _hours_since(date_str):
    """چند ساعت از این تاریخ گذشته"""
    if not date_str:
        return 999
    try:
        dt = datetime.fromisoformat(date_str)
        return (datetime.now(timezone.utc) - dt).total_seconds() / 3600
    except Exception:
        return 999