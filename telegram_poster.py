"""
ساخت و ارسال پست حرفه‌ای به کانال تلگرام ViaChart
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

    post = (
        "📈 <b>تحلیل ViaChart | " + symbol + "/USDT</b> (" + tf + ")\n\n"
        "🎯 امتیاز تحلیلی: <b>" + str(score) + "/100</b> " + score_label + "\n\n"
        "━━━━━━━━━━━━━━━\n"
        "📊 <b>وضعیت فعلی</b>\n"
        "━━━━━━━━━━━━━━━\n"
        "💰 قیمت: <b>" + _fmt(price) + "</b>\n"
        + change_emoji + " تغییر ۲۴ ساعت: <b>" + change_sign + f"{change_24h:.2f}" + "%</b>\n"
        "📊 RSI: <b>" + f"{rsi:.1f}" + "</b> | فاز: " + phase_fa + "\n\n"
        "━━━━━━━━━━━━━━━\n"
        "🎯 <b>نقاط کلیدی</b>\n"
        "━━━━━━━━━━━━━━━\n"
        "✅ ورود (Entry): <b>" + _fmt(entry) + "</ TPb>\n"
        "🛑 حد ضرر (SL): <b>" + _fmt(sl) + "</2b> (" + _pct(entry, sl) + ")\n\n"
        "🎯 <b>:اهداف:</b>\n"
        "   🔸 TP1: <b>" + _fmt(t <p1) + "</b> (" + _pct(entry, tp1) + ")\n"
        "   🔸b>" + _fmt(tp2) + "</b> (" + _pct(entry, tp2) + ")\n"
        "   🔸 TP3: <b>" + _fmt(tp3) + "</b> (" + _pct(entry, tp3) + ")\n\n"
        "━━━━━━━━━━━━━━━\n"
        "💡 <b>چرا این سیگنال؟</b>\n"
        "━━━━━━━━━━━━━━━\n"
        + reason_lines + "\n"
        "━━━━━━━━━━━━━━━\n"
        "📰 <b>خبر مهم</b>\n"
        "━━━━━━━━━━━━━━━\n"
        + news_line + "\n\n"
        "━━━━━━━━━━━━━━━\n"
        "🛡️ مدیریت ریسک: حداکثر ۱٪ در هر معامله\n"
        "⚠️ توصیه مالی نیست — DYOR\n\n"
        "📢 " + CHANNEL_HANDLE + "\n\n"
        "#ViaChart #" + symbol + " #" + full_name + " #Crypto #Signal #Analysis #Trading"
    )

    return post.strip()


# ============================================================
# قالب خبر: وضعیت بازار + ۲ خبر مهم
# ============================================================

def build_news_post(news_list):
    """ساخت پست وضعیت بازار + ۲ خبر مهم"""
    from data_fetcher import get_top_symbols, get_fear_greed_index

    router = LLMRouter()

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
        log.warning(f"خطا در دریافت وضعیت بازار: {e}")

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
        btc_line = "₿ BTC: <b>$" + f"{btc['price']:,.0f}" + "</b> " + e + " " + s + f"{btc['change_24h']:.2f}" + "%"
    else:
        btc_line = "₿ BTC: داده‌ای موجود نیست"

    if eth:
        e = trend_emoji(eth["change_24h"])
        s = "+" if eth["change_24h"] >= 0 else ""
        eth_line = "Ξ ETH: <b>$" + f"{eth['price']:,.0f}" + "</b> " + e + " " + s + f"{eth['change_24h']:.2f}" + "%"
    else:
        eth_line = "Ξ ETH: داده‌ای موجود نیست"

    # --- انتخاب ۲ خبر مهم ---
    keywords = ["bitcoin", "btc", "ethereum", "eth", "etf", "sec", "market",
                "fed", "rate", "inflation", "whale", "liquidity", "regulation",
                "binance", "coinbase", "solana"]

    relevant = []
    for n in news_list:
        title_lower = n["title"].lower()
        if any(k in title_lower for k in keywords):
            relevant.append(n)
        if len(relevant) >= 2:
            break

    if not relevant:
        relevant = news_list[:2]

    news_text = ""
    for i, n in enumerate(relevant, 1):
        news_text += str(i) + ". " + n["title"][:140] + "\n"

    # --- ترجمه با LLM ---
    system = (
        "You are a bilingual crypto news editor for ViaChart. "
        "Write in English and Persian (Farsi) ONLY. NEVER Arabic. "
        "Be extremely concise. Output only the final post."
    )

    prompt = (
        "این ۲ خبر رو به فارسی روان ترجمه کن:\n\n"
        + news_text + "\n\n"
        "مثال دقیق خروجی (بدون placeholder):\n\n"
        "▫️ <b>Bitcoin ETF sees record weekly inflows.</b>\n"
        "ورودی هفتگی رکوردی به ETF بیت‌کوین ثبت شد.\n\n"
        "▫️ <b>SEC delays spot ETF decision.</b>\n"
        "کمیسیون SEC تصمیم درباره ETF اسپات را به تعویق انداخت.\n\n"
        "قواعد قطعی:\n"
        "- دقیقاً ۲ خبر (نه بیشتر)\n"
        "- هر خبر: یک خط انگلیسی با <b> + یک خط فارسی زیرش\n"
        "- فارسی روان (نه عربی، نه کلمه به کلمه)\n"
        "- هیچ placeholder، براکت []، Note، توضیح اضافه نکن\n"
        "- هر خط زیر ۱۲ کلمه"
    )

    news_part = router.generate(prompt, system=system, max_tokens=400).strip()

    # --- پاک‌سازی ---
    bad_markers = [
        "[English", "[Farsi", "[فارسی", "[ترجمه",
        "Note:", "توجه:", "Please note", "Placeholder",
        "ترجمه فارسی با استفاده",
    ]
    clean_lines = []
    for line in news_part.split("\n"):
        skip = False
        for m in bad_markers:
            if m in line:
                skip = True
                break
        if not skip:
            clean_lines.append(line)

    news_part = "\n".join(clean_lines).strip()

    # --- پست نهایی ---
    post = (
        "🔔 <b>وضعیت بازار کریپتو | Market Update</b>\n\n"
        "━━━━━━━━━━━━━━━\n"
        "💰 <b>وضعیت لحظه‌ای</b>\n"
        "━━━━━━━━━━━━━━━\n"
        + btc_line + "\n"
        + eth_line + "\n"
        + "😱 شاخص ترس و طمع: <b>" + str(fng_value) + "</b> (" + fng_fa + ")\n\n"
        "━━━━━━━━━━━━━━━\n"
        "📰 <b>اخبار مهم</b>\n"
        "━━━━━━━━━━━━━━━\n"
        + news_part + "\n\n"
        "━━━━━━━━━━━━━━━\n"
        "📢 " + CHANNEL_HANDLE + "\n\n"
        "#ViaChart #Crypto #Bitcoin #Market #News"
    )

    return post.strip()


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
# توابع راحتی
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