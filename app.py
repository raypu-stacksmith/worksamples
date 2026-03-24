from __future__ import annotations

import json
import logging
import os
import sys
from typing import Any

from fastmcp import FastMCP
from starlette.responses import JSONResponse

from weather_service import (
    SUPPORTED_CITIES,
    get_current_weather,
    get_forecast,
    get_weather_alerts,
)


def setup_logging() -> None:
    transport = os.getenv("MCP_TRANSPORT", "stdio").strip().lower()

    logger = logging.getLogger()
    logger.setLevel(logging.INFO)

    handler: logging.Handler
    if transport == "http":
        handler = logging.StreamHandler(sys.stdout)
        formatter = logging.Formatter(
            fmt=json.dumps(
                {
                    "level": "%(levelname)s",
                    "message": "%(message)s",
                    "logger": "%(name)s",
                    "time": "%(asctime)s",
                }
            )
        )
        handler.setFormatter(formatter)
    else:
        handler = logging.StreamHandler(sys.stderr)
        formatter = logging.Formatter("%(levelname)s %(name)s %(message)s")
        handler.setFormatter(formatter)

    logger.handlers.clear()
    logger.addHandler(handler)


setup_logging()

mcp = FastMCP("Weather MCP")


@mcp.tool
async def get_current_weather_tool(city: str) -> dict[str, Any]:
    """Return current temperature, conditions, humidity, and wind for a supported city."""
    return await get_current_weather(city)


@mcp.tool
async def get_forecast_tool(city: str, days: int) -> dict[str, Any]:
    """Return a 1 to 7 day forecast for a supported city."""
    return await get_forecast(city, days)


@mcp.tool
async def get_weather_alerts_tool(city: str) -> dict[str, Any]:
    """Return active alerts and warnings for a supported city."""
    return await get_weather_alerts(city)


@mcp.resource("weather://cities/supported")
def supported_cities() -> dict[str, Any]:
    """List supported cities and their coordinates."""
    return {"cities": SUPPORTED_CITIES}


@mcp.custom_route("/health", methods=["GET"])
async def health_check(request):
    return JSONResponse({"status": "healthy", "service": "weather-mcp"})


if __name__ == "__main__":
    transport = os.getenv("MCP_TRANSPORT", "stdio").strip().lower()
    if transport == "http":
        host = os.getenv("HOST", "0.0.0.0")
        port = int(os.getenv("PORT", "8080"))
        mcp.run(transport="http", host=host, port=port)
    else:
        mcp.run()
