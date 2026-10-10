"""
ساخت و ارسال پست حرفه‌ای به کانال تلگرام ViaChart
قالب: بخش‌بندی شده، سئو-فرندلی، حرفه‌ای
"""
import os
import logging
from datetime import datetime, timezone

from telegram import Bot, InputFile
from telegram.constants import ParseMode

from llm_router import LLMRouter
from news import get_all_news, format_news_for_llm

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')
log = logging.getLogger(__name__)

CHANNEL_ID = os.environ.get("TELEGRAM_CHANNEL_ID", "@viachart_app")
CHANNEL_HANDLE = "@viachart_app"


# ============================================================
# ابزارها
# ============================================================

def _fmt(p):
    """فرمت قیمت بر اساس بزرگی عدد"""
    if p >= 1000:
        return f"${p:,.2f}"
    elif p >= 1:
        return f"${p:,.4f}"
    elif p >= 0.01:
        return f"${p:.4f}"
    else:
        return f"${p:.6f}"


def _pct(from_p, to_p):
    """درصد تغییر"""
    if from_p == 0:
        return "0.0%"
    change = ((to_p - from_p) / from_p) * 100
    sign = "+" if change >= 0 else ""
    return f"{sign}{change:.1f}%"


def _full_name(symbol):
    """نام کامل کوین برای هشتگ"""
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
# قالب ثابت پست سیگنال
# ============================================================

def build_signal_post(a):
    """
    ساخت پست سیگنال با قالب ثابت حرفه‌ای
    a = analysis data (خروجی score_coin)
    """
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

    # سطوح
    entry = price
    tp1 = price + atr_val * 1.5
    tp2 = price + atr_val * 3.0
    tp3 = price + atr_val * 5.0

    # امتیاز کیفی
    if score >= 70:
        score_label = "🔥 قوی"
    elif score >= 50:
        score_label = "🟢 متوسط"
    elif score >= 30:
        score_label = "🟡 ضعیف"
    else:
        score_label = "⚪ کم"

    # دلایل
    reason_lines = ""
    for r in reasons[:3]:
        reason_lines += f"🔹 {r}\n"
    if not reason_lines:
        reason_lines = "🔹 تحلیل تکنیکال در حال شکل‌گیری\n"

    # فاز AMD
    phase = amd.get("phase", "")
    phase_fa = {
        "accumulation": "Accumulation (انباشت)",
        "manipulation": "Manipulation (دستکاری)",
        "distribution": "Distribution (توزیع)",
        "ranging": "Ranging (رنج)",
    }.get(phase, "تحلیل شده")

    # خبر
    news = get_all_news()
    news_line = "خبر مهمی در دسترس نیست."
    if news:
        news_line = news[0]["title"][:140]

    # ایموجی تغییر
    change_emoji = "📈" if change_24h >= 0 else "📉"
    change_sign = "+" if change_24h >= 0 else ""

    post = f"""📈 **تحلیل ViaChart | {symbol}/USDT** ({tf})

🎯 امتیاز تحلیلی: **{score}/100** {score_label}

━━━━━━━━━━━━━━━
📊 **وضعیت فعلی**
━━━━━━━━━━━━━━━
💰 قیمت: **{_fmt(price)}**
{change_emoji} تغییر ۲۴ ساعت: **{change_sign}{change_24h:.2f}%**
📊 RSI: **{rsi:.1f}** | فاز: {phase_fa}

━━━━━━━━━━━━━━━
🎯 **نقاط کلیدی**
━━━━━━━━━━━━━━━
✅ ورود (Entry): **{_fmt(entry)}**
🛑 حد ضرر (SL): **{_fmt(sl)}** ({_pct(entry, sl)})

🎯 **اهداف:**
   🔸 TP1: **{_fmt(tp1)}** ({_pct(entry, tp1)})
   🔸 TP2: **{_fmt(tp2)}** ({_pct(entry, tp2)})
   🔸 TP3: **{_fmt(tp3)}** ({_pct(entry, tp3)})

━━━━━━━━━━━━━━━
💡 **چرا این سیگنال؟**
━━━━━━━━━━━━━━━
{reason_lines}
━━━━━━━━━━━━━━━
📰 **خبر مهم**
━━━━━━━━━━━━━━━
{news_line}

━━━━━━━━━━━━━━━
🛡️ مدیریت ریسک: حداکثر ۱٪ در هر معامله
⚠️ توصیه مالی نیست — DYOR

📢 {CHANNEL_HANDLE}

#ViaChart #{symbol} #{full_name} #Crypto #Signal #Analysis #Altcoins #Trading"""

    return post.strip()


# ============================================================
# قالب پست خبری
# ============================================================

def build_news_post(news_list):
    """ساخت پست خبری با قالب ثابت"""
    if not news_list:
        return None

    lines = ["🔔 **اخبار مهم کریپتو | Top Crypto News**\n"]

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
    """ارسال پست به کانال"""
    bot = Bot(token=os.environ["TELEGRAM_BOT_TOKEN"])

    try:
        if chart_path and os.path.exists(chart_path):
            # اگه متن زیر ۱۰۲۴ کاراکتره، همه رو تو کپشن بذار
            if len(text) <= 1024:
                with open(chart_path, "rb") as f:
                    await bot.send_photo(
                        chat_id=CHANNEL_ID,
                        photo=InputFile(f),
                        caption=text,
                        parse_mode=ParseMode.MARKDOWN,
                        disable_notification=disable_notification,
                    )
                log.info("✅ پست با عکس (تک پیام) ارسال شد")
            else:
                # متن طولانی: عکس با کپشن کوتاه، بعد متن کامل
                with open(chart_path, "rb") as f:
                    await bot.send_photo(
                        chat_id=CHANNEL_ID,
                        photo=InputFile(f),
                        caption=text[:1024],
                        parse_mode=ParseMode.MARKDOWN,
                        disable_notification=disable_notification,
                    )
                await bot.send_message(
                    chat_id=CHANNEL_ID,
                    text=text[1024:4096],
                    parse_mode=ParseMode.MARKDOWN,
                    disable_notification=True,
                )
                log.info("✅ پست با عکس + ادامه ارسال شد")
        else:
            await bot.send_message(
                chat_id=CHANNEL_ID,
                text=text[:4096],
                parse_mode=ParseMode.MARKDOWN,
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
    """ساخت و ارسال پست سیگنال"""
    log.info(f"📝 ساخت پست سیگنال برای {analysis_data['symbol']}...")
    post = build_signal_post(analysis_data)
    log.info(f"\n{post}\n")
    return await send_post(post, chart_path=chart_path)


async def post_news():
    """ساخت و ارسال پست خبری"""
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