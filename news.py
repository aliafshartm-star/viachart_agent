"""
جمع‌آوری اخبار کریپتو از منابع رایگان
"""
import logging
from datetime import datetime, timezone

import requests

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')
log = logging.getLogger(__name__)


def get_cryptopanic_news(limit=15):
    """
    اخبار از CryptoPanic (بدون API key هم کار میکنه)
    """
    try:
        url = "https://cryptopanic.com/api/free/v1/posts/"
        params = {
            "auth_token": "free",
            "public": "true",
            "kind": "news",
        }
        response = requests.get(url, params=params, timeout=15)

        # اگه rate limit خورد یا خطا داد، از RSS برمیگردیم
        if response.status_code != 200:
            log.warning(f"CryptoPanic خطا داد: {response.status_code}")
            return get_rss_news(limit)

        data = response.json()
        posts = data.get("results", [])[:limit]

        news = []
        for p in posts:
            news.append({
                "title": p.get("title", ""),
                "source": p.get("source", {}).get("title", "Unknown"),
                "published": p.get("published_at", ""),
                "url": p.get("url", ""),
                "currencies": [c.get("code") for c in p.get("currencies", [])],
                "votes": {
                    "positive": p.get("votes", {}).get("positive", 0),
                    "negative": p.get("votes", {}).get("negative", 0),
                    "important": p.get("votes", {}).get("important", 0),
                },
            })

        log.info(f"✅ {len(news)} خبر از CryptoPanic دریافت شد")
        return news

    except Exception as e:
        log.warning(f"خطا در CryptoPanic: {e}")
        return get_rss_news(limit)


def get_rss_news(limit=15):
    """
    پشتیبان: اخبار از CoinDesk RSS
    """
    try:
        import xml.etree.ElementTree as ET
        url = "https://www.coindesk.com/arc/outboundfeeds/rss/"
        response = requests.get(url, timeout=15)
        response.raise_for_status()

        root = ET.fromstring(response.content)
        items = root.findall(".//item")[:limit]

        news = []
        for item in items:
            title = item.findtext("title", "")
            link = item.findtext("link", "")
            pub = item.findtext("pubDate", "")
            news.append({
                "title": title,
                "source": "CoinDesk",
                "published": pub,
                "url": link,
                "currencies": [],
                "votes": {"positive": 0, "negative": 0, "important": 0},
            })

        log.info(f"✅ {len(news)} خبر از CoinDesk RSS دریافت شد")
        return news

    except Exception as e:
        log.error(f"خطا در RSS: {e}")
        return []


def get_all_news():
    """دریافت اخبار از همه منابع"""
    return get_cryptopanic_news(limit=15)


def format_news_for_llm(news, max_items=10):
    """تبدیل اخبار به فرمت متن برای LLM"""
    if not news:
        return "خبری در دسترس نیست."

    lines = []
    for i, n in enumerate(news[:max_items], 1):
        currencies = ", ".join(n["currencies"]) if n["currencies"] else "—"
        sentiment = ""
        if n["votes"]["positive"] > n["votes"]["negative"]:
            sentiment = "🟢"
        elif n["votes"]["negative"] > n["votes"]["positive"]:
            sentiment = "🔴"

        lines.append(
            f"{i}. {sentiment} {n['title']}\n"
            f"   منبع: {n['source']} | کوین‌ها: {currencies}"
        )

    return "\n".join(lines)


if __name__ == "__main__":
    print("\n🧪 تست news.py...\n")

    news = get_all_news()
    print(f"\n📰 {len(news)} خبر دریافت شد:\n")

    for i, n in enumerate(news[:5], 1):
        print(f"{i}. {n['title']}")
        print(f"   منبع: {n['source']}")
        print()

    print("\n📝 فرمت نهایی برای LLM:\n")
    print(format_news_for_llm(news))