# 🔥 AstraTrader  
### **Autonomous Multi-Agent AI Trading Platform for the Indian Stock Market (NSE)**  
A next-generation agentic AI system featuring autonomous traders, research tools, MCP servers, portfolio analytics, real-time market data, and TradingView-style visualizations.

---

## 🌟 Overview

**AstraTrader** is a fully autonomous, multi-agent AI trading ecosystem designed for the **Indian stock market (NSE)**.  
It orchestrates multiple AI traders, each with unique investment personalities, executes trades through MCP tools, creates portfolio snapshots, and displays advanced candlestick charts in a rich Gradio dashboard.

This project demonstrates:

- Multi-agent autonomy  
- MCP tool-calling (Accounts, Market, Push servers)  
- Real-time market data (Yahoo NSE + Polygon US)  
- Portfolio value tracking with OHLCV candles  
- Real-time logs  
- TradingView-grade UI with neon glow  
- SQLite-backed persistence  
- Scheduled autonomous trading  

---

## 🚀 Key Features

### 🤖 **1. Autonomous Multi-Agent Traders**
Four AI traders operate independently with distinct personalities:

| Trader | Model | Style |
|--------|--------|--------|
| **Warren** | GPT-4o mini | Value investing, patience |
| **George** | GPT-4o mini | Bold, aggressive macro trading |
| **Ray** | GPT-4o mini | Risk-parity, systematic |
| **Cathie** | GPT-4o mini | Innovation, growth, crypto ETFs |

Each trader:
- Loads its own long-term strategy  
- Validates NSE tickers (RELIANCE.NS, TCS.NS, etc.)  
- Executes buy/sell via MCP  
- Tracks holdings, balance & PNL  
- Logs all actions  
- Records portfolio snapshots  

---

### 📈 **2. TradingView-Style OHLCV Charts**

- Beautiful candlestick charts  
- Volume bars with sentiment color  
- MA10 & MA20 moving averages  
- High/Low dotted markers  
- Neon-glow TradingView dark theme  
- Smooth Plotly rendering  

---

### 🧠 **3. Research Agent (NSE-Safe)**

A dedicated research agent that:
- Validates stock symbols  
- Analyzes Indian stock data  
- Summarizes opportunities for the traders  
- Avoids invalid/delisted tickers  

---

### 🔌 **4. MCP Tool Ecosystem**

| MCP Server | Purpose |
|------------|---------|
| **accounts_server.py** | Holdings, balance, PNL, transactions, strategy |
| **market_server.py** | Fetch market prices (NSE via Yahoo, US via Polygon) |
| **push_server.py** | Pushover notifications |

Agents interact with these tools using natural language & structured input.

---

### 💾 **5. SQLite Persistence Layer**

Persistent storage for:
- Accounts  
- Holdings  
- Logs  
- Transactions  
- Market cache  
- Portfolio snapshots (for OHLC candles)  

---

### 🖥️ **6. Rich Gradio Dashboard**

- Live session for all traders  
- Dynamic PNL panels  
- Portfolio candlestick chart  
- Volume overlays  
- Real-time logs (color-coded)  
- Holdings viewer  
- Transactions viewer  
- Recorded session playback  

---

## 📸 Live Interface Screenshot

Below is the live session:


### 🔥 Live Session View
![Live Session](screenshots/Screenshot%202025-11-15%20102350.png)

---

### 📊 Portfolio Overview & Candlestick Chart
![Portfolio Chart](screenshots/Screenshot%202025-11-15%20105503.png)

---

### 📝 Live Logs, Holdings & Recent Transactions
![Logs View](screenshots/Screenshot%202025-11-15%20105527.png)

---

### 🕯️ Trader Portfolio OHLCV Chart (Cathie Example)
![Cathie Portfolio Chart](screenshots/Screenshot%202025-11-15%20105517.png)


Each panel shows:
- Portfolio value  
- Candle chart  
- Volume  
- Logs  
- Trader model & style  

---

## 🏗️ System Architecture

AstraTrader follows a modular, event-driven, multi-agent architecture built on MCP servers, LLM agents, and a persistent data layer.

