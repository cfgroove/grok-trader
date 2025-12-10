import webview
import threading
import time
import json
import yfinance as yf
from datetime import datetime
from openai import OpenAI
import os
from dotenv import load_dotenv
load_dotenv()

LIVE_TRADING = False
SYMBOLS = ["TQQQ", "QQQ", "SOXL", "NVDA", "COIN"]  # High volatility mode
SCENARIO = "You are a savage, opinionated AI trader. Be direct, funny, and honest."

client = OpenAI(api_key=os.getenv("XAI_API_KEY"), base_url="https://api.x.ai/v1")

portfolio = {"cash": 1000000.0, "positions": {s: 0 for s in SYMBOLS}, "trades": []}
risk_percent = 90
chat_history = [{"role": "system", "content": "You are Grok Trader — a brutally honest, high-conviction AI trader. Answer fast, be funny, roast bad ideas, explain every move."}]

HTML_WITH_CHAT = """<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<title>Grok Trader • Ultimate + Chat</title>
<script src="https://cdn.jsdelivr.net/npm/lightweight-charts@4.1.3/dist/lightweight-charts.standalone.production.js"></script>
<style>
@import url('https://fonts.googleapis.com/css2?family=Orbitron:wght@500;900&family=Inter&display=swap');
*{margin:0;padding:0;box-sizing:border-box;}
body,html{height:100%;background:#000;color:#fff;font-family:'Inter',sans-serif;overflow:hidden;}
canvas{position:fixed;top:0;left:0;width:100%;height:100%;z-index:-1;}
.glass{background:rgba(15,15,45,0.5);backdrop-filter:blur(20px);border:1px solid rgba(100,200,255,0.3);border-radius:20px;padding:20px;margin:15px;box-shadow:0 10px 40px rgba(0,255,255,0.2);}
h1{font-family:'Orbitron';font-size:3.8rem;text-align:center;background:linear-gradient(90deg,#00ffff,#ff00ff);-webkit-background-clip:text;-webkit-text-fill-color:transparent;}
.value{font-size:5rem;text-align:center;font-weight:900;text-shadow:0 0 30px #00ffff;}
.roi{font-size:2.8rem;text-align:center;}
.green{color:#00ffaa;text-shadow:0 0 20px #00ffaa;}
.red{color:#ff3366;text-shadow:0 0 20px #ff3366;}
.chat-container{background:rgba(0,0,30,0.8);height:280px;display:flex;flex-direction:column;border-radius:15px;overflow:hidden;margin:20px;}
#messages{flex:1;padding:15px;overflow-y:auto;font-size:15px;}
#messages .user{text-align:right;background:#007aff;color:white;padding:10px;border-radius:12px;margin:5px;max-width:80%;}
#messages .grok{text-align:left;background:#333;color:#00ffff;padding:10px;border-radius:12px;margin:5px;max-width:80%;border-left:4px solid #00ffff;}
.input-area{display:flex;padding:10px;background:#111;}
#userInput{flex:1;padding:12px;background:#222;border:none;border-radius:12px;color:white;font-size:16px;}
#sendBtn{background:#00ffff;color:black;padding:12px 20px;border:none;border-radius:12px;margin-left:10px;cursor:pointer;font-weight:bold;}
.btn{background:linear-gradient(45deg,#4488ff,#ff00aa);padding:16px 50px;font-size:24px;border-radius:50px;cursor:pointer;}
.log{height:200px;overflow-y:auto;background:rgba(0,0,30,0.7);padding:15px;border-radius:15px;font-size:14px;}
</style>
</head>
<body>
<canvas id="space"></canvas>
<div class="glass">
<h1>Grok Trader • Ultimate + Chat</h1>
<div class="value" id="value">$1,000,000.00</div>
<div class="roi" id="roi">ROI: +0.00%</div>
<div style="text-align:center;margin:30px;">
<button class="btn" onclick="pywebview.api.toggle()">Start / Stop Bot</button>
</div>
<div class="log" id="log">Ready — say hi below</div>

<h2 style="color:#00ffff;text-align:center;margin:20px 0;">Talk to Grok</h2>
<div class="chat-container">
    <div id="messages"><div class="grok">yo, what's up boss? market's moving. ask me anything or tell me what to do.</div></div>
    <div class="input-area">
        <input type="text" id="userInput" placeholder="Type message..." onkeypress="if(event.key==='Enter')send()">
        <button id="sendBtn" onclick="send()">Send</button>
    </div>
</div>
</div>

<script>
function send(){let input=document.getElementById('userInput'); let msg=input.value.trim(); if(!msg)return; addMessage(msg,'user'); input.value=''; pywebview.api.chat(msg);}
function addMessage(text, sender){let m=document.getElementById('messages'); m.innerHTML+=`<div class="${sender}">${text}</div>`; m.scrollTop=m.scrollHeight;}
function log(m){document.getElementById('log').innerHTML+=new Date().toLocaleTimeString()+" → "+m+"<br>";document.getElementById('log').scrollTop=document.getElementById('log').scrollHeight;}
function update(d){
    document.getElementById('value').innerText="$"+parseFloat(d.value).toFixed(2).replace(/\\B(?=(\\d{3})+(?!\\d))/g,",");
    let c=d.roi>=0?"green":"red"; document.getElementById('roi').innerHTML=`<span class="${c}">ROI: ${d.roi>=0?"+":""}${d.roi.toFixed(2)}%</span>`;
}
const c=document.getElementById('space'),ctx=c.getContext('2d');c.width=innerWidth;c.height=innerHeight;
let s=[];for(let i=0;i<500;i++)s.push({x:Math.random()*c.width,y:Math.random()*c.height,z:Math.random()*2+0.5,sp:Math.random()*0.6+0.1});
function draw(){ctx.fillStyle='rgba(0,0,0,0.06)';ctx.fillRect(0,0,c.width,c.height);
s.forEach(t=>{t.y+=t.sp;if(t.y>c.height)t.y=0;ctx.fillStyle='#fff';ctx.beginPath();ctx.arc(t.x,t.y,t.z,0,Math.PI*2);ctx.fill();});
requestAnimationFrame(draw);}draw();
</script>
</body>
</html>"""

class Api:
    def toggle(self):
        if hasattr(self,'running') and self.running: self.running=False
        else: self.running=True; threading.Thread(target=self.loop,daemon=True).start()

    def chat(self, user_message):
        global chat_history
        chat_history.append({"role": "user", "content": user_message})
        try:
            resp = client.chat.completions.create(
                model="grok-3", messages=chat_history, temperature=0.9, max_tokens=500
            )
            grok_reply = resp.choices[0].message.content
            chat_history.append({"role": "assistant", "content": grok_reply})
            window.evaluate_js(f'addMessage(`{grok_reply.replace("`","\\`")}`,"grok")')
        except Exception as e:
            window.evaluate_js(f'addMessage("error: {str(e)[:100]}","grok")')

    def loop(self):
        while self.running:
            try:
                prices = {s: yf.Ticker(s).history(period="1d")["Close"].iloc[-1] for s in SYMBOLS}
                total = portfolio["cash"] + sum(portfolio["positions"].get(s,0)*prices[s] for s in SYMBOLS)
                roi = (total-1000000)/1000000*100
                prompt = f"Portfolio: {portfolio['positions']} | Cash ${portfolio['cash']:,.0f} | Prices {json.dumps({s:round(prices[s],2) for s in SYMBOLS})} → JSON: {{symbol,action:'buy'|'sell'|'hold',qty:int,reasoning:string}}"
                resp = client.chat.completions.create(model="grok-3", messages=[{"role":"user","content":prompt}], temperature=0.8)
                d = json.loads(resp.choices[0].message.content.strip())
                sym = d.get("symbol","TQQQ"); action = d.get("action","hold"); qty = d.get("qty",0); reason = d.get("reasoning","")
                price = prices[sym]
                trade = "HOLD"
                if action=="buy" and qty>0:
                    max_qty = int((portfolio["cash"]*risk_percent/100)//price); qty = min(qty,max_qty)
                    if qty>0: portfolio["cash"]-=qty*price; portfolio["positions"][sym]+=qty; trade=f"BUY {qty} {sym}"
                elif action=="sell" and portfolio["positions"].get(sym,0)>=qty:
                    portfolio["cash"]+=qty*price; portfolio["positions"][sym]-=qty; trade=f"SELL {qty} {sym}"
                total = portfolio["cash"] + sum(portfolio["positions"].get(s,0)*prices[s] for s in SYMBOLS)
                roi = (total-1000000)/1000000*100
                window.evaluate_js(f'update({json.dumps({"value":total,"roi":roi})})')
                window.evaluate_js(f'log("Trade: {trade} | {reason}")')
            except Exception as e: window.evaluate_js(f'log("Error: {str(e)[:100]}")')
            time.sleep(60)  # 1-minute trades

api = Api()
if __name__ == "__main__":
    window = webview.create_window("Grok Trader • Chat Edition", html=HTML_WITH_CHAT, js_api=api, width=1100, height=900)
    webview.start()