# main.py — 24/7 headless real-money Grok Trader (Render-ready)
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

# Modern Alpaca SDK
if os.getenv("ALPACA_KEY") and os.getenv("ALPACA_SECRET"):
    from alpaca.trading.client import TradingClient
    from alpaca.trading.requests import MarketOrderRequest
    from alpaca.trading.enums import OrderSide, TimeInForce

    trading_client = TradingClient(
        os.getenv("ALPACA_KEY"),
        os.getenv("ALPACA_SECRET"),
        paper=not LIVE_TRADING
    )
else:
    trading_client = None

cash = 1000000.0
positions = {s: 0 for s in SYMBOLS}
risk_percent = 90

print("GROK TRADER LIVE — REAL MONEY MODE" if LIVE_TRADING else "Paper mode")
print(f"Starting cash: ${cash:,.2f}")

while True:
    try:
        prices = {s: yf.Ticker(s).history(period="1d")["Close"].iloc[-1] for s in SYMBOLS}
        total = cash + sum(positions.get(s, 0) * prices[s] for s in SYMBOLS)
        print(f"\n{datetime.now().strftime('%H:%M:%S')} | Portfolio: ${total:,.0f} | Cash: ${cash:,.0f}")

        prompt = f"Cash ${cash:,.0f} | Risk {risk_percent}% | Positions {positions} | Prices {json.dumps({s: round(prices[s], 2) for s in SYMBOLS})} → JSON: {{symbol,action:'buy'|'sell'|'hold',qty:int,reasoning:string}}"
        resp = client.chat.completions.create(model="grok-3", messages=[{"role": "user", "content": prompt}], temperature=0.8)
        d = json.loads(resp.choices[0].message.content.strip())

        sym = d.get("symbol", "TQQQ")
        action = d.get("action", "hold")
        qty = d.get("qty", 0)
        reason = d.get("reasoning", "")

        price = prices[sym]
        trade = "HOLD"

        if action == "buy" and qty > 0:
            max_qty = int((cash * risk_percent / 100) // price)
            qty = min(qty, max_qty)
            if qty > 0:
                cash -= qty * price
                positions[sym] = positions.get(sym, 0) + qty
                trade = f"BUY {qty} {sym}"
                if trading_client and LIVE_TRADING:
                    order = MarketOrderRequest(symbol=sym, qty=qty, side=OrderSide.BUY, time_in_force=TimeInForce.GTC)
                    trading_client.submit_order(order)

        elif action == "sell" and positions.get(sym, 0, 0) >= qty:
            cash += qty * price
            positions[sym] -= qty
            trade = f"SELL {qty} {sym}"
            if trading_client and LIVE_TRADING:
                order = MarketOrderRequest(symbol=sym, qty=qty, side=OrderSide.SELL, time_in_force=TimeInForce.GTC)
                trading_client.submit_order(order)

        print(f"TRADE → {trade} @ ${price:.2f} | {reason}")

    except Exception as e:
        print(f"ERROR: {e}")

    time.sleep(60)  # 1-minute trades
