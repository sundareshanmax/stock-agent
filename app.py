from flask import Flask, render_template, request
import threading, time
import yfinance as yf
import feedparser
from textblob import TextBlob
from datetime import datetime, timedelta

app = Flask(__name__)

# ================= CONFIG =================
STOCKS = {
    "RELIANCE.NS": "Reliance",
    "TCS.NS": "TCS",
    "INFY.NS": "Infosys",
    "HDFCBANK.NS": "HDFC Bank",
    "ICICIBANK.NS": "ICICI Bank",
    "SBIN.NS": "SBI",
}

WATCHLIST = ["RELIANCE.NS", "TCS.NS", "INFY.NS"]

PRICE_THRESHOLD = 1.5
CHECK_INTERVAL = 300
COOLDOWN_MINUTES = 30
# =========================================

alert_memory = {}
latest_alerts = []

# ---------- HELPERS ----------

def can_alert(symbol):
    now = datetime.now()
    last = alert_memory.get(symbol)
    return not last or (now - last) > timedelta(minutes=COOLDOWN_MINUTES)

def get_intraday_sparkline(symbol):
    try:
        data = yf.Ticker(symbol).history(period="1d", interval="30m")
        return [round(x, 2) for x in data["Close"].tail(10).tolist()]
    except:
        return []

def get_today_change(symbol):
    try:
        data = yf.Ticker(symbol).history(period="1d")
        if len(data) < 2:
            return 0
        o, c = data["Open"].iloc[0], data["Close"].iloc[-1]
        return round(((c - o) / o) * 100, 2)
    except:
        return 0

def get_trending():
    rows = []
    for sym, name in STOCKS.items():
        change = get_today_change(sym)
        rows.append({
            "symbol": sym,
            "name": name,
            "change": change,
            "spark": get_intraday_sparkline(sym)
        })

    gainers = sorted(rows, key=lambda x: x["change"], reverse=True)[:5]
    losers = sorted(rows, key=lambda x: x["change"])[:5]

    return gainers, losers, rows

def market_summary(all_rows):
    g = len([r for r in all_rows if r["change"] > 0])
    l = len([r for r in all_rows if r["change"] < 0])

    if g > l:
        return "Bullish 🟢"
    elif l > g:
        return "Bearish 🔴"
    return "Sideways 🟡"

def check_news(company):
    feed = feedparser.parse(
        f"https://news.google.com/rss/search?q={company}+stock"
    )
    sentiments, headlines = [], []

    for e in feed.entries[:5]:
        try:
            sentiments.append(TextBlob(e.title).sentiment.polarity)
            headlines.append(e.title)
        except:
            pass

    if not sentiments:
        return None, 0

    return headlines[0], sum(sentiments) / len(sentiments)

# ---------- AGENT ----------

def run_agent():
    global latest_alerts
    while True:
        for sym, name in STOCKS.items():
            change = get_today_change(sym)
            if abs(change) < PRICE_THRESHOLD or not can_alert(sym):
                continue

            headline, sentiment = check_news(name)
            mood = "Negative" if sentiment < 0 else "Positive"

            latest_alerts.insert(0, {
                "company": name,
                "change": change,
                "sentiment": mood,
                "headline": headline,
                "time": datetime.now().strftime("%H:%M")
            })

            latest_alerts[:] = latest_alerts[:20]
            alert_memory[sym] = datetime.now()

        time.sleep(CHECK_INTERVAL)

# ---------- ROUTES ----------

@app.route("/")
def dashboard():
    gainers, losers, all_rows = get_trending()
    summary = market_summary(all_rows)

    watch = [r for r in all_rows if r["symbol"] in WATCHLIST]

    return render_template(
        "index.html",
        gainers=gainers,
        losers=losers,
        alerts=latest_alerts,
        watchlist=watch,
        summary=summary,
        date=datetime.now().strftime("%d %b %Y")
    )

# ---------- MAIN ----------

if __name__ == "__main__":
    threading.Thread(target=run_agent, daemon=True).start()
    app.run(host="0.0.0.0", port=10000)
