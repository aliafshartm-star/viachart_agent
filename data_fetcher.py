"""
جمع‌آوری داده‌ها از Binance و منابع خبری
"""
import requests
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')
log = logging.getLogger(__name__)

# endpoint عمومی Binance — بدون محدودیت جغرافیایی
BINANCE_API = "https://data-api.binance.vision/api/v3"


def get_top_symbols(limit=100):
    """لیست ۱۰۰ ارز برتر بر اساس حجم معاملات USDT"""
    log.info(f"دریافت {limit} ارز برتر از Binance...")
    try:
        url = f"{BINANCE_API}/ticker/24hr"
        response = requests.get(url, timeout=15)
        response.raise_for_status()
        data = response.json()

        usdt_pairs = [
            item for item in data
            if item["symbol"].endswith("USDT")
            and float(item["quoteVolume"]) > 0
        ]
        usdt_pairs.sort(key=lambda x: float(x["quoteVolume"]), reverse=True)

        symbols = []
        for item in usdt_pairs[:limit]:
            symbol = item["symbol"]
            if any(x in symbol for x in ["UP", "DOWN", "BULL", "BEAR"]):
                continue
            symbols.append({
                "symbol": symbol,
                "price": float(item["lastPrice"]),
                "change_24h": float(item["priceChangePercent"]),
                "volume_24h": float(item["quoteVolume"]),
            })

        log.info(f"✅ {len(symbols)} ارز دریافت شد")
        return symbols
    except Exception as e:
        log.error(f"خطا در دریافت ارزها: {e}")
        return []


def get_klines(symbol, interval="4h", limit=200):
    """دریافت کندل‌های ارز از Binance"""
    try:
        url = f"{BINANCE_API}/klines"
        params = {"symbol": symbol, "interval": interval, "limit": limit}
        response = requests.get(url, params=params, timeout=15)
        response.raise_for_status()
        data = response.json()

        candles = []
        for c in data:
            candles.append({
                "time": int(c[0]),
                "open": float(c[1]),
                "high": float(c[2]),
                "low": float(c[3]),
                "close": float(c[4]),
                "volume": float(c[5]),
            })
        return candles
    except Exception as e:
        log.error(f"خطا در دریافت کندل {symbol}: {e}")
        return []


def get_fear_greed_index():
    """شاخص ترس و طمع از Alternative.me"""
    try:
        url = "https://api.alternative.me/fng/"
        response = requests.get(url, timeout=10)
        data = response.json()
        return {
            "value": int(data["data"][0]["value"]),
            "label": data["data"][0]["value_classification"],
        }
    except Exception as e:
        log.error(f"خطا در دریافت شاخص ترس و طمع: {e}")
        return {"value": 50, "label": "Neutral"}


if __name__ == "__main__":
    print("\n🧪 تست data_fetcher...\n")

    symbols = get_top_symbols(limit=10)
    print(f"\n📊 ۱۰ ارز برتر:")
    for s in symbols[:5]:
        print(f"   {s['symbol']}: ${s['price']} ({s['change_24h']:+.2f}%)")

    if symbols:
        print(f"\n📈 کندل BTCUSDT (آخرین ۳ تا):")
        candles = get_klines("BTCUSDT", "4h", 3)
        for c in candles:
            print(f"   Close: ${c['close']}")

    print(f"\n😱 شاخص ترس و طمع:")
    fg = get_fear_greed_index()
    print(f"   {fg['value']} - {fg['label']}")