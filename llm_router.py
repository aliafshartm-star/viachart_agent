"""
مسیریاب هوشمند بین Groq و Gemini با fallback خودکار
"""
import os
import logging
from groq import Groq
import google.generativeai as genai

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')
log = logging.getLogger(__name__)


class LLMRouter:
    """مسیریاب بین Groq و Gemini"""

    def __init__(self):
        self.groq_client = Groq(api_key=os.environ["GROQ_API_KEY"])
        genai.configure(api_key=os.environ["GEMINI_API_KEY"])
        self.gemini_model = genai.GenerativeModel("gemini-2.5-flash")

    def generate(self, prompt: str, system: str = "", max_tokens: int = 2000) -> str:
        """
        تولید متن با Groq (اول) و Gemini (پشتیبان)
        """
        # ۱. تلاش اول: Groq
        try:
            log.info("→ تلاش با Groq...")
            response = self.groq_client.chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=[
                    {"role": "system", "content": system or "You are a professional crypto analyst."},
                    {"role": "user", "content": prompt},
                ],
                max_tokens=max_tokens,
                temperature=0.7,
            )
            result = response.choices[0].message.content
            log.info("✅ Groq پاسخ داد")
            return result

        except Exception as e:
            log.warning(f"⚠️ Groq خطا داد: {e}")

        # ۲. تلاش دوم: Gemini
        try:
            log.info("→ سوییچ به Gemini...")
            full_prompt = f"{system}\n\n{prompt}" if system else prompt
            response = self.gemini_model.generate_content(full_prompt)
            log.info("✅ Gemini پاسخ داد")
            return response.text

        except Exception as e:
            log.error(f"❌ Gemini هم خطا داد: {e}")
            raise RuntimeError("همه‌ی LLM ها در دسترس نیستن!")


if __name__ == "__main__":
    # تست سریع
    print("\n🧪 تست LLM Router...\n")
    router = LLMRouter()

    prompt = "در یک جمله کوتاه بگو بیت‌کوین چیه."
    print(f"📝 سوال: {prompt}\n")
    print("🤖 پاسخ:")
    print(router.generate(prompt))
    print()