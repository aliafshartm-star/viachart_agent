"""
سیگنال کوتاه ViaChart
"""
import os
import logging

from telegram import Bot, InputFile
from telegram.constants import ParseMode

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')
log = logging.getLogger(__name__)

# کانال ارسال خودکار (کانال جدید) - از Secret خونده میشه
CHANNEL_ID = os.environ.get("TELEGRAM_CHANNEL_ID", "@binancesignal_ai")

# یوزرنیم نمایشی پایین پست (کانال قدیمی - برند)
CHANNEL_HANDLE = "@viachart_app"


def _fmt(p):
    if p >= 1000:
        return f"${p:,.2f}"
    elif p >= 1:
        return f"${p:,.4f}"
    elif p >= 0.01:
        return f"${p:.4f}"
    else:
        return f"${p:.6f}"


def _pct(from_p, to_p):
    if from_p == 0:
        return "0%"
    change = ((to_p - from_p) / from_p) * 100
    sign = "+" if change >= 0 else ""
    return f"{sign}{change:.1f}%"


def _full_name(symbol):
    mapping = {
        "BTC": "Bitcoin", "ETH": "Ethereum", "SOL": "Solana",
        "BNB": "BNB", "XRP": "Ripple", "ADA": "Cardano",
        "DOGE": "Dogecoin", "AVAX": "Avalanche", "DOT": "Polkadot",
        "LINK": "Chainlink", "NEAR": "Near", "APT": "Aptos",
        "ARB": "Arbitrum", "OP": "Optimism", "SUI": "Sui",
        "INJ": "Injective", "TIA": "Celestia", "PEPE": "Pepe",
        "WIF": "dogwifhat", "FET": "Fetch.ai",
    }
    return mapping.get(symbol, symbol)


def build_signal_post(a):
    symbol = a["symbol"].replace("USDT", "")
    full_name = _full_name(symbol)
    price = a["price"]
    score = a["score"]
    change = a.get("change_24h", 0)
    reasons = a.get("reasons", [])

    entry_low = a["entry_low"]
    entry_high = a["entry_high"]
    stop = a["stop"]
    tp1 = a["tp1"]
    tp2 = a["tp2"]
    tp3 = a["tp3"]

    tier = "🔥" if score >= 70 else ("🟢" if score >= 60 else "🟡")
    ch = "📈" if change >= 0 else "📉"
    cs = "+" if change >= 0 else ""

    # فقط ۱ دلیل مهم (فشرده)
    reason_line = ""
    if reasons:
        reason_line = f"💡 {reasons[0]}"

    parts = [
        f"{tier} <b>{symbol}/USDT</b> — {score}/100",
        f"💵 {_fmt(price)}  {ch} {cs}{change:.1f}%",
        "",
        f"🎯 ورود: {_fmt(entry_low)} - {_fmt(entry_high)}",
        f"🛑 SL: {_fmt(stop)} ({_pct(entry_high, stop)})",
        f"✅ TP: {_fmt(tp1)} ({_pct(entry_high, tp1)}) / {_fmt(tp2)} ({_pct(entry_high, tp2)}) / {_fmt(tp3)} ({_pct(entry_high, tp3)})",
    ]

    if reason_line:
        parts.append(reason_line)

    parts.extend([
        "",
        f"⚠️ اسپات | ریسک ۱٪ | 📢 {CHANNEL_HANDLE}",
        f"#ViaChart #{symbol} #{full_name} #Signal",
    ])

    return "\n".join(parts)


async def send_post(text, chart_path=None, disable_notification=False):
    bot = Bot(token=os.environ["TELEGRAM_BOT_TOKEN"])
    try:
        if chart_path and os.path.exists(chart_path):
            caption = text if len(text) <= 1024 else text[:1020] + "..."
            with open(chart_path, "rb") as f:
                await bot.send_photo(
                    chat_id=CHANNEL_ID,
                    photo=InputFile(f),
                    caption=caption,
                    parse_mode=ParseMode.HTML,
                    disable_notification=disable_notification,
                )
            log.info("✅ پست با عکس ارسال شد")
            if len(text) > 1024:
                await bot.send_message(
                    chat_id=CHANNEL_ID,
                    text=text[1024:],
                    parse_mode=ParseMode.HTML,
                    disable_notification=True,
                )
        else:
            await bot.send_message(
                chat_id=CHANNEL_ID,
                text=text[:4096],
                parse_mode=ParseMode.HTML,
                disable_notification=disable_notification,
            )
            log.info("✅ پست متنی ارسال شد")
        return True
    except Exception as e:
        log.error(f"❌ خطا در ارسال: {e}")
        return False


async def post_signal(analysis_data, chart_path=None):
    log.info(f"📝 ساخت پست سیگنال برای {analysis_data['symbol']}...")
    post = build_signal_post(analysis_data)
    log.info(f"\n{post}\n")
    return await send_post(post, chart_path=chart_path)