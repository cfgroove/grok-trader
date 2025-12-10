# main.py — 24/7 Grok Trader with daily email from cfgroove@gmail.com
import time
import json
import yfinance as yf
from datetime import datetime, date
from openai import OpenAI
import os
import sys
from dotenv import load_dotenv
import smtplib
from email.mime.text import MIMEText
load_dotenv()

LIVE_TRADING = False
SYMBOLS = ["TQQQ", "SOXL", "QQQ", "NVDA", "TSLA", "GLD", "SLV", "BTC-USD", "COIN"]
SCENARIO = "situational_awareness"

client = OpenAI(api_key=os.getenv("XAI_API_KEY"), base_url="https://api.x.ai/v1")

# Alpaca (unchanged)
if os.getenv("ALPACA_KEY") and os.getenv("ALPACA_SECRET"):
    from alpaca.trading.client import TradingClient
    from alpaca.trading.requests import MarketOrderRequest
    from alpaca.trading.enums import OrderSide, TimeInForce
    trading_client = TradingClient(os.getenv("ALPACA_KEY"), os.getenv("ALPACA_SECRET"), paper=not LIVE_TRADING)
else:
    trading_client = None

cash = 1000000.0
positions = {s: 0 for s in SYMBOLS}
risk_percent = 90
last_email_date = None

def safe_json_parse(text):
    try: return json.loads(text)
    except:
        try: return json.loads(text.strip()[text.find("{"):text.rfind("}")+1])
        except: return {"symbol":"TQQQ","action":"hold","qty":0,"reasoning":"JSON parse failed — holding"}

def send_daily_email():
    global last_email_date
    if last_email_date == date.today():
        return
    prices = {s: yf.Ticker(s).history(period="1d")["Close"].iloc[-1] for s in SYMBOLS}
    total = cash + sum(positions.get(s,0) * prices[s] for s in SYMBOLS)
    daily_pnl = total - 1000000
    daily_pct = daily_pnl / 1000000 * 100

    body = f"""
    <h2>Grok Trader Daily Report — {date.today()}</h2>
    <p><strong>Portfolio Value:</strong> ${total:,.2f}</p>
    <p><strong>Daily P&L:</strong> ${daily_pnl:,.2f} ({daily_pct:+.2f}%)</p>
    <p><strong>Cash:</strong> ${cash:,.2f}</p>
    <p><strong>Positions:</strong><br>
    {''.join([f"{s}: {positions.get(s,0)} shares @ ${prices[s]:.2f}<br>" for s in SYMBOLS if positions.get(s,0)>0]) or "None"}
    </p>
    <p><em>Live trading: {'ON' if LIVE_TRADING else 'OFF (paper)'}</em></p>
    """

    msg = MIMEText(body, "html")
    msg["Subject"] = f"Grok Trader Report — {date.today()} — {daily_pct:+.2f}%"
    msg["From"] = "Grok Trader <cfgroove@gmail.com>"
    msg["To"] = "chase@cfgroove.com"

    with smtplib.SMTP("smtp.gmail.com", 587) as server:
        server.starttls()
        server.login("cfgroove@gmail.com", os.getenv("GMAIL_APP_PASSWORD"))
        server.send_message(msg)

    print(f"Daily email sent — {daily_pct:+.2f}%")
    sys.stdout.flush()
    last_email_date = date.today()

print("GROK TRADER LIVE — DAILY EMAILS ENABLED")
sys.stdout.flush()

while True:
    try:
        prices = {s: yf.Ticker(s).history(period="1d")["Close"].iloc[-1] for s in SYMBOLS}
        total = cash + sum(positions.get(s,0) * prices[s] for s in SYMBOLS)
        print(f"\n{datetime.now().strftime('%H:%M:%S')} | ${total:,.0f} | Cash ${cash:,.0f}")
        sys.stdout.flush()

        prompt = f"Cash ${cash:,.0f} | Risk {risk_percent}% | Positions {positions} | Prices {json.dumps({s: round(prices[s], 2) for s in SYMBOLS})} → JSON: {{symbol,action:'buy'|'sell'|'hold',qty:int,reasoning:string}}"
        resp = client.chat.completions.create(model="grok-3", messages=[{"role":"user","content":prompt}], temperature=0.85)
        d = safe_json_parse(resp.choices[0].message.content.strip())

        sym = d.get("symbol","TQQQ") if d.get("symbol") in SYMBOLS else "TQQQ"
        action = d.get("action","hold")
        qty = d.get("qty",0)
        reason = d.get("reasoning","")

        price = prices[sym]
        trade = "HOLD"

        if action == "buy" and qty > 0:
            max_qty = int((cash * risk_percent / 100) // price)
            qty = min(qty, max_qty)
            if qty > 0:
                cash -= qty * price
                positions[sym] = positions.get(sym,0) + qty
                trade = f"BUY {qty} {sym}"
                if trading_client and LIVE_TRADING:
                    order = MarketOrderRequest(symbol=sym.replace("-USD",""), qty=qty, side=OrderSide.BUY, time_in_force=TimeInForce.GTC)
                    trading_client.submit_order(order)
        elif action == "sell" and positions.get(sym,0,0) >= qty:
            cash += qty * price
            positions[sym] -= qty
            trade = f"SELL {qty} {sym}"
            if trading_client and LIVE_TRADING:
                order = MarketOrderRequest(symbol=sym.replace("-USD",""), qty=qty, side=OrderSide.SELL, time_in_force=TimeInForce.GTC)
                trading_client.submit_order(order)

        print(f"TRADE → {trade} @ ${price:.2f} | {reason}")
        sys.stdout.flush()

        # Daily email at 4:30 PM ET
        now = datetime.now()
        if now.hour == 16 and now.minute == 30:
            send_daily_email()

    except Exception as e:
        print(f"ERROR: {e}")
        sys.stdout.flush()

    time.sleep(60)
