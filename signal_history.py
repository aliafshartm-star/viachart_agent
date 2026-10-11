"""
Signal History — ذخیره و تحلیل تاریخچه سیگنال‌ها
"""
import os
import json
import logging
from datetime import datetime, timezone

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')
log = logging.getLogger(__name__)

HISTORY_FILE = "state/signal_history.json"
os.makedirs("state", exist_ok=True)


def load_history():
    if os.path.exists(HISTORY_FILE):
        try:
            with open(HISTORY_FILE, "r") as f:
                return json.load(f)
        except Exception:
            pass
    return {}


def save_history(history):
    with open(HISTORY_FILE, "w") as f:
        json.dump(history, f, indent=2, ensure_ascii=False)


def add_signal(symbol, analysis):
    """اضافه کردن سیگنال جدید به تاریخچه"""
    history = load_history()

    if symbol not in history:
        history[symbol] = []

    record = {
        "date": datetime.now(timezone.utc).isoformat(),
        "price_at_signal": analysis["price"],
        "score": analysis["score"],
        "entry_low": analysis["entry_low"],
        "entry_high": analysis["entry_high"],
        "stop": analysis["stop"],
        "tp1": analysis["tp1"],
        "tp2": analysis["tp2"],
        "tp3": analysis["tp3"],
        "forces": analysis.get("forces", {}),
        "reasons": analysis.get("reasons", []),
        "result": None,
        "result_price": None,
        "result_date": None,
    }

    history[symbol].append(record)
    save_history(history)
    return record


def get_all_signals(symbol):
    history = load_history()
    return history.get(symbol, [])


def get_last_signal(symbol):
    signals = get_all_signals(symbol)
    if not signals:
        return None
    return signals[-1]


def update_result(symbol, current_price):
    """آپدیت نتیجه آخرین سیگنال"""
    history = load_history()
    signals = history.get(symbol, [])
    if not signals:
        return None

    last = signals[-1]
    if last.get("result"):
        return last

    entry = last["price_at_signal"]
    tp1 = last["tp1"]
    tp2 = last["tp2"]
    tp3 = last["tp3"]
    stop = last["stop"]

    if current_price >= tp3:
        last["result"] = "TP3_HIT"
    elif current_price >= tp2:
        last["result"] = "TP2_HIT"
    elif current_price >= tp1:
        last["result"] = "TP1_HIT"
    elif current_price <= stop:
        last["result"] = "STOPPED"
    else:
        change_pct = ((current_price - entry) / entry) * 100
        last["result"] = f"OPEN ({change_pct:+.1f}%)"

    last["result_price"] = current_price
    last["result_date"] = datetime.now(timezone.utc).isoformat()

    save_history(history)
    return last


def build_context_for_ai(symbol, current_analysis):
    """ساخت context برای AI Judge"""
    signals = get_all_signals(symbol)

    if not signals:
        return {
            "has_history": False,
            "current": {
                "price": current_analysis["price"],
                "score": current_analysis["score"],
                "forces": current_analysis.get("forces", {}),
                "reasons": current_analysis.get("reasons", []),
            },
            "past_signals": [],
        }

    # آپدیت نتیجه آخرین سیگنال
    update_result(symbol, current_analysis["price"])
    signals = get_all_signals(symbol)

    past = []
    for s in signals[-5:]:
        hours_ago = None
        try:
            dt = datetime.fromisoformat(s["date"])
            hours_ago = (datetime.now(timezone.utc) - dt).total_seconds() / 3600
        except Exception:
            pass

        past.append({
            "date": s["date"],
            "hours_ago": round(hours_ago, 1) if hours_ago else None,
            "price_then": s["price_at_signal"],
            "score_then": s["score"],
            "result": s.get("result"),
            "result_price": s.get("result_price"),
            "entry": s["entry_low"],
            "tp1": s["tp1"],
            "stop": s["stop"],
        })

    return {
        "has_history": True,
        "current": {
            "price": current_analysis["price"],
            "score": current_analysis["score"],
            "forces": current_analysis.get("forces", {}),
            "reasons": current_analysis.get("reasons", []),
        },
        "past_signals": past,
    }