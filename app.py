
from flask import Flask, render_template
import time
import yfinance as yf
import feedparser
from textblob import TextBlob
from datetime import datetime, timedelta
import threading

app = Flask(__name__)

STOCKS = {
    "RELIANCE.NS": "Reliance Industries",
    "TCS.NS": "Tata Consultancy Services"
}

PRICE_THRESHOLD = 1.5
COOLDOWN_MINUTES = 30
CHECK_INTERVAL = 300

alert_memory = {}
latest_alerts = []

def can_alert(symbol):
    now = datetime.now()
    last = alert_memory.get(symbol)
    if not last:
        return True
    return (now - last) > timedelta(minutes=COOLDOWN_MINUTES)

def price_score(change):
    if abs(change) >= 4: return 3
    if abs(change) >= 2: return 2
    if abs(change) >= 1: return 1
    return 0

def sentiment_score(sentiment):
    if sentiment <= -0.3 or sentiment >= 0.3: return 2
    if sentiment <= -0.1 or sentiment >= 0.1: return 1
    return 0

def check_stock(symbol):
    data = yf.Ticker(symbol).history(period="1d", interval="5m")
    if len(data) < 2:
        return None
    old, new = data["Close"].iloc[-2], data["Close"].iloc[-1]
    return round(((new - old) / old) * 100, 2)

def check_news(company):
    feed = feedparser.parse(
        f"https://news.google.com/rss/search?q={company}+stock"
    )
    sentiments = []
for e in feed.entries[:5]:
    try:
        sentiments.append(TextBlob(e.title).sentiment.polarity)
    except:
        sentiments.append(0)

    headlines = [e.title for e in feed.entries[:5]]
    if not sentiments:
        return None, 0
    return headlines[0], sum(sentiments) / len(sentiments)

def run_agent():
    global latest_alerts
    while True:
        for symbol, name in STOCKS.items():
            change = check_stock(symbol)
            if change is None or not can_alert(symbol):
                continue

            headline, sentiment = check_news(name)
            score = price_score(change) + sentiment_score(sentiment)

            if abs(change) >= PRICE_THRESHOLD and score >= 3:
                mood = "Negative" if sentiment < 0 else "Positive"
                alert = {
                    "company": name,
                    "change": change,
                    "sentiment": mood,
                    "headline": headline,
                    "time": datetime.now().strftime("%H:%M")
                }
                latest_alerts.insert(0, alert)
                alert_memory[symbol] = datetime.now()

        time.sleep(CHECK_INTERVAL)

@app.route("/")
def home():
    return render_template("index.html", alerts=latest_alerts[:10])

if __name__ == "__main__":
    threading.Thread(target=run_agent, daemon=True).start()
    app.run(host="0.0.0.0", port=10000)
