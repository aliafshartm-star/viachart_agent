"""
مسیریاب هوشمند بین Groq و Gemini
- مدل‌ها به صورت خودکار کشف میشن
- اگه یکی خطا داد، خودکار میره بعدی
"""
import os
import logging
from groq import Groq
import google.generativeai as genai

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')
log = logging.getLogger(__name__)


class LLMRouter:
    def __init__(self):
        self.groq_client = Groq(api_key=os.environ["GROQ_API_KEY"])
        genai.configure(api_key=os.environ["GEMINI_API_KEY"])

    def list_groq_models(self):
        """لیست مدل‌های در دسترس Groq"""
        try:
            models = self.groq_client.models.list()
            return [m.id for m in models.data]
        except Exception as e:
            log.error(f"خطا در لیست مدل‌های Groq: {e}")
            return []

    def list_gemini_models(self):
        """لیست مدل‌های Gemini که از generateContent پشتیبانی می‌کنن"""
        models = []
        try:
            for m in genai.list_models():
                if "generateContent" in m.supported_generation_methods:
                    # نام کامل مثل models/gemini-xxx رو کوتاه می‌کنیم
                    name = m.name.replace("models/", "")
                    models.append(name)
        except Exception as e:
            log.error(f"خطا در لیست مدل‌های Gemini: {e}")
        return models

    def _try_groq(self, prompt, system, max_tokens):
        models = self.list_groq_models()
        if not models:
            log.warning("⚠️ هیچ مدل Groq ای پیدا نشد")
            return None
        log.info(f"مدل‌های Groq موجود: {models[:5]}")

        for model in models:
            # از مدل‌های خاص صرف‌نظر کن (مثل whisper, tts)
            if any(x in model.lower() for x in ["whisper", "tts", "guard"]):
                continue
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
                log.info(f"✅ Groq ({model}) پاسخ داد")
                return response.choices[0].message.content
            except Exception as e:
                log.warning(f"⚠️ {model} خطا داد: {str(e)[:100]}")
        return None

    def _try_gemini(self, prompt, system):
        models = self.list_gemini_models()
        if not models:
            log.warning("⚠️ هیچ مدل Gemini ای پیدا نشد")
            return None
        log.info(f"مدل‌های Gemini موجود: {models[:5]}")

        full_prompt = f"{system}\n\n{prompt}" if system else prompt
        for model_name in models:
            try:
                log.info(f"→ تلاش با Gemini ({model_name})...")
                model = genai.GenerativeModel(model_name)
                response = model.generate_content(full_prompt)
                log.info(f"✅ Gemini ({model_name}) پاسخ داد")
                return response.text
            except Exception as e:
                log.warning(f"⚠️ {model_name} خطا داد: {str(e)[:100]}")
        return None

    def generate(self, prompt, system="", max_tokens=2000):
        # ۱. Groq
        result = self._try_groq(prompt, system, max_tokens)
        if result:
            return result

        # ۲. Gemini
        result = self._try_gemini(prompt, system)
        if result:
            return result

        raise RuntimeError("همه‌ی LLM ها در دسترس نیستن!")


if __name__ == "__main__":
    print("\n🧪 تست LLM Router...\n")
    router = LLMRouter()

    # نمایش مدل‌های در دسترس
    print("=" * 50)
    print("📋 مدل‌های Groq در دسترس:")
    for m in router.list_groq_models():
        print(f"   - {m}")

    print("\n📋 مدل‌های Gemini در دسترس:")
    for m in router.list_gemini_models():
        print(f"   - {m}")
    print("=" * 50)

    prompt = "در یک جمله کوتاه بگو بیت‌کوین چیه."
    print(f"\n📝 سوال: {prompt}\n")
    print("🤖 پاسخ:")
    print(router.generate(prompt))
    print()