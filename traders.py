from contextlib import AsyncExitStack
from accounts_client import read_accounts_resource, read_strategy_resource
from tracers import make_trace_id
from agents import Agent, Tool, Runner, OpenAIChatCompletionsModel, trace
from openai import AsyncOpenAI
from dotenv import load_dotenv
import os
import json
from agents.mcp import MCPServerStdio
from templates import (
    researcher_instructions,
    trader_instructions,
    trade_message,
    rebalance_message,
    research_tool,
)
from mcp_params import trader_mcp_server_params, researcher_mcp_server_params
from datetime import datetime
from accounts import Account
from database import write_log
from market import normalize_symbol, is_market_open

load_dotenv(override=True)

openai_api_key = os.getenv("OPENAI_API_KEY")
google_api_key = os.getenv("GOOGLE_API_KEY")

openai_client = AsyncOpenAI(api_key=openai_api_key)
gemini_client = AsyncOpenAI(
    base_url="https://generativelanguage.googleapis.com/v1beta/openai/",
    api_key=google_api_key
)

MAX_TURNS = 30


def get_model(model_name: str):
    if "gemini" in model_name.lower():
        return OpenAIChatCompletionsModel(model=model_name, openai_client=gemini_client)
    return OpenAIChatCompletionsModel(model=model_name, openai_client=openai_client)


async def get_researcher(mcp_servers, model_name) -> Agent:
    researcher = Agent(
        name="Researcher",
        instructions=researcher_instructions(),
        model=get_model(model_name),
        mcp_servers=mcp_servers,
    )
    return researcher


async def get_researcher_tool(mcp_servers, model_name) -> Tool:
    researcher = await get_researcher(mcp_servers, model_name)
    return researcher.as_tool(tool_name="Researcher", tool_description=research_tool())


class Trader:
    def __init__(self, name: str, lastname="Trader", model_name="gpt-4o-mini"):
        self.name = name
        self.lastname = lastname
        self.agent = None
        self.model_name = model_name
        self.do_trade = True


    async def create_agent(self, trader_mcp_servers, researcher_mcp_servers) -> Agent:
        tool = await get_researcher_tool(researcher_mcp_servers, self.model_name)
        self.agent = Agent(
            name=self.name,
            instructions=trader_instructions(self.name),
            model=get_model(self.model_name),
            tools=[tool],
            mcp_servers=trader_mcp_servers,
        )
        return self.agent


    async def get_account_report(self) -> str:
        account = await read_accounts_resource(self.name)
        account_json = json.loads(account)
        account_json.pop("portfolio_value_time_series", None)
        return json.dumps(account_json)


    async def run_agent(self, trader_mcp_servers, researcher_mcp_servers, market_open: bool):
        self.agent = await self.create_agent(trader_mcp_servers, researcher_mcp_servers)
        account = await self.get_account_report()
        strategy = await read_strategy_resource(self.name)

        # CLOSED MARKET = ANALYSIS MODE
        if not market_open:
            message = f"""
The Indian stock market (NSE/BSE) is CLOSED.
DO NOT use buy/sell tools.

Perform:
- Research
- Macro analysis
- Portfolio review
- Identify stocks for the next open

Remember:
ONLY valid NSE symbols ending with .NS
Do NOT invent symbols.

Account:
{account}

Strategy:
{strategy}
"""

            try:
                await Runner.run(self.agent, message, max_turns=MAX_TURNS)
            except Exception as e:
                write_log(self.name, "research", f"Research error: {e}")

            # Snapshot so the UI graph updates
            Account.get(self.name).record_research_snapshot("Analysis snapshot")
            return

        # MARKET OPEN — NORMAL TRADING
        msg = trade_message(self.name, strategy, account) if self.do_trade else rebalance_message(self.name, strategy, account)

        # Before trading, validate symbols in strategy text
        # (AI cannot invent tickers now due to templates, but safety check)
        def validate_symbols(msg: str) -> str:
            words = msg.replace(",", "").replace("\n", " ").split(" ")
            valid = []
            for w in words:
                sym = normalize_symbol(w)
                if sym:
                    valid.append(sym)
            return " ".join(valid)

        await Runner.run(self.agent, msg, max_turns=MAX_TURNS)

        # Alternate trade/rebalance next tick
        self.do_trade = not self.do_trade


    async def run_with_mcp_servers(self, market_open: bool):
        async with AsyncExitStack() as stack:
            trader_mcp_servers = [
                await stack.enter_async_context(
                    MCPServerStdio(params, client_session_timeout_seconds=120)
                )
                for params in trader_mcp_server_params
            ]
            researcher_mcp_servers = [
                await stack.enter_async_context(
                    MCPServerStdio(params, client_session_timeout_seconds=120)
                )
                for params in researcher_mcp_server_params(self.name)
            ]

            await self.run_agent(trader_mcp_servers, researcher_mcp_servers, market_open)


    async def run_with_trace(self, market_open: bool):
        trace_name = f"{self.name}-trading" if market_open else f"{self.name}-analysis"
        trace_id = make_trace_id(self.name.lower())

        with trace(trace_name, trace_id=trace_id):
            await self.run_with_mcp_servers(market_open)


    async def run(self, market_open: bool):
        try:
            await self.run_with_trace(market_open)
        except Exception as e:
            write_log(self.name, "agent", f"Trader error: {e}")
