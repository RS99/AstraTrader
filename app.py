import gradio as gr
import pandas as pd
import plotly.graph_objects as go
import yfinance as yf
from util import css, js, Color
from trading_floor import names, lastnames, short_model_names
from accounts import Account
from database import read_log
from market import normalize_symbol

# -------------------------------------------------------------------
# COLOR MAP FOR LOGS
# -------------------------------------------------------------------
mapper = {
    "trace": Color.WHITE,
    "agent": Color.CYAN,
    "function": Color.GREEN,
    "generation": Color.YELLOW,
    "response": Color.MAGENTA,
    "account": Color.RED,
}

# -------------------------------------------------------------------
# SUPPORT FUNCTIONS
# -------------------------------------------------------------------

def load_full_logs(name: str):
    rows = read_log(name, last_n=500000)
    return "\n".join(f"{dt} [{t}] {msg}" for dt, t, msg in rows)


def load_portfolio_history(name: str):
    acc = Account.get(name)
    df = pd.DataFrame(acc.portfolio_value_time_series, columns=["datetime", "value"])
    if df.empty:
        return pd.DataFrame()
    df["datetime"] = pd.to_datetime(df["datetime"])
    return df


def load_transactions(name: str):
    acc = Account.get(name)
    if not acc.transactions:
        return pd.DataFrame(columns=["timestamp", "symbol", "quantity", "price", "rationale"])
    return pd.DataFrame([t.model_dump() for t in acc.transactions])


# -------------------------------------------------------------------
# OHLC DOWNLOAD 
# -------------------------------------------------------------------

def fetch_stock_ohlcv(symbol: str, period: str = "1mo", interval: str = "1d"):
    """Download OHLCV using yf.download() with proper NSE support."""
    if not symbol:
        return pd.DataFrame()

    try:
        try:
            sym = normalize_symbol(symbol.strip())
        except:
            sym = symbol.strip()

        df = yf.download(sym, period=period, interval=interval, progress=False, threads=False)

        # Fallback .NS
        if (df is None or df.empty) and not sym.endswith(".NS"):
            df = yf.download(sym + ".NS", period=period, interval=interval, progress=False, threads=False)

        if df is None or df.empty:
            return pd.DataFrame()

        df = df.reset_index()

        if "Date" not in df.columns:
            df.rename(columns={df.columns[0]: "Date"}, inplace=True)

        for c in ["Open", "High", "Low", "Close", "Volume"]:
            if c not in df.columns:
                df[c] = 0

        return df[["Date", "Open", "High", "Low", "Close", "Volume"]]

    except Exception as e:
        print(f"OHLC error for {symbol}: {e}")
        return pd.DataFrame()


# -------------------------------------------------------------------
# TradingView-Quality Candlestick Chart 
# -------------------------------------------------------------------

def stock_candlestick_fig(df: pd.DataFrame, title: str = "Stock OHLCV"):
    """BEAUTIFUL TradingView-style neon candlestick chart."""
    if df.empty:
        fig = go.Figure()
        fig.update_layout(title=title, height=450,
                          paper_bgcolor="#111", plot_bgcolor="#111")
        return fig

    bullish = df["Close"].iloc[-1] >= df["Open"].iloc[-1]
    bg_color = "rgba(0,255,140,0.06)" if bullish else "rgba(255,70,70,0.06)"

    vol_colors = [
        "rgba(0,255,140,0.5)" if df["Close"].iloc[i] >= df["Open"].iloc[i]
        else "rgba(255,70,70,0.5)"
        for i in range(len(df))
    ]

    fig = go.Figure()

    # --- CANDLES ---
    fig.add_trace(go.Candlestick(
        x=df["Date"],
        open=df["Open"], high=df["High"],
        low=df["Low"], close=df["Close"],
        increasing_line_color="#00ff8c",
        decreasing_line_color="#ff4646",
        increasing_fillcolor="rgba(0,255,140,0.6)",
        decreasing_fillcolor="rgba(255,70,70,0.6)",
        name="Candles"
    ))

    # --- VOLUME BARS ---
    fig.add_trace(go.Bar(
        x=df["Date"],
        y=df["Volume"],
        marker_color=vol_colors,
        opacity=0.45,
        yaxis="y2",
        name="Volume"
    ))

    # --- MOVING AVERAGES ---
    if len(df) > 10:
        df["MA10"] = df["Close"].rolling(10).mean()
        fig.add_trace(go.Scatter(
            x=df["Date"], y=df["MA10"],
            mode="lines",
            line=dict(color="#ffaa00", width=2),
            name="MA10"
        ))

    if len(df) > 20:
        df["MA20"] = df["Close"].rolling(20).mean()
        fig.add_trace(go.Scatter(
            x=df["Date"], y=df["MA20"],
            mode="lines",
            line=dict(color="#0099ff", width=2),
            name="MA20"
        ))

    # --- HIGH / LOW DASHED ---
    last = df.iloc[-1]
    fig.add_hline(y=last["High"], line_dash="dot", line_color="#00ff8c",
                  annotation_text=f"High: {last['High']:.2f}", annotation_position="top right")

    fig.add_hline(y=last["Low"], line_dash="dot", line_color="#ff4646",
                  annotation_text=f"Low: {last['Low']:.2f}", annotation_position="bottom right")

    # --- LAYOUT ---
    fig.update_layout(
        title=title,
        height=480,
        paper_bgcolor="#0b0b0b",
        plot_bgcolor=bg_color,

        font=dict(color="#ebebeb", size=13),

        xaxis=dict(
            showgrid=False,
            rangeslider=dict(visible=False),
        ),

        yaxis=dict(
            title="Price",
            gridcolor="rgba(255,255,255,0.07)"
        ),

        yaxis2=dict(
            overlaying="y",
            side="right",
            showgrid=False
        ),

        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.02,
            xanchor="right",
            x=1,
            bgcolor="rgba(0,0,0,0.3)"
        ),

        margin=dict(l=50, r=50, t=50, b=40)
    )

    return fig


# -------------------------------------------------------------------
# Portfolio Candles 
# -------------------------------------------------------------------

def portfolio_candles_fig(candles: list, title="Portfolio Candles"):
    if not candles:
        fig = go.Figure()
        fig.update_layout(title=title, height=450,
                          paper_bgcolor="#111", plot_bgcolor="#111")
        return fig

    df = pd.DataFrame(candles)
    df["Date"] = pd.to_datetime(df["datetime"])

    bullish = df["close"].iloc[-1] >= df["open"].iloc[-1]
    bg_color = "rgba(0,255,140,0.06)" if bullish else "rgba(255,70,70,0.06)"

    vol_colors = [
        "rgba(0,255,140,0.5)" if df["close"].iloc[i] >= df["open"].iloc[i]
        else "rgba(255,70,70,0.5)"
        for i in range(len(df))
    ]

    fig = go.Figure()

    fig.add_trace(go.Candlestick(
        x=df["Date"],
        open=df["open"], high=df["high"],
        low=df["low"], close=df["close"],
        increasing_line_color="#00ff8c",
        decreasing_line_color="#ff4646",
        increasing_fillcolor="rgba(0,255,140,0.6)",
        decreasing_fillcolor="rgba(255,70,70,0.6)",
        name="Portfolio"
    ))

    fig.add_trace(go.Bar(
        x=df["Date"],
        y=df["volume"],
        marker_color=vol_colors,
        opacity=0.45,
        yaxis="y2",
        name="Volume"
    ))

    fig.update_layout(
        title=title,
        height=480,
        paper_bgcolor="#0b0b0b",
        plot_bgcolor=bg_color,
        font=dict(color="#ebebeb"),
        xaxis=dict(showgrid=False, rangeslider=dict(visible=False)),
        yaxis=dict(title="Value", gridcolor="rgba(255,255,255,0.07)"),
        yaxis2=dict(overlaying="y", side="right", showgrid=False),
        margin=dict(l=50, r=50, t=50, b=40),
    )
    return fig


# -------------------------------------------------------------------
# LIVE TRADER VIEW
# -------------------------------------------------------------------

class Trader:
    def __init__(self, name, lastname, model_name):
        self.name = name
        self.lastname = lastname
        self.model_name = model_name
        self.account = Account.get(name)

    def reload(self):
        self.account = Account.get(self.name)

    def get_title(self):
        return f"<div style='text-align:center;font-size:32px;'>{self.name}<span style='color:#aaa;font-size:20px;'> ({self.model_name}) - {self.lastname}</span></div>"

    def get_portfolio_value_html(self):
        pv = self.account.calculate_portfolio_value() or 0.0
        pnl = self.account.calculate_profit_loss(pv) or 0.0
        color = "green" if pnl >= 0 else "red"
        arrow = "⬆" if pnl >= 0 else "⬇"

        return f"""
        <div style='text-align:center;background:{color};padding:6px;'>
            <span style='font-size:28px'>₹{pv:,.0f}</span>
            <span style='font-size:20px'> {arrow} ₹{pnl:,.0f}</span>
        </div>
        """

    def get_logs(self, prev=None):
        rows = read_log(self.name, last_n=15)
        html = ""
        for dt, t, msg in rows:
            col = mapper.get(t, Color.WHITE).value
            html += f"<span style='color:{col}'>{dt} [{t}] {msg}</span><br/>"
        html = f"<div style='height:200px;overflow-y:auto;'>{html}</div>"
        return html if html != prev else gr.update()

    def get_portfolio_fig(self):
        return portfolio_candles_fig(self.account.get_portfolio_candles(),
                                     f"{self.name} Portfolio Candles")

    def get_holdings_df(self):
        h = self.account.get_holdings()
        return pd.DataFrame([{"Symbol": s, "Quantity": q} for s, q in h.items()]) if h else pd.DataFrame(columns=["Symbol", "Quantity"])

    def get_transactions_df(self):
        tx = self.account.transactions
        return pd.DataFrame([t.model_dump() for t in tx]) if tx else pd.DataFrame(columns=["timestamp", "symbol", "quantity", "price", "rationale"])


class TraderView:
    def __init__(self, trader):
        self.t = trader

    def make_ui(self):
        with gr.Column():
            gr.HTML(self.t.get_title())
            pv = gr.HTML(self.t.get_portfolio_value_html)
            chart = gr.Plot(self.t.get_portfolio_fig)
            logs = gr.HTML(self.t.get_logs)
            holdings = gr.Dataframe(self.t.get_holdings_df, label="Holdings")
            tx = gr.Dataframe(self.t.get_transactions_df, label="Recent Transactions")

        def refresh():
            self.t.reload()
            return (
                self.t.get_portfolio_value_html(),
                self.t.get_portfolio_fig(),
                self.t.get_holdings_df(),
                self.t.get_transactions_df(),
            )

        refresh_timer = gr.Timer(120)
        refresh_timer.tick(refresh, [], [pv, chart, holdings, tx], queue=False)

        log_timer = gr.Timer(2)
        log_timer.tick(lambda prev: self.t.get_logs(prev), [logs], [logs], queue=False)


# -------------------------------------------------------------------
# RECORDED SESSIONS
# -------------------------------------------------------------------

def create_ui():
    traders = [Trader(n, ln, mn) for n, ln, mn in zip(names, lastnames, short_model_names)]
    views = [TraderView(t) for t in traders]

    with gr.Blocks(title="AI Traders", css=css, js=js) as ui:

        # LIVE SESSION
        with gr.Tab("LIVE SESSION"):
            with gr.Row():
                for v in views:
                    v.make_ui()

        # RECORDED SESSION
        with gr.Tab("RECORDED SESSIONS"):
            gr.Markdown("### Recorded Sessions — Stock & Portfolio Candles (TradingView Style)")

            with gr.Row():
                with gr.Column(scale=3):
                    trader_sel = gr.Dropdown(names, label="Trader", value=names[0])
                    start = gr.Textbox(label="Start Date (YYYY-MM-DD)")
                    end = gr.Textbox(label="End Date (YYYY-MM-DD)")
                    slider = gr.Slider(0, 100, label="Playback %", value=100)

                    stock_box = gr.Textbox(label="Stock Symbol", value="")
                    period_dd = gr.Dropdown(["5d", "1mo", "3mo", "6mo", "1y"],
                                            value="1mo", label="Period")
                    interval_dd = gr.Dropdown(["1d", "1h", "30m", "15m"],
                                              value="1d", label="Interval")

                    btn = gr.Button("Load Charts")

                with gr.Column(scale=7):
                    stock_fig = gr.Plot()
                    port_fig = gr.Plot()
                    logs_box = gr.Textbox(lines=12, label="Logs")
                    hold_box = gr.Dataframe(label="Holdings")
                    tx_box = gr.Dataframe(label="Transactions")

            def load_recording(trader, s, e, pct, stock, period, interval):
                df = load_portfolio_history(trader)
                if s:
                    df = df[df["datetime"] >= pd.to_datetime(s)]
                if e:
                    df = df[df["datetime"] <= pd.to_datetime(e)]

                if not df.empty:
                    idx = max(1, int((pct/100) * len(df)))
                    df = df.iloc[:idx]

                # Stock Figure
                sf = go.Figure()
                if stock.strip():
                    ohlcv = fetch_stock_ohlcv(stock.strip(), period, interval)
                    sf = stock_candlestick_fig(ohlcv, f"{stock} OHLCV")

                # Portfolio Figure
                acc = Account.get(trader)
                pf = portfolio_candles_fig(acc.get_portfolio_candles(),
                                           f"{trader} Portfolio Candles")

                logs = load_full_logs(trader)
                holds = pd.DataFrame([acc.holdings]) if acc.holdings else pd.DataFrame(columns=["Symbol","Quantity"])
                tx = load_transactions(trader)

                return sf, pf, logs, holds, tx

            btn.click(
                load_recording,
                [trader_sel, start, end, slider, stock_box, period_dd, interval_dd],
                [stock_fig, port_fig, logs_box, hold_box, tx_box]
            )

    return ui


if __name__ == "__main__":
    ui = create_ui()
    ui.launch(inbrowser=True)
