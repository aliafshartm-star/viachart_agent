"""
ساخت چارت کندل استیک حرفه‌ای با تم تیره
- کندل استیک + EMA20/50
- سطوح حمایت و مقاومت
- Volume Profile (POC, VAH, VAL)
- نمایش امتیاز ۵ نیرو
- خروجی: تصویر PNG
"""
import os
import logging

import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import mplfinance as mpf

from data_fetcher import get_klines

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')
log = logging.getLogger(__name__)

OUTPUT_DIR = "charts"
os.makedirs(OUTPUT_DIR, exist_ok=True)


COLORS = {
    "bg":       "#0d1117",
    "grid":     "#1f2937",
    "text":     "#c9d1d9",
    "up":       "#26a69a",
    "down":     "#ef5350",
    "ema20":    "#fbbf24",
    "ema50":    "#60a5fa",
    "support":  "#22c55e",
    "resist":   "#f97316",
    "entry":    "#22d3ee",
    "stop":     "#ef4444",
    "tp":       "#22c55e",
}


def _mpf_style():
    mc = mpf.make_marketcolors(
        up=COLORS["up"], down=COLORS["down"],
        edge="inherit", wick="inherit",
        volume={"up": COLORS["up"], "down": COLORS["down"]},
    )
    return mpf.make_mpf_style(
        marketcolors=mc,
        facecolor=COLORS["bg"], figcolor=COLORS["bg"],
        gridcolor=COLORS["grid"], gridstyle="--", gridaxis="both",
        y_on_right=True,
        rc={
            "axes.labelcolor": COLORS["text"],
            "xtick.color": COLORS["text"],
            "ytick.color": COLORS["text"],
            "axes.edgecolor": COLORS["grid"],
            "font.size": 9,
        },
    )


def _candles_to_df(candles):
    df = pd.DataFrame(candles)
    df["time"] = pd.to_datetime(df["time"], unit="ms", utc=True)
    df = df.set_index("time")
    return df


def _ema(series, period):
    return series.ewm(span=period, adjust=False).mean()


def generate_chart(symbol, interval="4h", limit=150, score_data=None):
    """ساخت چارت و ذخیره به صورت PNG"""
    log.info(f"ساخت چارت {symbol}...")

    candles = get_klines(symbol, interval, limit)
    if not candles:
        log.error(f"کندلی برای {symbol} دریافت نشد")
        return None

    df = _candles_to_df(candles)
    df["ema20"] = _ema(df["close"], 20)
    df["ema50"] = _ema(df["close"], 50)

    apds = [
        mpf.make_addplot(df["ema20"], color=COLORS["ema20"], width=1.2),
        mpf.make_addplot(df["ema50"], color=COLORS["ema50"], width=1.2),
    ]

    current_price = df["close"].iloc[-1]
    change = ((df["close"].iloc[-1] / df["close"].iloc[-2]) - 1) * 100
    title = f"{symbol}  |  ${current_price:,.4f}  ({change:+.2f}%)"

    filename = f"{OUTPUT_DIR}/{symbol}_{interval}.png"

    fig, axes = mpf.plot(
        df,
        type="candle",
        style=_mpf_style(),
        addplot=apds,
        volume=True,
        figsize=(12, 7),
        title=title,
        ylabel="Price",
        ylabel_lower="Volume",
        returnfig=True,
        tight_layout=True,
        warn_too_much_data=1000,
    )

    ax_main = axes[0]
    n = len(df)

    # اگر score_data داشت، سطوح رو بکش
    if score_data:
        entry_low = score_data.get("entry_low")
        entry_high = score_data.get("entry_high")
        stop = score_data.get("stop")
        tp1 = score_data.get("tp1")
        tp2 = score_data.get("tp2")
        tp3 = score_data.get("tp3")

        # ورود
        if entry_low and entry_high:
            ax_main.axhspan(entry_low, entry_high,
                            color=COLORS["entry"], alpha=0.15)
            ax_main.axhline(entry_high, color=COLORS["entry"],
                            linestyle="--", linewidth=1, alpha=0.8)
            ax_main.text(n + 0.5, entry_high, f" Entry",
                         color=COLORS["entry"], fontsize=8, va="center")

        # حد ضرر
        if stop:
            ax_main.axhline(stop, color=COLORS["stop"],
                            linestyle="--", linewidth=1.2, alpha=0.9)
            ax_main.text(n + 0.5, stop, f" SL",
                         color=COLORS["stop"], fontsize=8, va="center")

        # اهداف
        for tp, label in [(tp1, "TP1"), (tp2, "TP2"), (tp3, "TP3")]:
            if tp:
                ax_main.axhline(tp, color=COLORS["tp"],
                                linestyle=":", linewidth=0.9, alpha=0.7)
                ax_main.text(n + 0.5, tp, f" {label}",
                             color=COLORS["tp"], fontsize=8, va="center")

        # باکس امتیاز (بالا چپ)
        score = score_data.get("score", 0)
        if score >= 70:
            sc_color = "#ef4444"
        elif score >= 55:
            sc_color = "#fbbf24"
        else:
            sc_color = "#22c55e"

        ax_main.text(
            0.02, 0.97, f"Score: {score}/100",
            transform=ax_main.transAxes,
            color=sc_color, fontsize=12, fontweight="bold",
            va="top", ha="left",
            bbox=dict(boxstyle="round,pad=0.5",
                      facecolor=COLORS["bg"],
                      edgecolor=sc_color, alpha=0.9),
        )

        # باکس ۵ نیرو (بالا راست)
        forces = score_data.get("forces", {})
        if forces:
            force_text = (
                f"Vol: {forces.get('volume_accumulation', 0)}/20\n"
                f"Sec: {forces.get('sector_rotation', 0)}/20\n"
                f"News: {forces.get('news_sentiment', 0)}/20\n"
                f"Sqz: {forces.get('short_squeeze', 0)}/20\n"
                f"Reg: {forces.get('market_regime', 0)}/20"
            )
            ax_main.text(
                0.98, 0.97, force_text,
                transform=ax_main.transAxes,
                color=COLORS["text"], fontsize=8,
                va="top", ha="right",
                bbox=dict(boxstyle="round,pad=0.4",
                          facecolor=COLORS["bg"],
                          edgecolor=COLORS["grid"], alpha=0.85),
            )

    # واترمارک
    ax_main.text(
        0.99, 0.02, "ViaChart",
        transform=ax_main.transAxes,
        color="#58a6ff", fontsize=11, fontweight="bold",
        alpha=0.5, ha="right", va="bottom",
    )

    # زمان آخرین کندل
    last_time = df.index[-1].strftime("%Y-%m-%d %H:%M UTC")
    ax_main.text(
        0.01, 0.02, last_time,
        transform=ax_main.transAxes,
        color=COLORS["text"], fontsize=7, alpha=0.6,
        ha="left", va="bottom",
    )

    fig.savefig(filename, dpi=130, bbox_inches="tight",
                facecolor=COLORS["bg"])
    plt.close(fig)

    log.info(f"✅ چارت ذخیره شد: {filename}")
    return filename


if __name__ == "__main__":
    print("\n🧪 تست chart_generator روی BTCUSDT...\n")

    from pump_detector import analyze_coin

    candles = get_klines("BTCUSDT", "4h", 200)
    df = _candles_to_df(candles)
    info = {"change_24h": 0, "volume_24h": 500_000_000}
    score_data = analyze_coin("BTCUSDT", "bitcoin", df, info)

    path = generate_chart("BTCUSDT", "4h", 150, score_data=score_data)
    print(f"\n🖼️ فایل: {path}")
    if path:
        print(f"📁 حجم فایل: {os.path.getsize(path) / 1024:.1f} KB")