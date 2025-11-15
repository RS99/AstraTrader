from mcp.server.fastmcp import FastMCP
from market import get_share_price

mcp = FastMCP("market_server")

@mcp.tool()
async def lookup_share_price(symbol: str) -> float:
    """This tool provides the current price of the given stock symbol.

    Args:
        symbol: the symbol of the stock
    """
    price = get_share_price(symbol)
    if price == 0.0:
        # Provide a clearer error to callers so they can handle invalid/unavailable tickers.
        raise ValueError(f"Symbol {symbol} not found or unsupported (price returned 0.0).")
    return price

if __name__ == "__main__":
    mcp.run(transport='stdio')
