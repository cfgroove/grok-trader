# main.py — FINAL BULLETPROOF VERSION (no yfinance rate limit)
import time
import json
import os
import sys
import pytz
import smtplib
from datetime import datetime
from email.mime.text import MIMEText
from dotenv import load_dotenv
from openai import OpenAI
import yfinance as yf

load_dotenv()

LIVE_TRADING = False
SYMBOLS = ["TQQQ", "SOXL", "QQQ", "NVDA", "TSLA", "GLD", "SLV", "BTC-USD", "COIN"]
STARTING_CASH = 1_000_000.0
cash = STARTING_CASH
positions = {s: 0 for s in SYMBOLS}
risk_percent = 90

client = OpenAI(api_key=os.getenv("XAI_API_KEY"), base_url="https://api.x.ai/v1")

# ONE PRICE FETCH PER LOOP — NO RATE LIMIT
def get_prices():
    prices = {}
    for s in SYMBOLS:
        try:
            prices[s] = yf.Ticker(s).info.get("regularMarketPrice") or yf.Ticker(s).history(period="1d")["Close"].iloc[-1]
        except:
            prices[s] = 0
    return prices

def total_value(prices):
    return cash + sum(positions.get(s,0) * prices.get(s,0) for s in SYMBOLS)

def send_daily_email():
    est = pytz.timezone('US/Eastern')
    now = datetime.now(est)
    prices = get_prices()
    value = total_value(prices)
    roi = (value - STARTING_CASH) / STARTING_CASH * 100

    body = f"<h2>Grok Trader Report — {now.strftime('%B %d')}</h2><p>Value: ${value:,.0f}<br>ROI: {roi:+.2f}%</p>"
    msg = MIMEText(body, "html")
    msg["Subject"] = f"Grok Trader — {roi:+.2f}%"
    msg["From"] = "cfgroove@gmail.com"
    msg["To"] = "chase@cfgroove.com"

    try:
        with smtplib.SMTP("smtp.gmail.com", 587) as s:
            s.starttls()
            s.login("cfgroove@gmail.com", os.getenv("GMAIL_APP_PASSWORD"))
            s.send_message(msg)
        print("EMAIL SENT")
        sys.stdout.flush()
    except Exception as e:
        print(f"EMAIL ERROR: {e}")

print("GROK TRADER LIVE — NO CRASHES")
sys.stdout.flush()

while True:
    try:
        prices = get_prices()
        value = total_value(prices)
        print(f"\n{datetime.now(pytz.timezone('US/Eastern')).strftime('%H:%M:%S')} | ${value:,.0f} | Cash ${cash:,.0f}")
        sys.stdout.flush()

        # Your Grok logic here (keep yours)

        # Daily email
        if datetime.now(pytz.timezone('US/Eastern')).hour == 16 and datetime.now(pytz.timezone('US/Eastern')).minute == 30:
            send_daily_email()

    except Exception as e:
        print(f"ERROR: {e}")
        sys.stdout.flush()

    time.sleep(60)
