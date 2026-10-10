"""
مسیریاب هوشمند بین Groq و Gemini با fallback خودکار
"""
import os
import logging
from groq import Groq
import google.generativeai as genai

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')
log = logging.getLogger(__name__)

# مدل‌های Groq به ترتیب اولویت
GROQ_MODELS = [
    "llama-3.1-8b-instant",
    "llama-3.1-70b-versatile",
    "llama3-70b-8192",
    "llama3-8b-8192",
    "mixtral-8x7b-32768",
    "gemma2-9b-it",
]

# مدل‌های Gemini به ترتیب اولویت
GEMINI_MODELS = [
    "gemini-2.0-flash",
    "gemini-2.0-flash-exp",
    "gemini-1.5-flash",
    "gemini-1.5-flash-latest",
    "gemini-1.5-pro",
    "gemini-pro",
]


class LLMRouter:
    """مسیریاب بین Groq و Gemini"""

    def __init__(self):
        self.groq_client = Groq(api_key=os.environ["GROQ_API_KEY"])
        genai.configure(api_key=os.environ["GEMINI_API_KEY"])

    def _try_groq(self, prompt: str, system: str, max_tokens: int) -> str:
        """تلاش با مدل‌های مختلف Groq"""
        for model in GROQ_MODELS:
            try:
                log.info(f"→ تلاش با Groq ({model})...")
                response = self.groq_client.chat.completions.create(
                    model=model,
                    messages=[
                        {"role": "system", "content": system or "You are a professional crypto analyst."},
                        {"role": "user", "content": prompt},
                    ],
                    max_tokens=max_tokens,
                    temperature=0.7,
                )
                result = response.choices[0].message.content
                log.info(f"✅ Groq ({model}) پاسخ داد")
                return result
            except Exception as e:
                log.warning(f"⚠️ Groq ({model}) خطا داد: {str(e)[:120]}")
        return None

    def _try_gemini(self, prompt: str, system: str) -> str:
        """تلاش با مدل‌های مختلف Gemini"""
        full_prompt = f"{system}\n\n{prompt}" if system else prompt
        for model_name in GEMINI_MODELS:
            try:
                log.info(f"→ تلاش با Gemini ({model_name})...")
                model = genai.GenerativeModel(model_name)
                response = model.generate_content(full_prompt)
                log.info(f"✅ Gemini ({model_name}) پاسخ داد")
                return response.text
            except Exception as e:
                log.warning(f"⚠️ Gemini ({model_name}) خطا داد: {str(e)[:120]}")
        return None

    def generate(self, prompt: str, system: str = "", max_tokens: int = 2000) -> str:
        """تولید متن با Groq (اول) و Gemini (پشتیبان)"""
        # ۱. تلاش با Groq
        result = self._try_groq(prompt, system, max_tokens)
        if result:
            return result

        # ۲. تلاش با Gemini
        result = self._try_gemini(prompt, system)
        if result:
            return result

        raise RuntimeError("همه‌ی LLM ها در دسترس نیستن!")


if __name__ == "__main__":
    print("\n🧪 تست LLM Router...\n")
    router = LLMRouter()

    prompt = "در یک جمله کوتاه بگو بیت‌کوین چیه."
    print(f"📝 سوال: {prompt}\n")
    print("🤖 پاسخ:")
    print(router.generate(prompt))
    print()