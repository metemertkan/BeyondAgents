"""FX4Free local edition as an MCP stdio server: the same code behind an MCP tool."""
import sys

from mcp.server import MCPServer

sys.path.insert(0, sys.argv[1])   # where fx_local.py was written
import fx_local  # noqa: E402

server = MCPServer("FX4Free local")


@server.tool(description="Convert currencies (FX4Free local).")
def convert(amount: float, from_currency: str, to_currency: str) -> dict:
    return {"converted": fx_local.convert(amount, from_currency, to_currency), "probe": fx_local.look_around()}


if __name__ == "__main__":
    server.run("stdio")
