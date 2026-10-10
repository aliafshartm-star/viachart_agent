"""
ساخت و ارسال پست حرفه‌ای به کانال تلگرام
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


# ============================================================
# ساخت پست سیگنال
# ============================================================

def build_signal_post(analysis_data, news_text=""):
    """
    با کمک LLM یه پست حرفه‌ای دوزبانه می‌سازه
    """
    router = LLMRouter()

    symbol = analysis_data["symbol"]
    price = analysis_data["price"]
    score = analysis_data["score"]
    rsi = analysis_data.get("rsi", 0)
    sl = analysis_data.get("stop_loss", 0)
    vp = analysis_data.get("volume_profile", {})
    amd = analysis_data.get("amd", {})
    reasons = analysis_data.get("reasons", [])

    system = (
        "You are a professional crypto analyst writing for the ViaChart Persian/English Telegram channel. "
        "Write concise, professional, and trader-friendly posts. "
        "Use English for numbers and tickers, Persian for explanations."
    )

    prompt = f"""
اطلاعات زیر را به یک پست تلگرامی حرفه‌ای دوزبانه (فارسی + English) تبدیل کن.

📊 **داده‌های تحلیل {symbol}:**
- قیمت فعلی: ${price:,.4f}
- امتیاز: {score}/100
- RSI: {rsi}
- حد ضرر (SL): ${sl:,.4f}
- POC: ${vp.get('poc', 0):,.4f}
- VAH: ${vp.get('vah', 0):,.4f}
- VAL: ${vp.get('val', 0):,.4f}
- فاز AMD: {amd.get('phase', 'N/A')} — {amd.get('reason', '')}
- دلایل: {', '.join(reasons) if reasons else 'ندارد'}

📰 **اخبار مهم بازار:**
{news_text[:800] if news_text else 'خبر مهمی نیست.'}

**ساختار پست:**

1. یک جمله جذاب انگلیسی + ترجمه فارسی به عنوان تیتر با ایموجی مناسب
2. **سناریو (Scenario):** دو سه خط توضیح چرا این ارز پتانسیل داره
3. **نقاط کلیدی (Key Levels):**
   - ورود (Entry)
   - حد ضرر (SL)
   - اهداف (Targets) — سه سطح منطقی پیشنهاد بده
4. **اخبار مهم:** یک یا دو خط خبر مرتبط
5. پایان با disclaimer: "این تحلیل توصیه مالی نیست."

**قالب نهایی:**
- از ایموجی استفاده کن
- اعداد رو bold کن با *
- تیتر انگلیسی + زیرش فارسی
- فارسی روان و حرفه‌ای بنویس

خروجی رو **فقط** به صورت متن پست آماده بده، بدون توضیح اضافی.
"""

    post = router.generate(prompt, system=system, max_tokens=1500)
    return post.strip()


# ============================================================
# ساخت پست خبری
# ============================================================

def build_news_post(news_list):
    """ساخت یه پست خبری خلاصه از اخبار مهم"""
    if not news_list:
        return None

    router = LLMRouter()
    news_text = format_news_for_llm(news_list, max_items=10)

    system = (
        "You are a crypto news editor for the ViaChart Persian/English Telegram channel. "
        "Summarize important news into short, engaging posts."
    )

    prompt = f"""
از بین اخبار زیر، ۳ تا ۵ خبر **مهم** رو انتخاب کن و به یک پست تلگرامی دوزبانه (فارسی + English) تبدیل کن.

📰 **اخبار:**
{news_text}

**ساختار:**
- تیتر: "🔔 اخبار مهم کریپتو | Top Crypto News"
- هر خبر: یک خط انگلیسی خلاصه + یک خط فارسی + ایموجی مرتبط
- آخرش: هشتگ‌های مرتبط

**قواعد:**
- خبرای مهم‌تر (BTC, ETH, ETF, SEC, whale) رو اول بذار
- فارسی روان و خلاصه
- حداکثر ۵ خبر

خروجی رو **فقط** به صورت متن پست آماده بده.
"""

    post = router.generate(prompt, system=system, max_tokens=1000)
    return post.strip()


# ============================================================
# ارسال به کانال
# ============================================================

async def send_post(text, chart_path=None, disable_notification=False):
    """ارسال پست به کانال (با یا بدون چارت)"""
    bot = Bot(token=os.environ["TELEGRAM_BOT_TOKEN"])

    try:
        if chart_path and os.path.exists(chart_path):
            with open(chart_path, "rb") as f:
                await bot.send_photo(
                    chat_id=CHANNEL_ID,
                    photo=InputFile(f),
                    caption=text[:1024],  # کپشن تلگرام حداکثر ۱۰۲۴ کاراکتر
                    parse_mode=ParseMode.MARKDOWN,
                    disable_notification=disable_notification,
                )
            log.info(f"✅ پست با عکس ارسال شد: {chart_path}")

            # اگه متن طولانی‌تر از ۱۰۲۴ کاراکتره، ادامه رو تو پیام بعدی بفرست
            if len(text) > 1024:
                await bot.send_message(
                    chat_id=CHANNEL_ID,
                    text=text[1024:],
                    parse_mode=ParseMode.MARKDOWN,
                    disable_notification=disable_notification,
                )
        else:
            # بدون عکس
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
# پست کردن سیگنال (کامل)
# ============================================================

async def post_signal(analysis_data, chart_path):
    """ساخت و ارسال پست سیگنال"""
    log.info(f"📝 ساخت پست سیگنال برای {analysis_data['symbol']}...")

    news = get_all_news()
    news_text = format_news_for_llm(news, max_items=5)

    post = build_signal_post(analysis_data, news_text)
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

        # تحلیل BTC
        candles = get_klines("BTCUSDT", "4h", 200)
        df = candles_to_df(candles)
        info = {"change_24h": 0, "volume_24h": 0}
        analysis = score_coin(df, "BTCUSDT", info)

        # چارت
        chart = generate_chart("BTCUSDT", "4h", 150, score_data=analysis)

        # ارسال پست سیگنال
        print("\n📤 ارسال پست سیگنال...")
        await post_signal(analysis, chart)

        print("\n📤 ارسال پست خبری...")
        await post_news()

    asyncio.run(test())