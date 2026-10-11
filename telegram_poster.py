"""
ساخت و ارسال سیگنال حرفه‌ای به کانال ViaChart
۵ نیرو: Volume, Trend, News, Momentum, Regime
"""
import os
import logging

from telegram import Bot, InputFile
from telegram.constants import ParseMode

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')
log = logging.getLogger(__name__)

CHANNEL_ID = os.environ.get("TELEGRAM_CHANNEL_ID", "@viachart_app")
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
        return "0.0%"
    change = ((to_p - from_p) / from_p) * 100
    sign = "+" if change >= 0 else ""
    return f"{sign}{change:.1f}%"


def _full_name(symbol):
    mapping = {
        "BTC": "Bitcoin", "ETH": "Ethereum", "SOL": "Solana",
        "BNB": "BNB", "XRP": "Ripple", "ADA": "Cardano",
        "DOGE": "Dogecoin", "AVAX": "Avalanche", "DOT": "Polkadot",
        "MATIC": "Polygon", "LINK": "Chainlink", "TON": "Toncoin",
        "TRX": "Tron", "LTC": "Litecoin", "BCH": "BitcoinCash",
        "NEAR": "Near", "ATOM": "Cosmos", "XLM": "Stellar",
        "APT": "Aptos", "ARB": "Arbitrum", "OP": "Optimism",
        "SUI": "Sui", "SEI": "Sei", "INJ": "Injective",
        "TIA": "Celestia", "PEPE": "Pepe", "WIF": "dogwifhat",
        "FET": "Fetch.ai", "RNDR": "Render", "TAO": "Bittensor",
        "MAGIC": "Magic", "RLC": "iExec", "STRK": "Starknet",
        "CFX": "Conflux",
    }
    return mapping.get(symbol, symbol)


def build_signal_post(a):
    symbol_raw = a["symbol"]
    symbol = symbol_raw.replace("USDT", "")
    full_name = _full_name(symbol)
    tf = "4H"
    price = a["price"]
    score = a["score"]
    change_24h = a.get("change_24h", 0)
    forces = a.get("forces", {})
    reasons = a.get("reasons", [])

    entry_low = a["entry_low"]
    entry_high = a["entry_high"]
    stop = a["stop"]
    tp1 = a["tp1"]
    tp2 = a["tp2"]
    tp3 = a["tp3"]

    # Tier
    if score >= 70:
        tier = "TIER 1 🔥"
    elif score >= 60:
        tier = "TIER 2 🟢"
    else:
        tier = "TIER 3 🟡"

    change_emoji = "📈" if change_24h >= 0 else "📉"
    change_sign = "+" if change_24h >= 0 else ""

    # دلایل (حداکثر ۵)
    reason_lines = ""
    for r in reasons[:5]:
        reason_lines += "🔹 " + r + "\n"
    if not reason_lines:
        reason_lines = "🔹 تحلیل تکنیکال\n"

    # نیروها
    f1 = forces.get("volume", 0)
    f2 = forces.get("trend", 0)
    f3 = forces.get("news", 0)
    f4 = forces.get("momentum", 0)
    f5 = forces.get("regime", 0)

    parts = []
    parts.append("🟢 <b>ViaChart SPOT | " + symbol + "/USDT</b>")
    parts.append("")
    parts.append("🎯 امتیاز: <b>" + str(score) + "/100</b> (" + tier + ")")
    parts.append("⏰ تایم‌فریم: 1-7 روز")
    parts.append("")
    parts.append("━━━━━━━━━━━━━━━")
    parts.append("💰 <b>پلن معاملاتی</b>")
    parts.append("━━━━━━━━━━━━━━━")
    parts.append("🟢 ورود: <b>" + _fmt(entry_low) + " - " + _fmt(entry_high) + "</b>")
    parts.append("")
    parts.append("🎯 اهداف:")
    parts.append("   🔸 TP1: <b>" + _fmt(tp1) + "</b> (" + _pct(entry_high, tp1) + ")")
    parts.append("   🔸 TP2: <b>" + _fmt(tp2) + "</b> (" + _pct(entry_high, tp2) + ")")
    parts.append("   🔸 TP3: <b>" + _fmt(tp3) + "</b> (" + _pct(entry_high, tp3) + ")")
    parts.append("")
    parts.append("🛑 حد ضرر: <b>" + _fmt(stop) + "</b> (" + _pct(entry_high, stop) + ")")
    parts.append("")
    parts.append("━━━━━━━━━━━━━━━")
    parts.append("💡 <b>چرا این سیگنال؟</b>")
    parts.append("━━━━━━━━━━━━━━━")
    parts.append(reason_lines.rstrip())
    parts.append("")
    parts.append("━━━━━━━━━━━━━━━")
    parts.append("📊 <b>امتیاز ۵ نیرو</b>")
    parts.append("━━━━━━━━━━━━━━━")
    parts.append("📈 Volume: " + str(f1) + "/20")
    parts.append("📊 Trend: " + str(f2) + "/20")
    parts.append("📰 News: " + str(f3) + "/20")
    parts.append("🔥 Momentum: " + str(f4) + "/20")
    parts.append("🌊 Regime: " + str(f5) + "/20")
    parts.append("")
    parts.append("━━━━━━━━━━━━━━━")
    parts.append("🛡️ <b>مدیریت ریسک</b>")
    parts.append("━━━━━━━━━━━━━━━")
    parts.append("• فقط اسپات (بدون اهرم)")
    parts.append("• حداکثر ۱٪ ریسک در هر معامله")
    parts.append("• بعد از TP1 حد ضرر رو به نقطه ورود بیار")
    parts.append("• ⚠️ توصیه مالی نیست — DYOR")
    parts.append("")
    parts.append("📢 " + CHANNEL_HANDLE)
    parts.append("")
    parts.append("#ViaChart #" + symbol + " #" + full_name + " #Crypto #Spot #Signal")

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