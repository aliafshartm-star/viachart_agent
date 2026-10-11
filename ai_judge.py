"""
AI Judge — با Gemini تصمیم می‌گیره سیگنال بفرسته یا نه
"""
import os
import json
import logging

import google.generativeai as genai

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')
log = logging.getLogger(__name__)


def ask_ai_judge(symbol, context):
    """
    از Gemini بپرس: این سیگنال رو بفرستیم یا نه؟
    Returns: {"decision": "SEND"|"SKIP", "reason": "..."}
    """
    try:
        genai.configure(api_key=os.environ["GEMINI_API_KEY"])

        models_to_try = [
            "gemini-2.0-flash",
            "gemini-1.5-flash",
            "gemini-1.5-pro",
            "gemini-pro",
        ]

        prompt = _build_prompt(symbol, context)

        result_text = None
        for model_name in models_to_try:
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
                    break
            except Exception as e:
                log.warning(f"مدل {model_name} خطا: {str(e)[:80]}")
                continue

        if not result_text:
            return {"decision": "SEND", "reason": "AI unavailable — default send"}

        # پیدا کردن JSON
        json_start = result_text.find("{")
        json_end = result_text.rfind("}") + 1

        if json_start >= 0 and json_end > json_start:
            try:
                parsed = json.loads(result_text[json_start:json_end])
                decision = parsed.get("decision", "SEND").upper()
                reason = parsed.get("reason", "")
                if decision not in ["SEND", "SKIP"]:
                    decision = "SEND"
                return {"decision": decision, "reason": reason}
            except Exception:
                pass

        # Fallback
        upper = result_text.upper()
        if "SKIP" in upper:
            return {"decision": "SKIP", "reason": result_text[:200]}
        return {"decision": "SEND", "reason": result_text[:200]}

    except Exception as e:
        log.error(f"AI Judge خطا: {e}")
        return {"decision": "SEND", "reason": f"Error: {str(e)[:100]}"}


def _build_prompt(symbol, ctx):
    coin = symbol.replace("USDT", "")
    current = ctx["current"]

    if not ctx["has_history"]:
        return f"""You are an AI trading assistant for a crypto Telegram channel.

NEW signal candidate (first time ever):

Symbol: {coin}/USDT (SPOT trading)
Current Price: ${current['price']}
Score: {current['score']}/100
Forces: {json.dumps(current['forces'], ensure_ascii=False)}
Reasons: {json.dumps(current['reasons'], ensure_ascii=False)}

Decision: Should we send this signal?

Respond ONLY with JSON:
{{"decision": "SEND", "reason": "short Persian explanation (max 15 words)"}}"""

    past = ctx["past_signals"]
    past_str = ""
    for p in past:
        past_str += f"- {p['hours_ago']}h ago: ${p['price_then']} (score {p['score_then']}) → {p['result']}\n"

    return f"""You are an AI trading assistant for a crypto Telegram channel.

Decide: send a NEW signal for {coin}/USDT or SKIP?

=== CURRENT ===
Symbol: {coin}/USDT (SPOT)
Current Price: ${current['price']}
Current Score: {current['score']}/100
Forces: {json.dumps(current['forces'], ensure_ascii=False)}
Reasons: {json.dumps(current['reasons'], ensure_ascii=False)}

=== PAST SIGNALS FOR THIS COIN ===
{past_str}

=== DECISION RULES ===
1. Last signal < 24h ago → SKIP (too soon)
2. Last signal OPEN in profit (+2% to +5%) → SKIP (let it run)
3. Last signal HIT TP1/TP2/TP3 → SKIP (already won)
4. Last signal STOPPED and score < 65 → SKIP
5. Last signal STOPPED, score >= 65, 7+ days passed → SEND (new setup)
6. No signal in 7+ days, score >= 50 → SEND
7. Price went up > 10% since last signal → SKIP (missed)
8. Price dropped > 10% since last signal + recovering → SEND if score high

Context: We want HIGH QUALITY signals. Repeating same coin annoys subscribers.

Respond ONLY with JSON (no markdown):
{{"decision": "SEND" or "SKIP", "reason": "short Persian explanation (max 20 words)"}}"""