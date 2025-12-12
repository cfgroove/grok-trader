# main.py — LOCAL TEST VERSION (email works instantly)
import time
import json
import yfinance as yf
import pytz
from datetime import datetime
from openai import OpenAI
import os
import sys
from dotenv import load_dotenv
import smtplib
from email.mime.text import MIMEText

load_dotenv()

# Force email test mode
FORCE_EMAIL_TEST = True   # ← Set to False when done testing

client = OpenAI(api_key=os.getenv("XAI_API_KEY"), base_url="https://api.x.ai/v1")

cash = 1_000_000.0
positions = {"TQQQ": 8000}  # fake position so email has something to show

def total_value():
    try:
        prices = {s: yf.Ticker(s).history(period="1d")["Close"].iloc[-1] for s in ["TQQQ", "NVDA"]}
        return cash + sum(positions.get(s,0) * prices.get(s,0) for s in positions)
    except:
        return cash

def send_daily_email():
    est = pytz.timezone('US/Eastern')
    now = datetime.now(est)
    value = total_value()
    roi = (value - 1_000_000) / 1_000_000 * 100

    body = f"""
    <h2>Grok Trader Daily Report — TEST MODE</h2>
    <p><strong>Time:</strong> {now.strftime('%I:%M %p %Z')}</p>
    <p><strong>Portfolio:</strong> ${value:,.2f}</p>
    <p><strong>ROI:</strong> {roi:+.2f}%</p>
    <p><strong>Cash:</strong> ${cash:,.2f}</p>
    <p>This is a test — you're crushing it.</p>
    """

    msg = MIMEText(body, "html")
    msg["Subject"] = f"Grok Trader TEST — {roi:+.2f}%"
    msg["From"] = "Grok Trader <cfgroove@gmail.com>"
    msg["To"] = "chase@cfgroove.com"

    try:
        with smtplib.SMTP("smtp.gmail.com", 587) as server:
            server.starttls()
            server.login("cfgroove@gmail.com", os.getenv("GMAIL_APP_PASSWORD"))
            server.send_message(msg)
        print("EMAIL SENT SUCCESSFULLY — check your inbox!")
    except Exception as e:
        print(f"EMAIL FAILED: {e}")

# Run once and exit — perfect for testing
print("Sending test email in 5 seconds...")
time.sleep(5)
send_daily_email()
print("Test complete. You're ready for Render.")
