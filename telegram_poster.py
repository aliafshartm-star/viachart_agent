"""
ساخت و ارسال پست حرفه‌ای به کانال تلگرام ViaChart
استفاده از HTML به جای Markdown برای پایداری بیشتر
"""
import os
import logging

from telegram import Bot, InputFile
from telegram.constants import ParseMode

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
# قالب سیگنال (HTML)
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

    # استفاده از <b> به جای **
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
# قالب خبری (HTML)
# ============================================================

def build_news_post(news_list):
    if not news_list:
        return None

    lines = ["🔔 <b>اخبار مهم کریپتو | Top Crypto News</b>\n"]

    for n in news_list[:5]:
        title = n["title"][:130]
        source = n.get("source", "Crypto")
        lines.append(f"▫️ {title}\n   ─ {source}\n")

    lines.append(f"📢 {CHANNEL_HANDLE}\n")
    lines.append("#ViaChart #Crypto #News #Blockchain")

    return "\n".join(lines)


# ============================================================
# ارسال به کانال
# ============================================================

async def send_post(text, chart_path=None, disable_notification=False):
    bot = Bot(token=os.environ["TELEGRAM_BOT_TOKEN"])

    try:
        if chart_path and os.path.exists(chart_path):
            # عکس با کپشن (کپشن محدود به ۱۰۲۴ کاراکتر)
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

            # اگه متن طولانی‌تر بود، ادامه رو تو پیام بعدی
            if len(text) > 1024:
                await bot.send_message(
                    chat_id=CHANNEL_ID,
                    text=text[1024:],
                    parse_mode=ParseMode.HTML,
                    disable_notification=True,
                )
        else:
            # فقط متن
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
    log.info("📰 ساخت پست خبری...")
    news = get_all_news()
    post = build_news_post(news)
    if post:
        return await send_post(post, chart_path=None)
    return False


# ============================================================
# تست
# ============================================================

if __name__ == "__main__":
    import asyncio
    from data_fetcher import get_klines
    from analysis import candles_to_df, score_coin
    from chart_generator import generate_chart

    async def test():
        print("\n🧪 تست telegram_poster...\n")

        candles = get_klines("BTCUSDT", "4h", 200)
        df = candles_to_df(candles)
        info = {"change_24h": -1.2, "volume_24h": 0}
        analysis = score_coin(df, "BTCUSDT", info)
        analysis["interval"] = "4H"

        chart = generate_chart("BTCUSDT", "4h", 150, score_data=analysis)

        print("\n📤 ارسال پست سیگنال...")
        await post_signal(analysis, chart)

        print("\n📤 ارسال پست خبری...")
        await post_news()

    asyncio.run(test())