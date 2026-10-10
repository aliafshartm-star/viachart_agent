"""
تست اتصال به سرویس‌های ViaChart Agent
"""
import os
import asyncio
from telegram import Bot
from groq import Groq
import google.generativeai as genai


async def test_telegram():
    """تست اتصال به تلگرام"""
    print("🔍 تست تلگرام...")
    try:
        bot = Bot(token=os.environ["TELEGRAM_BOT_TOKEN"])
        me = await bot.get_me()
        print(f"   ✅ بات: @{me.username}")

        # ارسال پیام تست به کانال
        await bot.send_message(
            chat_id=os.environ["TELEGRAM_CHANNEL_ID"],
            text="🤖 تست اتصال ViaChart Agent\n\nاگه این پیام رو می‌بینی، یعنی زیرساخت آماده‌ست! ✅"
        )
        print("   ✅ پیام تست به کانال ارسال شد")
        return True
    except Exception as e:
        print(f"   ❌ خطا: {e}")
        return False


def test_groq():
    """تست اتصال به Groq"""
    print("🔍 تست Groq...")
    try:
        client = Groq(api_key=os.environ["GROQ_API_KEY"])
        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "user", "content": "فقط بنویس: OK"}],
            max_tokens=10,
        )
        print(f"   ✅ Groq پاسخ داد: {response.choices[0].message.content}")
        return True
    except Exception as e:
        print(f"   ❌ خطا: {e}")
        return False


def test_gemini():
    """تست اتصال به Gemini"""
    print("🔍 تست Gemini...")
    try:
        genai.configure(api_key=os.environ["GEMINI_API_KEY"])
        model = genai.GenerativeModel("gemini-2.5-flash")
        response = model.generate_content("فقط بنویس: OK")
        print(f"   ✅ Gemini پاسخ داد: {response.text}")
        return True
    except Exception as e:
        print(f"   ❌ خطا: {e}")
        return False


async def main():
    print("=" * 50)
    print("🚀 تست اتصال ViaChart Agent")
    print("=" * 50)

    tg_ok = await test_telegram()
    print()
    groq_ok = test_groq()
    print()
    gemini_ok = test_gemini()

    print()
    print("=" * 50)
    print("📊 نتیجه نهایی:")
    print(f"   تلگرام: {'✅' if tg_ok else '❌'}")
    print(f"   Groq:   {'✅' if groq_ok else '❌'}")
    print(f"   Gemini: {'✅' if gemini_ok else '❌'}")
    print("=" * 50)


if __name__ == "__main__":
    asyncio.run(main())