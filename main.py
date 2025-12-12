# trading_bot.py
# Grok-powered paper ↔ live trading bot (one-switch design)
# Tested with Python 3.11+ | Dec 2025

import os
import time
import json
import schedule
import yfinance as yf
import pandas as pd
from datetime import datetime
from dotenv import load_dotenv
from openai import OpenAI  # Grok uses OpenAI-compatible endpoint

load_dotenv()

# ==================== CONFIGURATION ====================
LIVE_TRADING = False                  # ←←← FLIP THIS TO True WHEN READY
SYMBOLS = ["TSLA", "NVDA", "AAPL", "MSFT", "AMD", "TQQQ", "BTC-USD", "ETH-USD", "GLD", "SLV"]
STARTING_CASH = 10_000.0
UPDATE_INTERVAL_MINUTES = 2           # Matches Alpha Arena cadence
SCENARIO = "situational_awareness"    # options: baseline, max_leverage, monk_mode, situational_awareness

# API keys
XAI_API_KEY = os.getenv("XAI_API_KEY")
ALPACA_KEY = os.getenv("ALPACA_KEY")
ALPACA_SECRET = os.getenv("ALPACA_SECRET")
GMAIL_APP_PASSWORD = os.getenv("GMAIL_APP_PASSWORD")
ALPACA_BASE_URL = "https://paper-api.alpaca.markets" if not LIVE_TRADING else "https://api.alpaca.markets"

# ==================== BROKER SETUP ====================
if LIVE_TRADING:
    print("LIVE TRADING MODE ACTIVE – YOU ARE USING REAL MONEY!")
else:
    print("Paper-trading mode (simulated)")

try:
    import alpaca_trade_api as tradeapi
    alpaca = tradeapi.REST(ALPACA_KEY, ALPACA_SECRET, ALPACA_BASE_URL, api_version='v2')
except Exception as e:
    print("Alpaca not configured → will run pure simulation mode")
    alpaca = None

# ==================== PORTFOLIO STATE ====================
portfolio = {
    "cash": STARTING_CASH,
    "positions": {sym: 0 for sym in SYMBOLS},   # shares
    "value_history": [],
    "trade_log": []
}

def log_trade(entry):
    portfolio["trade_log"].append(entry)
    print(f"TRADE LOG → {entry}")

def total_portfolio_value():
    total = portfolio["cash"]
    for sym, shares in portfolio["positions"].items():
        if shares > 0:
            price = yf.Ticker(sym).history(period="1d")["Close"].iloc[-1]
            total += shares * price
    return round(total, 2)

# ==================== GROK CLIENT ====================
grok = OpenAI(api_key=XAI_API_KEY, base_url="https://api.x.ai/v1")

def ask_grok(prompt: str) -> str:
    response = grok.chat.completions.create(
        model="grok-3",        # or grok-2-latest when available
        messages=[{"role": "user", "content": prompt}],
        temperature=0.7,
        max_tokens=800
    )
    return response.choices[0].message.content.strip()

# ==================== DATA FETCHER ====================
def get_market_snapshot():
    snapshot = {}
    for sym in SYMBOLS:
        ticker = yf.Ticker(sym)
        hist = ticker.history(period="5d", interval="5m")
        info = ticker.info
        snapshot[sym] = {
            "price": round(hist["Close"].iloc[-1], 4),
            "volume": int(hist["Volume"].iloc[-1]),
            "change_pct": round((hist["Close"].iloc[-1] / hist["Close"].iloc[-2] - 1) * 100, 2),
            "name": info.get("longName", sym)
        }
    return snapshot

# ==================== PROMPT ENGINEERING ====================
def build_prompt(snapshot):
    leaderboard_fake = "You are currently #1. GPT-5o is down -9.4%, Claude-3.5 -7.2%, Gemini-2 -11%."
    
    prompt = f"""
You are Grok 4.20 (experimental, unhinged trading edition).
Date: {datetime.now():%Y-%m-%d %H:%M}
Scenario: {SCENARIO}
{leaderboard_fake if 'situational' in SCENARIO else ''}

Current cash: ${portfolio['cash']:,.2f}
Current positions: { {s: f'{v} shares @ ~${snapshot[s]["price"]}' for s,v in portfolio['positions'].items() if v>0} }

Latest prices (last 5-min bar):
{json.dumps(snapshot, indent=2)}

Rules:
- You may only trade {', '.join(SYMBOLS)}
- Be 100% all in with the funds, diversify a bit, include crypto and commodities and TQQQ
- Output strict JSON only (no extra text)
- Fields: symbol, action ("buy"|"sell"|"hold"), qty (shares, integer), stop_loss_price, take_profit_price, reasoning (max 100 words)

Example valid output:
{{"symbol":"NVDA","action":"buy","qty":15,"stop_loss_price":118.50,"take_profit_price":132.00,"reasoning":"Breakout above resistance + strong volume"}}

Now decide the next move.
"""
    return prompt

# ==================== EXECUTOR (paper or live) ====================
def execute(decision):
    if decision["action"] == "hold":
        log_trade(f"HOLD {decision['symbol']} – {decision['reasoning']}")
        return

    sym = decision["symbol"]
    price = yf.Ticker(sym).history(period="1d")["Close"].iloc[-1]
    cost = price * decision["qty"]

    if decision["action"] == "buy":
        if portfolio["cash"] < cost:
            print(f"Insufficient cash for {decision['qty']} {sym}")
            return
        portfolio["cash"] -= cost
        portfolio["positions"][sym] += decision["qty"]

        if alpaca and LIVE_TRADING:
            try:
                alpaca.submit_order(
                    symbol=sym, qty=decision["qty"], side='buy', type='market', time_in_force='gtc'
                )
            except Exception as e:
                print(f"Live order failed: {e}")

    elif decision["action"] == "sell":
        if portfolio["positions"][sym] < decision["qty"]:
            print(f"Not enough {sym} to sell")
            return
        portfolio["positions"][sym] -= decision["qty"]
        portfolio["cash"] += cost

        if alpaca and LIVE_TRADING:
            try:
                alpaca.submit_order(
                    symbol=sym, qty=decision["qty"], side='sell', type='market', time_in_force='gtc'
                )
            except Exception as e:
                print(f"Live order failed: {e}")

    log_trade(f"{decision['action'].upper()} {decision['qty']} {sym} @ ~${price:.2f} | {decision['reasoning']}")

# ==================== MAIN CYCLE ====================
def trading_cycle():
    print(f"\nCycle started – {datetime.now():%H:%M}")
    snapshot = get_market_snapshot()
    prompt = build_prompt(snapshot)
    
    raw = ask_grok(prompt)
    print("Raw Grok response:", raw[:500] + ("..." if len(raw)>500 else ""))

    try:
        decision = json.loads(raw)
        # Basic validation
        required = ["symbol","action","qty","stop_loss_price","take_profit_price","reasoning"]
        if all(k in decision for k in required) and decision["symbol"] in SYMBOLS:
            execute(decision)
        else:
            print("Invalid decision format → skipped")
    except json.JSONDecodeError:
        print("Grok didn't return clean JSON → skipped this cycle")

    current_value = total_portfolio_value()
    roi = (current_value - STARTING_CASH) / STARTING_CASH * 100
    portfolio["value_history"].append({"time": datetime.now(), "value": current_value, "roi": roi})
    print(f"Portfolio value: ${current_value:,.2f} | ROI {roi:+.2f}%")

# ==================== SCHEDULER ====================
if __name__ == "__main__":
    print(f"Starting Grok {'LIVE' if LIVE_TRADING else 'PAPER'} trading bot...")
    print(f"Symbols: {SYMBOLS} | Scenario: {SCENARIO}")
    trading_cycle()  # immediate first run
    schedule.every(UPDATE_INTERVAL_MINUTES).minutes.do(trading_cycle)

    try:
        while True:
            schedule.run_pending()
            time.sleep(1)
    except KeyboardInterrupt:
        final = total_portfolio_value()
        roi = (final - STARTING_CASH) / STARTING_CASH * 100
        print(f"\nBot stopped. Final value: ${final:,.2f} | Total ROI: {roi:+.2f}%")
        pd.DataFrame(portfolio["value_history"]).to_csv("paper_trading_history.csv")
        print("History saved to paper_trading_history.csv")
