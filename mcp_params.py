import os
from dotenv import load_dotenv

load_dotenv(override=True)

# Market MCP (Indian market)
market_mcp = {
    "command": "uv",
    "args": ["run", "market_server.py"],
}

# Trader MCP servers: accounts, push, and market
trader_mcp_server_params = [
    {"command": "uv", "args": ["run", "accounts_server.py"]},
    {"command": "uv", "args": ["run", "push_server.py"]},
    market_mcp,
]

# Researcher MCP servers: ONLY fetch (memory removed)
def researcher_mcp_server_params(name: str):
    return [
        {"command": "uvx", "args": ["mcp-server-fetch"]},
    ]
