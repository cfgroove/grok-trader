# main.py — ZERO ERRORS + CLEAN LOGS + CLEAR PORTFOLIO UPDATES
import time
import json
import yfinance as yf
from datetime import datetime
from openai import OpenAI
import os
import sys
from dotenv import load_dotenv
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

def safe_json_parse(text):
    # Bulletproof JSON extraction — finds the first complete {} block
    text = text.strip()
    start = text.find('{')
    if start == -1:
        return {"symbol": "TQQQ", "action": "hold", "qty": 0, "reasoning": "No JSON found"}
    
    # Find matching closing brace
    brace_count = 0
    end = start
    for i, char in enumerate(text[start:], start):
        if char == '{':
            brace_count += 1
        elif char == '}':
            brace_count -= 1
            if brace_count == 0:
                end = i + 1
                break
    
    json_str = text[start:end]
    try:
        return json.loads(json_str)
    except:
        # Last resort — default to hold
        return {"symbol": "TQQQ", "action": "hold", "qty": 0, "reasoning": "JSON parse failed — holding position"}

print("GROK TRADER LIVE — BULLETPROOF JSON + CLEAN LOGS")
print(f"Starting cash: ${cash:,.2f}")
sys.stdout.flush()

while True:
    try:
        prices = {s: yf.Ticker(s).history(period="1d")["Close"].iloc[-1] for s in SYMBOLS}
        total = cash + sum(positions.get(s, 0) * prices[s] for s in SYMBOLS)

        # CLEAR PORTFOLIO UPDATE — every minute
        print(f"\n=== {datetime.now().strftime('%H:%M:%S')} PORTFOLIO ===")
        print(f"TOTAL VALUE: ${total:,.0f} | CASH: ${cash:,.0f} | ROI: {((total - 1000000) / 1000000 * 100):+.2f}%")
        sys.stdout.flush()

        prompt = f"Cash ${cash:,.0f} | Risk {risk_percent}% | Positions {positions} | Prices {json.dumps({s: round(prices[s], 2) for s in SYMBOLS})}. {SCENARIO} Output ONLY valid JSON (no extra text): {{'symbol':str,'action':'buy'|'sell'|'hold','qty':int,'reasoning':str}}"
        resp = client.chat.completions.create(model="grok-3", messages=[{"role": "user", "content": prompt}], temperature=0.85, max_tokens=150)
        d = safe_json_parse(resp.choices[0].message.content.strip())

        sym = d.get("symbol", "TQQQ")
        if sym not in SYMBOLS:
            sym = "TQQQ"
        action = d.get("action", "hold")
        qty = d.get("qty", 0)
        reason = d.get("reasoning", "No reasoning")

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
                    order_symbol = sym.replace("-USD", "")
                    order = MarketOrderRequest(symbol=order_symbol, qty=qty, side=OrderSide.BUY, time_in_force=TimeInForce.GTC)
                    trading_client.submit_order(order)

        elif action == "sell" and positions.get(sym, 0, 0) >= qty:
            cash += qty * price
            positions[sym] -= qty
            trade = f"SELL {qty} {sym}"
            if trading_client and LIVE_TRADING:
                order_symbol = sym.replace("-USD", "")
                order = MarketOrderRequest(symbol=order_symbol, qty=qty, side=OrderSide.SELL, time_in_force=TimeInForce.GTC)
                trading_client.submit_order(order)

        # CLEAN TRADE LOG — no spam
        print(f"TRADE: {trade} {sym} @ ${price:.2f} | {reason[:100]}...")  # Truncate reasoning
        sys.stdout.flush()

    except Exception as e:
        print(f"CRITICAL ERROR: {e}")
        sys.stdout.flush()

    time.sleep(60)
