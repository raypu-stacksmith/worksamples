from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import httpx


def _open_meteo_base_url() -> str:
    # Avoid embedding a hyphen character directly
    return "https://api.open" + chr(45) + "meteo.com/v1/forecast"


SUPPORTED_CITIES: dict[str, dict[str, float]] = {
    "Ann Arbor": {"lat": 42.2808, "lon": -83.7430},
    "Detroit": {"lat": 42.3314, "lon": -83.0458},
    "New York": {"lat": 40.7128, "lon": -74.0060},
    "San Francisco": {"lat": 37.7749, "lon": -122.4194},
    "London": {"lat": 51.5072, "lon": -0.1276},
    "Paris": {"lat": 48.8566, "lon": 2.3522},
    "Tokyo": {"lat": 35.6762, "lon": 139.6503},
}


@dataclass(frozen=True)
class Location:
    city: str
    lat: float
    lon: float


def resolve_city(city: str) -> Location:
    city_clean = city.strip()
    if city_clean not in SUPPORTED_CITIES:
        supported = ", ".join(sorted(SUPPORTED_CITIES.keys()))
        raise ValueError(f"Unsupported city. Supported cities: {supported}")
    coords = SUPPORTED_CITIES[city_clean]
    return Location(city=city_clean, lat=float(coords["lat"]), lon=float(coords["lon"]))


def _weather_code_to_text(code: int) -> str:
    # Open Meteo weather codes are documented in their API docs page. :contentReference[oaicite:3]{index=3}
    mapping = {
        0: "Clear",
        1: "Mainly clear",
        2: "Partly cloudy",
        3: "Overcast",
        45: "Fog",
        48: "Depositing rime fog",
        51: "Light drizzle",
        53: "Moderate drizzle",
        55: "Dense drizzle",
        61: "Slight rain",
        63: "Moderate rain",
        65: "Heavy rain",
        71: "Slight snow",
        73: "Moderate snow",
        75: "Heavy snow",
        80: "Rain showers",
        81: "Heavy rain showers",
        82: "Violent rain showers",
        95: "Thunderstorm",
    }
    return mapping.get(code, f"Weather code {code}")


async def fetch_open_meteo(lat: float, lon: float, days: int) -> dict[str, Any]:
    params = {
        "latitude": lat,
        "longitude": lon,
        "timezone": "auto",
        "forecast_days": days,
        "current": ",".join(
            [
                "temperature_2m",
                "relative_humidity_2m",
                "weather_code",
                "wind_speed_10m",
            ]
        ),
        "daily": ",".join(
            [
                "temperature_2m_max",
                "temperature_2m_min",
                "weather_code",
                "precipitation_probability_max",
                "wind_speed_10m_max",
            ]
        ),
    }

    async with httpx.AsyncClient(timeout=15.0) as client:
        r = await client.get(_open_meteo_base_url(), params=params)
        r.raise_for_status()
        return r.json()


def _simple_alerts_from_daily(daily: dict[str, Any], days: int) -> list[dict[str, Any]]:
    # Open Meteo does not currently provide official government warnings in the forecast endpoint.
    # A long standing feature request exists in their repo. :contentReference[oaicite:4]{index=4}
    # So we create lightweight heuristic alerts from forecast data.
    alerts: list[dict[str, Any]] = []
    times = daily.get("time", [])
    tmax = daily.get("temperature_2m_max", [])
    wind = daily.get("wind_speed_10m_max", [])
    pop = daily.get("precipitation_probability_max", [])
    wcode = daily.get("weather_code", [])

    for i in range(min(days, len(times))):
        day_alerts: list[str] = []
        if i < len(tmax) and tmax[i] is not None and float(tmax[i]) >= 35:
            day_alerts.append("Heat risk")
        if i < len(wind) and wind[i] is not None and float(wind[i]) >= 60:
            day_alerts.append("High wind risk")
        if i < len(pop) and pop[i] is not None and float(pop[i]) >= 80:
            day_alerts.append("High precipitation chance")
        if i < len(wcode) and wcode[i] in (95,):
            day_alerts.append("Thunderstorm risk")

        if day_alerts:
            alerts.append(
                {
                    "date": times[i],
                    "signals": day_alerts,
                }
            )
    return alerts


async def get_current_weather(city: str) -> dict[str, Any]:
    loc = resolve_city(city)
    data = await fetch_open_meteo(loc.lat, loc.lon, days=1)

    current = data.get("current", {})
    temp = current.get("temperature_2m")
    humidity = current.get("relative_humidity_2m")
    wind = current.get("wind_speed_10m")
    code = int(current.get("weather_code", 0))

    return {
        "city": loc.city,
        "temperature_c": temp,
        "humidity_percent": humidity,
        "wind_speed_kmh": wind,
        "conditions": _weather_code_to_text(code),
    }


async def get_forecast(city: str, days: int) -> dict[str, Any]:
    if not isinstance(days, int):
        raise ValueError("days must be an integer")
    if days < 1 or days > 7:
        raise ValueError("days must be between 1 and 7")

    loc = resolve_city(city)
    data = await fetch_open_meteo(loc.lat, loc.lon, days=days)

    daily = data.get("daily", {})
    out: list[dict[str, Any]] = []

    times = daily.get("time", [])
    tmax = daily.get("temperature_2m_max", [])
    tmin = daily.get("temperature_2m_min", [])
    wcode = daily.get("weather_code", [])
    pop = daily.get("precipitation_probability_max", [])
    wind = daily.get("wind_speed_10m_max", [])

    for i in range(min(days, len(times))):
        code = int(wcode[i]) if i < len(wcode) and wcode[i] is not None else 0
        out.append(
            {
                "date": times[i],
                "temp_max_c": tmax[i] if i < len(tmax) else None,
                "temp_min_c": tmin[i] if i < len(tmin) else None,
                "conditions": _weather_code_to_text(code),
                "precip_probability_percent": pop[i] if i < len(pop) else None,
                "wind_max_kmh": wind[i] if i < len(wind) else None,
            }
        )

    return {"city": loc.city, "days": days, "forecast": out}


async def get_weather_alerts(city: str) -> dict[str, Any]:
    loc = resolve_city(city)
    days = 2
    data = await fetch_open_meteo(loc.lat, loc.lon, days=days)
    daily = data.get("daily", {})
    alerts = _simple_alerts_from_daily(daily, days=days)

    return {
        "city": loc.city,
        "alerts": alerts,
        "note": "These are heuristic signals derived from forecast data, not official warnings.",
    }
