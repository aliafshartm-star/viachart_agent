"""
Signal History — ذخیره تاریخچه سیگنال‌ها
و چک کردن اینکه TP یا Stop خورده یا نه
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
    """ذخیره سیگنال جدید"""
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
        "result": "OPEN",           # OPEN / TP1_HIT / TP2_HIT / TP3_HIT / STOPPED
        "result_price": None,
        "result_date": None,
    }

    history[symbol].append(record)
    save_history(history)
    return record


def get_all_signals(symbol):
    history = load_history()
    return history.get(symbol, [])


def update_result(symbol, current_price):
    """
    آپدیت وضعیت آخرین سیگنال بر اساس قیمت فعلی
    - TP خورد؟
    - Stop خورد؟
    """
    history = load_history()
    signals = history.get(symbol, [])
    if not signals:
        return None

    # فقط آخرین سیگنال رو چک کن
    last = signals[-1]

    # اگه قبلاً نتیجه مشخص شده → دست نزن
    if last.get("result") and last["result"] not in ["OPEN"] and last["result"] is not None:
        # اگه OPEN قبلاً بوده ولی الان TP یا Stop خورده
        pass

    tp1 = last.get("tp1", 0)
    tp2 = last.get("tp2", 0)
    tp3 = last.get("tp3", 0)
    stop = last.get("stop", 0)
    entry = last.get("price_at_signal", 0)

    # چک کردن نتیجه
    if current_price >= tp3:
        last["result"] = "TP3_HIT"
    elif current_price >= tp2:
        last["result"] = "TP2_HIT"
    elif current_price >= tp1:
        last["result"] = "TP1_HIT"
    elif current_price <= stop:
        last["result"] = "STOPPED"
    else:
        # هنوز بازه
        change = ((current_price - entry) / entry) * 100 if entry > 0 else 0
        last["result"] = f"OPEN ({change:+.1f}%)"

    last["result_price"] = current_price
    last["result_date"] = datetime.now(timezone.utc).isoformat()

    save_history(history)
    return last