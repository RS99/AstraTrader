from pydantic import BaseModel
import json
from dotenv import load_dotenv
from datetime import datetime, timezone
from market import get_share_price
from database import write_account, read_account, write_log
import math
import pandas as pd

load_dotenv(override=True)

INITIAL_BALANCE = 10_000.0
SPREAD = 0.002


class Transaction(BaseModel):
    symbol: str
    quantity: int
    price: float
    timestamp: str
    rationale: str

    def total(self) -> float:
        return self.quantity * self.price
    
    def __repr__(self):
        return f"{abs(self.quantity)} shares of {self.symbol} at {self.price} each."


class Account(BaseModel):
    name: str
    balance: float
    strategy: str
    holdings: dict[str, int]
    transactions: list[Transaction]
    # portfolio_value_time_series stores tuples (iso_datetime_str, value)
    portfolio_value_time_series: list[tuple[str, float]]

    @classmethod
    def get(cls, name: str):
        fields = read_account(name.lower())
        if not fields:
            fields = {
                "name": name.lower(),
                "balance": INITIAL_BALANCE,
                "strategy": "",
                "holdings": {},
                "transactions": [],
                "portfolio_value_time_series": []
            }
            write_account(name, fields)
        return cls(**fields)
    
    
    def save(self):
        write_account(self.name.lower(), self.model_dump())

    def reset(self, strategy: str):
        self.balance = INITIAL_BALANCE
        self.strategy = strategy
        self.holdings = {}
        self.transactions = []
        self.portfolio_value_time_series = []
        self.save()

    def deposit(self, amount: float):
        """ Deposit funds into the account. """
        if amount <= 0:
            raise ValueError("Deposit amount must be positive.")
        self.balance += amount
        print(f"Deposited ${amount}. New balance: ${self.balance}")
        self.save()

    def withdraw(self, amount: float):
        """ Withdraw funds from the account, ensuring it doesn't go negative. """
        if amount > self.balance:
            raise ValueError("Insufficient funds for withdrawal.")
        self.balance -= amount
        print(f"Withdrew ${amount}. New balance: ${self.balance}")
        self.save()

    def buy_shares(self, symbol: str, quantity: int, rationale: str) -> str:
        """ Buy shares of a stock if sufficient funds are available. """
        price = get_share_price(symbol)
        buy_price = price * (1 + SPREAD)
        total_cost = buy_price * quantity
        
        if total_cost > self.balance:
            raise ValueError("Insufficient funds to buy shares.")
        elif price == 0:
            raise ValueError(f"Unrecognized symbol {symbol}")
        
        # Update holdings
        self.holdings[symbol] = self.holdings.get(symbol, 0) + quantity
        timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S%z")
        # Record transaction
        transaction = Transaction(symbol=symbol, quantity=quantity, price=buy_price, timestamp=timestamp, rationale=rationale)
        self.transactions.append(transaction)
        
        # Update balance
        self.balance -= total_cost
        self.save()
        write_log(self.name, "account", f"Bought {quantity} of {symbol}")
        return "Completed. Latest details:\n" + self.report()

    def sell_shares(self, symbol: str, quantity: int, rationale: str) -> str:
        """ Sell shares of a stock if the user has enough shares. """
        if self.holdings.get(symbol, 0) < quantity:
            raise ValueError(f"Cannot sell {quantity} shares of {symbol}. Not enough shares held.")
        
        price = get_share_price(symbol)
        sell_price = price * (1 - SPREAD)
        total_proceeds = sell_price * quantity
        
        # Update holdings
        self.holdings[symbol] -= quantity
        
        # If shares are completely sold, remove from holdings
        if self.holdings[symbol] == 0:
            del self.holdings[symbol]
        timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S%z")
        # Record transaction
        transaction = Transaction(symbol=symbol, quantity=-quantity, price=sell_price, timestamp=timestamp, rationale=rationale)  # negative quantity for sell
        self.transactions.append(transaction)

        # Update balance
        self.balance += total_proceeds
        self.save()
        write_log(self.name, "account", f"Sold {quantity} of {symbol}")
        return "Completed. Latest details:\n" + self.report()

    def calculate_portfolio_value(self):
        """ Calculate the total value of the user's portfolio. """
        total_value = self.balance
        for symbol, quantity in self.holdings.items():
            total_value += get_share_price(symbol) * quantity
        return total_value

    def calculate_profit_loss(self, portfolio_value: float = None):
        """ Calculate profit or loss relative to initial balance. """
        if portfolio_value is None:
            portfolio_value = self.calculate_portfolio_value()
        pnl = portfolio_value - INITIAL_BALANCE
        return pnl

    def get_holdings(self):
        """ Report the current holdings of the user. """
        return self.holdings

    def get_profit_loss(self):
        """ Report the user's profit or loss at any point in time. """
        return self.calculate_profit_loss()

    def list_transactions(self):
        """ List all transactions made by the user. """
        return [transaction.model_dump() for transaction in self.transactions]
    
    def report(self) -> str:
        """ Return a json string representing the account.  """
        portfolio_value = self.calculate_portfolio_value()
        # append snapshot to time series when reporting manually
        ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S%z")
        self.portfolio_value_time_series.append((ts, portfolio_value))
        self.save()
        pnl = self.calculate_profit_loss(portfolio_value)
        data = self.model_dump()
        data["total_portfolio_value"] = portfolio_value
        data["total_profit_loss"] = pnl
        write_log(self.name, "account", f"Retrieved account details")
        return json.dumps(data)
    
    def get_strategy(self) -> str:
        """ Return the strategy of the account """
        write_log(self.name, "account", f"Retrieved strategy")
        return self.strategy
    
    def change_strategy(self, strategy: str) -> str:
        """ At your discretion, if you choose to, call this to change your investment strategy for the future """
        self.strategy = strategy
        self.save()
        write_log(self.name, "account", f"Changed strategy")
        return "Changed strategy"

    # -------------------------------
    # Snapshot API 
    # -------------------------------
    def record_snapshot(self, when: datetime | None = None):
        """
        Record a portfolio snapshot into portfolio_value_time_series.
        Use UTC ISO timestamp. This should be called periodically (e.g., after a run or every minute).
        """
        now = when or datetime.now(timezone.utc)
        ts = now.strftime("%Y-%m-%d %H:%M:%S%z")
        value = self.calculate_portfolio_value()
        # Append only if last value differs (avoid duplicates)
        if not self.portfolio_value_time_series or float(self.portfolio_value_time_series[-1][1]) != float(value):
            self.portfolio_value_time_series.append((ts, float(value)))
            self.save()
            write_log(self.name, "account", f"Snapshot recorded: {value:.2f}")
        return (ts, value)

    def get_portfolio_candles(self, resolution: str = "1min", start: str | None = None, end: str | None = None) -> list:
        """
        Build OHLCV candles aggregated at `resolution`.
        resolution: pandas resample string like '1min','5min','15min','1H','4H','1D'
        start, end: optional ISO date strings to filter the time series before aggregation.
        Returns list of dicts: { "datetime": iso, "open":..., "high":..., "low":..., "close":..., "volume": int }
        Volume is computed as sum of absolute trade quantities in the same interval.
        """
        # Build DataFrame from snapshots
        rows = self.portfolio_value_time_series
        if not rows:
            return []

        df = pd.DataFrame(rows, columns=["datetime", "value"])
        # parse datetimes
        df["datetime"] = pd.to_datetime(df["datetime"], utc=True, errors="coerce")
        df = df.dropna(subset=["datetime"])
        df = df.set_index("datetime").sort_index()

        # apply start/end filter
        if start:
            df = df[df.index >= pd.to_datetime(start, utc=True)]
        if end:
            df = df[df.index <= pd.to_datetime(end, utc=True)]

        if df.empty:
            return []

        # Resample OHLC
        try:
            agg = df["value"].resample(resolution).agg(["first", "max", "min", "last"])
        except Exception:
            # fallback to 1min if invalid resolution
            agg = df["value"].resample("1min").agg(["first", "max", "min", "last"])

        agg = agg.dropna(subset=["first"])  # drop empty bins
        agg.columns = ["open", "high", "low", "close"]

        # Build volume series: aggregate absolute transaction quantities into same bins
        txs = self.list_transactions()
        if txs:
            tx_df = pd.DataFrame(txs)
            # ensure timestamp parsed and absolute quantities
            tx_df["timestamp"] = pd.to_datetime(tx_df["timestamp"], utc=True, errors="coerce")
            tx_df["abs_qty"] = tx_df["quantity"].abs()
            tx_df = tx_df.dropna(subset=["timestamp"]).set_index("timestamp").sort_index()
            try:
                vol = tx_df["abs_qty"].resample(resolution).sum().reindex(agg.index, fill_value=0)
            except Exception:
                vol = pd.Series(0, index=agg.index)
        else:
            vol = pd.Series(0, index=agg.index)

        # Prepare output list
        out = []
        for idx, row in agg.iterrows():
            dt_iso = idx.isoformat()
            o = float(row["open"])
            h = float(row["high"])
            l = float(row["low"])
            c = float(row["close"])
            v = int(vol.get(idx, 0) or 0)
            out.append({"datetime": dt_iso, "open": o, "high": h, "low": l, "close": c, "volume": v})
        return out
