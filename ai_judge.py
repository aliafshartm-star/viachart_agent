"""
AI Judge — با Gemini تصمیم می‌گیره سیگنال بفرسته یا نه
- خودکار مدل‌های در دسترس رو پیدا می‌کنه
- fallback امنیتی: اگه AI خطا داد، cooldown ساده اجرا میشه
"""
import os
import json
import logging
from datetime import datetime, timezone

import google.generativeai as genai

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')
log = logging.getLogger(__name__)


# ============================================================
# پیدا کردن مدل‌های در دسترس Gemini
# ============================================================

def get_available_gemini_models():
    """لیست مدل‌های Gemini که از generateContent پشتیبانی می‌کنن"""
    try:
        genai.configure(api_key=os.environ["GEMINI_API_KEY"])
        models = []
        for m in genai.list_models():
            if "generateContent" in m.supported_generation_methods:
                name = m.name.replace("models/", "")
                # فیلتر کردن مدل‌های مناسب
                if any(x in name.lower() for x in ["gemini", "flash", "pro"]):
                    models.append(name)
        log.info(f"📋 Gemini models: {models[:5]}")
        return models
    except Exception as e:
        log.error(f"خطا در دریافت مدل‌ها: {e}")
        return []


# ============================================================
# fallback ساده (اگه AI کار نکرد)
# ============================================================

def simple_cooldown_check(context):
    """
    اگه AI کار نکرد، این چک ساده اجرا میشه:
    - اگه سیگنال قبلی < 48h پیش → SKIP
    - اگه سیگنال قبلی OPEN بود → SKIP
    - اگه 7+ روز گذشته → SEND
    """
    if not context["has_history"]:
        return {"decision": "SEND", "reason": "اولین سیگنال (fallback)"}

    past = context["past_signals"]
    if not past:
        return {"decision": "SEND", "reason": "بدون تاریخچه"}

    last = past[-1]
    hours_ago = last.get("hours_ago") or 999

    # اگه < 48h → SKIP
    if hours_ago < 48:
        return {
            "decision": "SKIP",
            "reason": f"سیگنال قبلی فقط {hours_ago:.0f} ساعت پیش بود"
        }

    # اگه نتیجه OPEN بود → SKIP
    result = last.get("result", "")
    if result and "OPEN" in result:
        return {
            "decision": "SKIP",
            "reason": "سیگنال قبلی هنوز بازه"
        }

    # اگه TP خورده → SKIP
    if result and "TP" in result:
        return {
            "decision": "SKIP",
            "reason": "سیگنال قبلی موفق بود"
        }

    # اگه 7+ روز → SEND
    if hours_ago >= 168:
        return {
            "decision": "SEND",
            "reason": "ستاپ جدید پس از ۷ روز"
        }

    return {"decision": "SKIP", "reason": "صبر تا شرایط بهتر"}


# ============================================================
# AI Judge اصلی
# ============================================================

def ask_ai_judge(symbol, context):
    """
    از Gemini بپرس: این سیگنال رو بفرستیم یا نه؟
    Returns: {"decision": "SEND"|"SKIP", "reason": "..."}
    """
    try:
        genai.configure(api_key=os.environ["GEMINI_API_KEY"])

        available_models = get_available_gemini_models()

        if not available_models:
            log.warning("⚠️ هیچ مدل Gemini در دسترس نیست → fallback")
            return simple_cooldown_check(context)

        prompt = _build_prompt(symbol, context)

        result_text = None
        for model_name in available_models:
            try:
                model = genai.GenerativeModel(model_name)
                response = model.generate_content(
                    prompt,
                    generation_config={
                        "temperature": 0.2,
                        "max_output_tokens": 300,
                    }
                )
                result_text = response.text.strip()
                if result_text:
                    log.info(f"   ✅ Gemini ({model_name}) پاسخ داد")
                    break
            except Exception as e:
                log.warning(f"   مدل {model_name} خطا: {str(e)[:80]}")
                continue

        if not result_text:
            log.warning("⚠️ Gemini پاسخ نداد → fallback")
            return simple_cooldown_check(context)

        # پیدا کردن JSON
        json_start = result_text.find("{")
        json_end = result_text.rfind("}") + 1

        if json_start >= 0 and json_end > json_start:
            try:
                parsed = json.loads(result_text[json_start:json_end])
                decision = parsed.get("decision", "SEND").upper()
                reason = parsed.get("reason", "")
                if decision not in ["SEND", "SKIP"]:
                    decision = "SKIP"
                return {"decision": decision, "reason": reason}
            except Exception as e:
                log.warning(f"خطا در پارس JSON: {e}")

        # fallback
        upper = result_text.upper()
        if "SKIP" in upper:
            return {"decision": "SKIP", "reason": result_text[:200]}
        return {"decision": "SEND", "reason": result_text[:200]}

    except Exception as e:
        log.error(f"AI Judge خطا: {e}")
        return simple_cooldown_check(context)


def _build_prompt(symbol, ctx):
    coin = symbol.replace("USDT", "")
    current = ctx["current"]

    if not ctx["has_history"]:
        return f"""You are an AI trading assistant for a crypto Telegram channel.

NEW signal candidate (first time):

Symbol: {coin}/USDT (SPOT)
Price: ${current['price']}
Score: {current['score']}/100
Forces: {json.dumps(current['forces'], ensure_ascii=False)}
Reasons: {json.dumps(current['reasons'], ensure_ascii=False)}

Decision: Should we send this signal?

Respond ONLY with JSON:
{{"decision": "SEND", "reason": "short Persian explanation (max 15 words)"}}"""

    past = ctx["past_signals"]
    past_str = ""
    for p in past:
        past_str += f"- {p.get('hours_ago', '?')}h ago: ${p['price_then']} (score {p['score_then']}) → {p.get('result', 'open')}\n"

    return f"""You are an AI trading assistant for a crypto Telegram channel.

Decide: send NEW signal for {coin}/USDT or SKIP?

=== CURRENT ===
Symbol: {coin}/USDT
Price: ${current['price']}
Score: {current['score']}/100
Forces: {json.dumps(current['forces'], ensure_ascii=False)}
Reasons: {json.dumps(current['reasons'], ensure_ascii=False)}

=== PAST SIGNALS FOR THIS COIN ===
{past_str}

=== DECISION RULES ===
1. Last signal < 48h ago → SKIP (too soon)
2. Last signal OPEN in profit → SKIP (let it run)
3. Last signal HIT TP1/TP2/TP3 → SKIP (already won)
4. Last signal STOPPED and score < 65 → SKIP
5. Last signal STOPPED, score >= 65, 7+ days passed → SEND
6. No signal in 7+ days, score >= 50 → SEND
7. Price went up > 10% since last signal → SKIP (missed)
8. Price dropped > 10% + recovering + high score → SEND

Goal: HIGH QUALITY signals. Repeating same coin annoys subscribers.

Respond ONLY with JSON (no markdown):
{{"decision": "SEND" or "SKIP", "reason": "short Persian explanation (max 20 words)"}}"""