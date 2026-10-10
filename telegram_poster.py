def _translate_to_farsi(router, english_text):
    """ترجمه با Gemini مستقیم — بدون واسطه Groq"""
    import google.generativeai as genai

    try:
        genai.configure(api_key=os.environ["GEMINI_API_KEY"])

        # چند مدل رو امتحان کن
        model_names = [
            "gemini-2.0-flash",
            "gemini-1.5-flash",
            "gemini-1.5-pro",
            "gemini-pro",
        ]

        prompt = (
            "Translate this English crypto headline to Persian (Farsi).\n"
            "Output ONLY the Persian translation. Nothing else.\n\n"
            "English: " + english_text + "\n\n"
            "Persian:"
        )

        result = None
        for model_name in model_names:
            try:
                model = genai.GenerativeModel(model_name)
                response = model.generate_content(
                    prompt,
                    generation_config={
                        "temperature": 0.1,
                        "max_output_tokens": 100,
                    }
                )
                result = response.text.strip()
                if result:
                    log.info(f"✅ ترجمه با {model_name}")
                    break
            except Exception as e:
                log.warning(f"مدل {model_name} خطا داد: {str(e)[:80]}")
                continue

        if not result:
            return "—"

        # پاک‌سازی شدید: فقط خط فارسی نهایی
        lines = result.split("\n")
        fa_lines = []

        for line in lines:
            line = line.strip()
            if not line:
                continue

            # حذف برچسب‌ها
            low = line.lower()
            for prefix in ["persian:", "translation:", "english:", "output:"]:
                if low.startswith(prefix):
                    line = line[len(prefix):].strip()
                    break

            if not line:
                continue

            # چک کن که اکثراً فارسی باشه
            fa_chars = sum(1 for c in line if '\u0600' <= c <= '\u06FF')
            total = len(line.replace(" ", ""))

            if total > 0 and fa_chars / total > 0.5:
                fa_lines.append(line)

        if not fa_lines:
            return "—"

        # فقط خط اول (تمیزترین)
        result = fa_lines[0]
        result = result.strip('"').strip("'").strip("«»").strip()
        return result

    except Exception as e:
        log.warning(f"ترجمه ناموفق: {e}")
        return "—"