# grok_trader_server.py — 24/7 headless version for Render
import time
import json
import yfinance as yf
from datetime import datetime
from openai import OpenAI
import os
from dotenv import load_dotenv
load_dotenv()

LIVE_TRADING = False
SYMBOLS = ["TQQQ", "QQQ", "SOXL", "NVDA", "COIN"]
SCENARIO = "situational_awareness"

client = OpenAI(api_key=os.getenv("XAI_API_KEY"), base_url="https://api.x.ai/v1")

# Only import Alpaca if keys exist
if os.getenv("ALPACA_KEY") and os.getenv("ALPACA_SECRET"):
    from alpaca_trade_api import REST
    alpaca = REST(os.getenv("ALPACA_KEY"), os.getenv("ALPACA_SECRET"), base_url='https://paper-api.alpaca.markets' if not LIVE_TRADING else 'https://api.alpaca.markets')
else:
    alpaca = None

cash = 1000000.0
positions = {s: 0 for s in SYMBOLS}
risk_percent = 90

print("Grok Trader LIVE — Real money mode" if LIVE_TRADING else "Paper trading mode")
print(f"Starting cash: ${cash:,.2f}")

while True:
    try:
        prices = {s: yf.Ticker(s).history(period="1d")["Close"].iloc[-1] for s in SYMBOLS}
        total = cash + sum(positions.get(s,0) * prices[s] for s in SYMBOLS)
        print(f"\n{datetime.now().strftime('%H:%M:%S')} | Portfolio: ${total:,.0f} | Cash: ${cash:,.0f}")

        prompt = f"Cash ${cash:,.0f} | Risk {risk_percent}% | Positions {positions} | Prices {json.dumps({s:round(prices[s],2) for s in SYMBOLS})} → JSON: {{symbol,action:'buy'|'sell'|'hold',qty:int,reasoning:string}}"
        resp = client.chat.completions.create(model="grok-3", messages=[{"role":"user","content":prompt}], temperature=0.8)
        decision = json.loads(resp.choices[0].message.content.strip())

        sym = decision.get("symbol","TQQQ")
        action = decision.get("action","hold")
        qty = decision.get("qty",0)
        reason = decision.get("reasoning","")

        price = prices[sym]
        trade = "HOLD"

        if action == "buy" and qty > 0:
            max_qty = int((cash * risk_percent / 100) // price)
            qty = min(qty, max_qty)
            if qty > 0:
                cash -= qty * price
                positions[sym] = positions.get(sym,0) + qty
                trade = f"BUY {qty} {sym}"
                if alpaca and LIVE_TRADING:
                    alpaca.submit_order(symbol=sym, qty=qty, side='buy', type='market', time_in_force='gtc')
        elif action == "sell" and positions.get(sym,0,0) >= qty:
            cash += qty * price
            positions[sym] -= qty
            trade = f"SELL {qty} {sym}"
            if alpaca and LIVE_TRADING:
                alpaca.submit_order(symbol=sym, qty=qty, side='sell', type='market', time_in_force='gtc')

        print(f"TRADE → {trade} @ ${price:.2f} | {reason}")

    except Exception as e:
        print(f"Error: {e}")

    time.sleep(60)  # 1-minute trades
