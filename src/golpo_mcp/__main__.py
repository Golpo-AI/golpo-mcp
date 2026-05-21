"""Entry point: `python -m golpo_mcp` or `golpo-mcp` (console script)."""

from .server import mcp


def main() -> None:
    """Run the Golpo MCP server over stdio."""
    mcp.run()


if __name__ == "__main__":
    main()
