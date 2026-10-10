"""
ساخت و ارسال پست حرفه‌ای به کانال تلگرام ViaChart
- قالب سیگنال: بخش‌بندی شده، حرفه‌ای
- قالب خبر: وضعیت بازار + ۲ خبر مهم (دوزبانه)
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


# ============================================================
# ابزارها
# ============================================================

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
        reason_lines += f"🔹 {r}\n"
    if not reason_lines:
        reason_lines = "🔹 تحلیل تکنیکال در حال شکل‌گیری\n"

    phase = amd.get("phase", "")
    phase_fa = {
        "accumulation": "Accumulation (انباشت)",
        "manipulation": "Manipulation (دستکاری)",
        "distribution": "Distribution (توزیع)",
        "ranging": "Ranging (رنج)",
    }.get(phase, "تحلیل شده")

    news = get_all_news()
    news_line = "خبر مهمی در دسترس نیست."
    if news:
        news_line = news[0]["title"][:140]

    change_emoji = "📈" if change_24h >= 0 else "📉"
    change_sign = "+" if change_24h >= 0 else ""

    post = f"""📈 <b>تحلیل ViaChart | {symbol}/USDT</b> ({tf})

🎯 امتیاز تحلیلی: <b>{score}/100</b> {score_label}

━━━━━━━━━━━━━━━
📊 <b>وضعیت فعلی</b>
━━━━━━━━━━━━━━━
💰 قیمت: <b>{_fmt(price)}</b>
{change_emoji} تغییر ۲۴ ساعت: <b>{change_sign}{change_24h:.2f}%</b>
📊 RSI: <b>{rsi:.1f}</b> | فاز: {phase_fa}

━━━━━━━━━━━━━━━
🎯 <b>نقاط کلیدی</b>
━━━━━━━━━━━━━━━
✅ ورود (Entry): <b>{_fmt(entry)}</b>
🛑 حد ضرر (SL): <b>{_fmt(sl)}</b> ({_pct(entry, sl)})

🎯 <b>اهداف:</b>
   🔸 TP1: <b>{_fmt(tp1)}</b> ({_pct(entry, tp1)})
   🔸 TP2: <b>{_fmt(tp2)}</b> ({_pct(entry, tp2)})
   🔸 TP3: <b>{_fmt(tp3)}</b> ({_pct(entry, tp3)})

━━━━━━━━━━━━━━━
💡 <b>چرا این سیگنال؟</b>
━━━━━━━━━━━━━━━
{reason_lines}
━━━━━━━━━━━━━━━
📰 <b>خبر مهم</b>
━━━━━━━━━━━━━━━
{news_line}

━━━━━━━━━━━━━━━
🛡️ مدیریت ریسک: حداکثر ۱٪ در هر معامله
⚠️ توصیه مالی نیست — DYOR

📢 {CHANNEL_HANDLE}

#ViaChart #{symbol} #{full_name} #Crypto #Signal #Analysis #Trading"""

    return post.strip()


# ============================================================
# قالب خبر: وضعیت بازار + ۲ خبر مهم
# ============================================================

def build_news_post(news_list):
    """
    ساخت پست خلاصه وضعیت بازار + ۲ خبر مهم
    """
    from data_fetcher import get_top_symbols, get_fear_greed_index

    router = LLMRouter()

    # --- ۱. وضعیت بازار ---
    try:
        top = get_top_symbols(limit=10)
        btc = next((c for c in top if c["symbol"] == "BTCUSDT"), None)
        eth = next((c for c in top if c["symbol"] == "ETHUSDT"), None)
    except Exception:
        btc, eth = None, None

    try:
        fng = get_fear_greed_index()
    except Exception:
        fng = {"value": 50, "label": "Neutral"}

    fng_fa = {
        "Extreme Fear": "ترس شدید",
        "Fear": "ترس",
        "Neutral": "خنثی",
        "Greed": "طمع",
        "Extreme Greed": "طمع شدید",
    }.get(fng["label"], fng["label"])

    def trend_emoji(change):
        if change > 3:
            return "🚀"
        elif change > 0:
            return "📈"
        elif change > -3:
            return "📉"
        else:
            return "🔻"

    btc_line = "₿ BTC: داده‌ای موجود نیست"
    if btc:
        e = trend_emoji(btc["change_24h"])
        s = "+" if btc["change_24h"] >= 0 else ""
        btc_line = f"₿ BTC: <b>${btc['price']:,.0f}</b> {e} {s}{btc['change_24h']:.2f}%"

    eth_line = "Ξ ETH: داده‌ای موجود نیست"
    if eth:
        e = trend_emoji(eth["change_24h"])
        s = "+" if eth["change_24h"] >= 0 else ""
        eth_line = f"Ξ ETH: <b>${eth['price']:,.0f}</b> {e} {s}{eth['change_24h']:.2f}%"

    # --- ۲. انتخاب ۲ خبر مهم مرتبط با بازار ---
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
        news_text += f"{i}. {n['title'][:140]}\n"

    # --- ۳. ترجمه ۲ خبر با LLM ---
    system = (
        "You are a bilingual crypto news editor for ViaChart. "
        "You write in English and Persian (Farsi) ONLY. NEVER Arabic. "
        "Be extremely concise and professional. Output only the final post."
    )

    prompt = f"""این ۲ خبر رو به فارسی روان ترجمه کن:

{news_text}

مثال دقیق خروجی که باید تولید کنی (بدون هیچ placeholder):

▫️ <b>Bitcoin ETF sees record weekly inflows.</b>
ورودی هفتگی رکوردی به ETF بیت‌کوین ثبت شد.

▫️ <b>SEC delays spot ETF decision.</b>
کمیسیون SEC تصمیم درباره ETF اسپات را به تعویق انداخت.

قواعد قطعی:
- دقیقاً ۲ خبر (نه بیشتر)
- هر خبر: یک خط انگلیسی (با <b>) + یک خط فارسی زیرش
- فارسی روان و خبری (نه عربی، نه کلمه به کلمه)
- هیچ placeholder، براکت []، Note، توضیح، تذکر اضافه نکن
- هر خط زیر ۱۲ کلمه"""

    news_part = router.generate(prompt, system=system, max_tokens=400).strip()

    # پاک‌سازی
    bad_markers = [
        "[English", "[Farsi", "[فارسی", "[ترجمه",
        "Note:", "توجه:", "Please note", "Placeholder",
        "ترجمه فارسی با استفاده",
    ]
    clean_lines = []
    for import line in news_part.split("\n"):
        if any(m in line for m in bad_markers generate):
            continue
        clean_lines.append(line)
    news_part = "\n".join(clean_lines).strip()

   _ch # --- ۴. پست نهایی ---
    post = f"""🔔 <b>وضعیت بازار کartریپتو | Market Update</b>

━━━━━━━━━━━━━━━
💰 <b>وضعیت لحظه‌ای</b>
━━━━━━━━━━━━━━━
{btc_line}
{eth_line}
😱 شاخص ترس و طمع: <b>{fng['value']}</b> ({fng_fa})

━━━━━━━━━━━━━━━
📰 <b>اخبار مهم</b>
━━━━━━━━━━━━━━━
{news_part}

━━━━━━━━━━━━━━━
📢 {CHANNEL_HANDLE}

#ViaChart #Crypto #Bitcoin #Market #News"""

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
    from data_fetcher import get_klines
    from analysis import candles_to_df, score_coin
    from chart_generator

    async def test():
        print("\n🧪 تست telegram_poster...\n")

        # فقط پست خبری
        print("📤 ارسال پست خبری...")
        await post_news()

    asyncio.run(test())