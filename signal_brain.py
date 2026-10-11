"""
Signal Brain — مغز تصمیم‌گیرنده ساده
بدون AI، فقط منطق تمیز
"""
import logging
from datetime import datetime, timezone

log = logging.getLogger(__name__)


def should_send(symbol, current_analysis, history):
    """
    تصمیم می‌گیره سیگنال بفرسته یا نه
    
    Args:
        symbol: مثل "NEARUSDT"
        current_analysis: داده فعلی (price, score, forces, ...)
        history: لیست سیگنال‌های قبلی این ارز
    
    Returns:
        dict: {"decision": "SEND"|"SKIP", "reason": "..."}
    """
    current_price = current_analysis["price"]
    current_score = current_analysis["score"]

    # ═══════════════════════════════════════
    # حالت ۱: هیچ سیگنال قبلی نیست
    # ═══════════════════════════════════════
    if not history:
        return {
            "decision": "SEND",
            "reason": f"اولین سیگنال (امتیاز {current_score})"
        }

    # آخرین سیگنال
    last = history[-1]
    last_time_str = last.get("date")
    last_price = last.get("price_at_signal", 0)
    last_score = last.get("score", 0)
    last_result = last.get("result", "")

    # محاسبه زمان سپری شده
    hours_ago = 999
    if last_time_str:
        try:
            last_dt = datetime.fromisoformat(last_time_str)
            hours_ago = (datetime.now(timezone.utc) - last_dt).total_seconds() / 3600
        except Exception:
            pass

    # ═══════════════════════════════════════
    # حالت ۲: سیگنال قبلی < 24h پیش
    # ═══════════════════════════════════════
    if hours_ago < 24:
        return {
            "decision": "SKIP",
            "reason": f"سیگنال قبلی فقط {hours_ago:.0f} ساعت پیش بود"
        }

    # ═══════════════════════════════════════
    # حالت ۳: سیگنال قبلی موفق بود (TP خورد)
    # ═══════════════════════════════════════
    if last_result and "TP" in last_result:
        return {
            "decision": "SKIP",
            "reason": f"سیگنال قبلی موفق بود ({last_result})"
        }

    # ═══════════════════════════════════════
    # حالت ۴: سیگنال قبلی استاپ خورد
    # ═══════════════════════════════════════
    if last_result == "STOPPED":
        # اگه امتیاز قوی‌تر شده + 7+ روز گذشته
        if hours_ago >= 168 and current_score >= 65:
            return {
                "decision": "SEND",
                "reason": f"ستاپ جدید قوی ({current_score}) پس از {hours_ago/24:.0f} روز"
            }
        # اگه < 7 روز
        return {
            "decision": "SKIP",
            "reason": "سیگنال قبلی ناموفق بود، صبر بیشتر"
        }

    # ═══════════════════════════════════════
    # حالت ۵: سیگنال قبلی OPEN (باز) است
    # ═══════════════════════════════════════
    if last_result and "OPEN" in last_result:
        # تغییر قیمت از زمان سیگنال
        if last_price > 0:
            price_change = ((current_price - last_price) / last_price) * 100
        else:
            price_change = 0

        # اگه تو سود قابل توجهه → بذار ادامه بده
        if price_change > 3:
            return {
                "decision": "SKIP",
                "reason": f"سیگنال قبلی تو سود ({price_change:+.1f}%)، بذار ادامه بده"
            }

        # اگه 48h گذشته و هنوز در حرکته
        if hours_ago < 48:
            return {
                "decision": "SKIP",
                "reason": "سیگنال قبلی هنوز بازه"
            }

        # بعد از 48h، اگه امتیاز قوی‌تره + قیمت نزدیک قبلی
        if current_score >= last_score + 5 and abs(price_change) < 5:
            return {
                "decision": "SEND",
                "reason": f"امتیاز بهتر شد ({last_score}→{current_score})"
            }

        return {
            "decision": "SKIP",
            "reason": "سیگنال قبلی هنوز بازه"
        }

    # ═══════════════════════════════════════
    # حالت ۶: هیچ نتیجه‌ای ثبت نشده (خام)
    # ═══════════════════════════════════════
    if last_price > 0:
        price_change = ((current_price - last_price) / last_price) * 100
    else:
        price_change = 0

    # اگه قیمت خیلی رفته بالا → دیره
    if price_change > 10:
        return {
            "decision": "SKIP",
            "reason": f"قیمت {price_change:+.0f}% رفته، دیره"
        }

    # اگه قیمت ریخته و داره برمی‌گرده + امتیاز قوی
    if price_change < -5 and current_score >= 60:
        return {
            "decision": "SEND",
            "reason": f"ریزش {price_change:.0f}% + امتیاز قوی"
        }

    # اگه < 48h → صبر
    if hours_ago < 48:
        return {
            "decision": "SKIP",
            "reason": f"سیگنال قبلی {hours_ago:.0f} ساعت پیش بود"
        }

    # اگه 7+ روز گذشته → اجازه بده
    if hours_ago >= 168:
        return {
            "decision": "SEND",
            "reason": f"ستاپ جدید پس از {hours_ago/24:.0f} روز"
        }

    return {
        "decision": "SKIP",
        "reason": "صبر تا شرایط بهتر"
    }