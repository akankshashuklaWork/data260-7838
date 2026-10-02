"""Local MCP server exposing exactly three rental-domain tools."""

from __future__ import annotations

import logging
import os
import sys

from mcp.server.fastmcp import FastMCP

try:
    from .domain_tools import MemoryDomainStore, SqlAlchemyDomainStore, execute_tool
except ImportError:  # supports `mcp dev code/hw5_mcp/domain_server.py`
    from domain_tools import MemoryDomainStore, SqlAlchemyDomainStore, execute_tool

logging.basicConfig(stream=sys.stderr, level=logging.INFO, format="%(levelname)s %(message)s")
log = logging.getLogger(__name__)
mcp = FastMCP("s7838-rental-domain")
if os.getenv("DATABASE_URL"):
    from hw4_backend.database import SessionLocal
    store = SqlAlchemyDomainStore(SessionLocal)
else:
    store = MemoryDomainStore.demo()


@mcp.tool()
def search(query: str, limit: int = 10) -> str:
    """Search rental listings by code, title, location, or category."""
    log.info("domain search query=%r limit=%s", query, limit)
    return execute_tool("search", {"query": query, "limit": limit}, store)


@mcp.tool()
def detail(listing_id: int) -> str:
    """Return one rental listing and its owner details."""
    log.info("domain detail listing_id=%s", listing_id)
    return execute_tool("detail", {"listing_id": listing_id}, store)


@mcp.tool()
def aggregate(owner_id: int) -> str:
    """Summarize listing count and available units for one property owner."""
    log.info("domain aggregate owner_id=%s", owner_id)
    return execute_tool("aggregate", {"owner_id": owner_id}, store)


if __name__ == "__main__":
    mcp.run(transport="stdio")
