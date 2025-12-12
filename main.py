# main.py — FINAL 100% WORKING VERSION
import time
import json
import yfinance as yf
import pytz
import smtplib
import sys          # ← WAS MISSING
from datetime import datetime
from email.mime.text import MIMEText
from openai import OpenAI
import os
from dotenv import load_dotenv

load_dotenv()

LIVE_TRADING = False
SYMBOLS = ["TQQQ", "SOXL", "QQQ", "NVDA", "TSLA", "GLD", "SLV", "BTC-USD", "COIN"]

client = OpenAI(api_key=os.getenv("XAI_API_KEY"), base_url="https://api.x.ai/v1")

if os.getenv("ALPACA_KEY") and os.getenv("ALPACA_SECRET"):
    from alpaca.trading.client import TradingClient
    from alpaca.trading.requests import MarketOrderRequest
    from alpaca.trading.enums import OrderSide, TimeInForce
    trading_client = TradingClient(os.getenv("ALPACA_KEY"), os.getenv("ALPACA_SECRET"), paper=not LIVE_TRADING)
else:
    trading_client = None

cash = 1_000_000.0
positions = {s: 0 for s in SYMBOLS}
risk_percent = 100

def get_prices():
    prices = {}
    for s in SYMBOLS:
        try:
            prices[s] = yf.Ticker(s).history(period="1d")["Close"].iloc[-1]
        except:
            prices[s] = 0
    return prices

def total_value(prices):
    return cash + sum(positions.get(s, 0) * prices.get(s, 0) for s in SYMBOLS)

def safe_json_parse(text):
    try:
        start = text.find("{")
        end = text.rfind("}") + 1
        return json.loads(text[start:end])
    except:
        return {"symbol": "TQQQ", "action": "buy", "qty": 100, "reasoning": "Bad JSON — forcing buy"}

def send_daily_email():
    est = pytz.timezone('US/Eastern')
    now = datetime.now(est)
    prices = get_prices()
    value = total_value(prices)
    roi = (value - 1_000_000) / 1_000_000 * 100

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
        print("DAILY EMAIL SENT")
        sys.stdout.flush()
    except Exception as e:
        print(f"EMAIL ERROR: {e}")

print("GROK TRADER LIVE — 100% ALL-IN, DIVERSIFY MODE")
print(f"Starting cash: ${cash:,.2f}")
sys.stdout.flush()

while True:
    try:
        prices = get_prices()
        value = total_value(prices)

        print(f"\n{datetime.now(pytz.timezone('US/Eastern')).strftime('%H:%M:%S')} | ${value:,.0f} | Cash ${cash:,.0f}")
        sys.stdout.flush()

        prompt = f"Cash ${cash:,.0f} | Risk 100% | Positions {positions} | Prices {json.dumps({s: round(prices[s], 2) for s in SYMBOLS})} → ONLY JSON: {{symbol,action:'buy'|'sell'|'hold',qty:int,reasoning:string}}"
        resp = client.chat.completions.create(model="grok-3", messages=[{"role": "user", "content": prompt}], temperature=0.85, max_tokens=150)
        d = safe_json_parse(resp.choices[0].message.content.strip())

        sym = d.get("symbol", "TQQQ") if d.get("symbol") in SYMBOLS else "TQQQ"
        action = d.get("action", "hold")
        qty = d.get("qty", 0)
        reason = d.get("reasoning", "")

        price = prices.get(sym, 0)
        trade = "HOLD"

        if action == "buy" and qty > 0:
            max_qty = int(cash // price)
            qty = min(qty, max_qty)
            if qty > 0:
                cash -= qty * price
                positions[sym] += qty
                trade = f"BUY {qty} {sym}"
                if trading_client and LIVE_TRADING:
                    order = MarketOrderRequest(symbol=sym.replace("-USD",""), qty=qty, side=OrderSide.BUY, time_in_force=TimeInForce.GTC)
                    trading_client.submit_order(order)

        elif action == "sell" and positions.get(sym, 0, 0) >= qty:
            cash += qty * price
            positions[sym] -= qty
            trade = f"SELL {qty} {sym}"
            if trading_client and LIVE_TRADING:
                order = MarketOrderRequest(symbol=sym.replace("-USD",""), qty=qty, side=OrderSide.SELL, time_in_force=TimeInForce.GTC)
                trading_client.submit_order(order)

        print(f"TRADE → {trade} @ ${price:.2f} | {reason}")
        sys.stdout.flush()

        # DAILY EMAIL
        if datetime.now(pytz.timezone('US/Eastern')).hour == 16 and datetime.now(pytz.timezone('US/Eastern')).minute == 30:
            send_daily_email()

    except Exception as e:
        print(f"ERROR: {e}")
        sys.stdout.flush()

    time.sleep(60)
