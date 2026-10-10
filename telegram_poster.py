"""
ساخت و ارسال پست حرفه‌ای به کانال تلگرام ViaChart
- قالب سیگنال: بخش‌بندی شده
- قالب خبر: وضعیت بازار + ۲ خبر (Gemini)
"""
import os
import logging

from telegram import Bot, InputFile
from telegram.constants import ParseMode

from llm_router import LLMRouter
from news import get_all_news

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
    }
    return mapping.get(symbol, symbol)


# ============================================================
# ترجمه با Gemini (بدون Groq)
# ============================================================

def _translate_to_farsi(english_text):
    """ترجمه با Gemini مستقیم — بدون واسطه Groq"""
    import google.generativeai as genai

    try:
        genai.configure(api_key=os.environ["GEMINI_API_KEY"])

        model_names = [
            "gemini-2.0-flash",
            "gemini-1.5-flash",
            "gemini-1.5-pro",
            "gemini-pro",
        ]

        prompt = (
            "Translate this English crypto headline to Persian (Farsi).\n"
            "Output ONLY the Persian translation. Nothing else.\n\n"
            "English: " + english_text + "\n\n"
            "Persian:"
        )

        result = None
        for model_name in model_names:
            try:
                model = genai.GenerativeModel(model_name)
                response = model.generate_content(
                    prompt,
                    generation_config={
                        "temperature": 0.1,
                        "max_output_tokens": 100,
                    }
                )
                result = response.text.strip()
                if result:
                    log.info(f"✅ ترجمه با {model_name}")
                    break
            except Exception as e:
                log.warning(f"مدل {model_name} خطا داد: {str(e)[:80]}")
                continue

        if not result:
            return "—"

        # پاک‌سازی: فقط خط اول فارسی
        lines = result.split("\n")
        fa_lines = []

        for line in lines:
            line = line.strip()
            if not line:
                continue

            low = line.lower()
            for prefix in ["persian:", "translation:", "english:", "output:"]:
                if low.startswith(prefix):
                    line = line[len(prefix):].strip()
                    break

            if not line:
                continue

            fa_chars = sum(1 for c in line if '\u0600' <= c <= '\u06FF')
            total = len(line.replace(" ", ""))

            if total > 0 and fa_chars / total > 0.5:
                fa_lines.append(line)

        if not fa_lines:
            return "—"

        result = fa_lines[0]
        result = result.strip('"').strip("'").strip("«»").strip()
        return result

    except Exception as e:
        log.warning(f"ترجمه ناموفق: {e}")
        return "—"


# ============================================================
# قالب سیگنال
# ============================================================

def build_signal_post(a):
    symbol_raw = a["symbol"]
    symbol = symbol_raw.replace("USDT", "")
    full_name = _full_name(symbol)
    tf = a.get("interval", "4H").upper()
    price = a["price"]
    score = a["score"]
    rsi = a.get("rsi", 50)
    change_24h = a.get("change_24h", 0)
    sl = a.get("stop_loss", price * 0.97)
    atr_val = a.get("atr", price * 0.02)
    amd = a.get("amd", {})
    reasons = a.get("reasons", [])

    entry = price
    tp1 = price + atr_val * 1.5
    tp2 = price + atr_val * 3.0
    tp3 = price + atr_val * 5.0

    if score >= 70:
        score_label = "🔥 قوی"
    elif score >= 50:
        score_label = "🟢 متوسط"
    elif score >= 30:
        score_label = "🟡 ضعیف"
    else:
        score_label = "⚪ کم"

    reason_lines = ""
    for r in reasons[:3]:
        reason_lines += "🔹 " + r + "\n"
    if not reason_lines:
        reason_lines = "🔹 تحلیل تکنیکال در حال شکل‌گیری\n"

    phase = amd.get("phase", "")
    phase_map = {
        "accumulation": "Accumulation (انباشت)",
        "manipulation": "Manipulation (دستکاری)",
        "distribution": "Distribution (توزیع)",
        "ranging": "Ranging (رنج)",
    }
    phase_fa = phase_map.get(phase, "تحلیل شده")

    news = get_all_news()
    news_line = "خبر مهمی در دسترس نیست."
    if news:
        news_line = news[0]["title"][:140]

    change_emoji = "📈" if change_24h >= 0 else "📉"
    change_sign = "+" if change_24h >= 0 else ""

    parts = []
    parts.append("📈 <b>تحلیل ViaChart | " + symbol + "/USDT</b> (" + tf + ")")
    parts.append("")
    parts.append("🎯 امتیاز تحلیلی: <b>" + str(score) + "/100</b> " + score_label)
    parts.append("")
    parts.append("━━━━━━━━━━━━━━━")
    parts.append("📊 <b>وضعیت فعلی</b>")
    parts.append("━━━━━━━━━━━━━━━")
    parts.append("💰 قیمت: <b>" + _fmt(price) + "</b>")
    parts.append(change_emoji + " تغییر ۲۴ ساعت: <b>" + change_sign + f"{change_24h:.2f}%</b>")
    parts.append("📊 RSI: <b>" + f"{rsi:.1f}" + "</b> | فاز: " + phase_fa)
    parts.append("")
    parts.append("━━━━━━━━━━━━━━━")
    parts.append("🎯 <b>نقاط کلیدی</b>")
    parts.append("━━━━━━━━━━━━━━━")
    parts.append("✅ ورود (Entry): <b>" + _fmt(entry) + "</b>")
    parts.append("🛑 حد ضرر (SL): <b>" + _fmt(sl) + "</b> (" + _pct(entry, sl) + ")")
    parts.append("")
    parts.append("🎯 <b>اهداف:</b>")
    parts.append("   🔸 TP1: <b>" + _fmt(tp1) + "</b> (" + _pct(entry, tp1) + ")")
    parts.append("   🔸 TP2: <b>" + _fmt(tp2) + "</b> (" + _pct(entry, tp2) + ")")
    parts.append("   🔸 TP3: <b>" + _fmt(tp3) + "</b> (" + _pct(entry, tp3) + ")")
    parts.append("")
    parts.append("━━━━━━━━━━━━━━━")
    parts.append("💡 <b>چرا این سیگنال؟</b>")
    parts.append("━━━━━━━━━━━━━━━")
    parts.append(reason_lines.rstrip())
    parts.append("")
    parts.append("━━━━━━━━━━━━━━━")
    parts.append("📰 <b>خبر مهم</b>")
    parts.append("━━━━━━━━━━━━━━━")
    parts.append(news_line)
    parts.append("")
    parts.append("━━━━━━━━━━━━━━━")
    parts.append("🛡️ مدیریت ریسک: حداکثر ۱٪ در هر معامله")
    parts.append("⚠️ توصیه مالی نیست — DYOR")
    parts.append("")
    parts.append("📢 " + CHANNEL_HANDLE)
    parts.append("")
    parts.append("#ViaChart #" + symbol + " #" + full_name + " #Crypto #Signal #Analysis #Trading")

    return "\n".join(parts)


# ============================================================
# قالب خبر: وضعیت بازار + ۲ خبر
# ============================================================

def build_news_post(news_list):
    from data_fetcher import get_top_symbols, get_fear_greed_index

    # --- وضعیت بازار ---
    btc = None
    eth = None
    try:
        top = get_top_symbols(limit=10)
        for c in top:
            if c["symbol"] == "BTCUSDT":
                btc = c
            elif c["symbol"] == "ETHUSDT":
                eth = c
    except Exception as e:
        log.warning(f"خطا در وضعیت بازار: {e}")

    fng_value = 50
    fng_label_en = "Neutral"
    try:
        fng = get_fear_greed_index()
        fng_value = fng["value"]
        fng_label_en = fng["label"]
    except Exception as e:
        log.warning(f"خطا در ترس و طمع: {e}")

    fng_map = {
        "Extreme Fear": "ترس شدید",
        "Fear": "ترس",
        "Neutral": "خنثی",
        "Greed": "طمع",
        "Extreme Greed": "طمع شدید",
    }
    fng_fa = fng_map.get(fng_label_en, fng_label_en)

    def trend_emoji(change):
        if change > 3:
            return "🚀"
        elif change > 0:
            return "📈"
        elif change > -3:
            return "📉"
        else:
            return "🔻"

    if btc:
        e = trend_emoji(btc["change_24h"])
        s = "+" if btc["change_24h"] >= 0 else ""
        btc_line = "₿ BTC: <b>$" + f"{btc['price']:,.0f}" + "</b> " + e + " " + s + f"{btc['change_24h']:.2f}%"
    else:
        btc_line = "₿ BTC: —"

    if eth:
        e = trend_emoji(eth["change_24h"])
        s = "+" if eth["change_24h"] >= 0 else ""
        eth_line = "Ξ ETH: <b>$" + f"{eth['price']:,.0f}" + "</b> " + e + " " + s + f"{eth['change_24h']:.2f}%"
    else:
        eth_line = "Ξ ETH: —"

    # --- انتخاب ۲ خبر ---
    keywords = ["bitcoin", "btc", "ethereum", "eth", "etf", "sec",
                "market", "fed", "whale", "liquidity", "regulation"]

    relevant = []
    for n in news_list:
        title_lower = n["title"].lower()
        if any(k in title_lower for k in keywords):
            relevant.append(n)
        if len(relevant) >= 2:
            break

    if not relevant:
        relevant = news_list[:2]

    # --- ترجمه ---
    news_lines = []
    for n in relevant[:2]:
        en = n["title"][:130]
        fa = _translate_to_farsi(en)
        news_lines.append("▫️ <b>" + en + "</b>")
        news_lines.append(fa)
        news_lines.append("")

    news_part = "\n".join(news_lines).rstrip()

    parts = []
    parts.append("🔔 <b>وضعیت بازار کریپتو | Market Update</b>")
    parts.append("")
    parts.append("━━━━━━━━━━━━━━━")
    parts.append("💰 <b>وضعیت لحظه‌ای</b>")
    parts.append("━━━━━━━━━━━━━━━")
    parts.append(btc_line)
    parts.append(eth_line)
    parts.append("😱 شاخص ترس و طمع: <b>" + str(fng_value) + "</b> (" + fng_fa + ")")
    parts.append("")
    parts.append("━━━━━━━━━━━━━━━")
    parts.append("📰 <b>اخبار مهم</b>")
    parts.append("━━━━━━━━━━━━━━━")
    parts.append(news_part)
    parts.append("")
    parts.append("━━━━━━━━━━━━━━━")
    parts.append("📢 " + CHANNEL_HANDLE)
    parts.append("")
    parts.append("#ViaChart #Crypto #Bitcoin #Market #News")

    return "\n".join(parts)


# ============================================================
# ارسال به کانال
# ============================================================

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


# ============================================================
# توابع اصلی (post_signal / post_news)
# ============================================================

async def post_signal(analysis_data, chart_path):
    log.info(f"📝 ساخت پست سیگنال برای {analysis_data['symbol']}...")
    post = build_signal_post(analysis_data)
    log.info(f"\n{post}\n")
    return await send_post(post, chart_path=chart_path)


async def post_news():
    log.info("📰 ساخت پست وضعیت بازار + اخبار...")
    news = get_all_news()
    post = build_news_post(news)
    if post:
        log.info(f"\n{post}\n")
        return await send_post(post, chart_path=None)
    return False


# ============================================================
# تست
# ============================================================

if __name__ == "__main__":
    import asyncio

    async def test():
        print("\n🧪 تست telegram_poster...\n")
        await post_news()

    asyncio.run(test())