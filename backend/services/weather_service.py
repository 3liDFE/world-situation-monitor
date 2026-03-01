"""
Weather Service - Fetches current weather conditions and generates alerts
for major cities in the Middle East using Open-Meteo API.
"""

import hashlib
import logging
from datetime import datetime, timezone

import httpx
from cachetools import TTLCache

from config import settings
from models import WeatherAlert

logger = logging.getLogger(__name__)

_weather_cache: TTLCache = TTLCache(maxsize=1, ttl=settings.CACHE_TTL_WEATHER)

# WMO Weather Interpretation Codes (WW)
# https://open-meteo.com/en/docs
WMO_CODES: dict[int, tuple[str, str]] = {
    0: ("Clear sky", "info"),
    1: ("Mainly clear", "info"),
    2: ("Partly cloudy", "info"),
    3: ("Overcast", "info"),
    45: ("Fog", "moderate"),
    48: ("Depositing rime fog", "moderate"),
    51: ("Light drizzle", "info"),
    53: ("Moderate drizzle", "info"),
    55: ("Dense drizzle", "moderate"),
    56: ("Light freezing drizzle", "moderate"),
    57: ("Dense freezing drizzle", "moderate"),
    61: ("Slight rain", "info"),
    63: ("Moderate rain", "moderate"),
    65: ("Heavy rain", "severe"),
    66: ("Light freezing rain", "moderate"),
    67: ("Heavy freezing rain", "severe"),
    71: ("Slight snow fall", "moderate"),
    73: ("Moderate snow fall", "moderate"),
    75: ("Heavy snow fall", "severe"),
    77: ("Snow grains", "info"),
    80: ("Slight rain showers", "info"),
    81: ("Moderate rain showers", "moderate"),
    82: ("Violent rain showers", "severe"),
    85: ("Slight snow showers", "moderate"),
    86: ("Heavy snow showers", "severe"),
    95: ("Thunderstorm", "severe"),
    96: ("Thunderstorm with slight hail", "severe"),
    99: ("Thunderstorm with heavy hail", "extreme"),
}


def _generate_weather_id(city: str) -> str:
    """Generate a deterministic ID for weather data."""
    return hashlib.md5(f"weather-{city}".encode()).hexdigest()[:12]


def _assess_severity(weather_code: int, wind_speed: float, temperature: float) -> str:
    """
    Assess overall weather severity considering multiple factors.
    Extreme heat/cold and high winds increase severity.
    """
    base_severity = WMO_CODES.get(weather_code, ("Unknown", "info"))[1]

    severity_rank = {"info": 0, "moderate": 1, "severe": 2, "extreme": 3}
    rank = severity_rank.get(base_severity, 0)

    # Extreme heat (common in ME)
    if temperature >= 50:
        rank = max(rank, 3)  # extreme
    elif temperature >= 45:
        rank = max(rank, 2)  # severe
    elif temperature >= 42:
        rank = max(rank, 1)  # moderate

    # Extreme cold (rare but possible in highlands)
    if temperature <= -10:
        rank = max(rank, 2)
    elif temperature <= 0:
        rank = max(rank, 1)

    # High winds
    if wind_speed >= 100:
        rank = max(rank, 3)
    elif wind_speed >= 70:
        rank = max(rank, 2)
    elif wind_speed >= 50:
        rank = max(rank, 1)

    rank_to_severity = {0: "info", 1: "moderate", 2: "severe", 3: "extreme"}
    return rank_to_severity.get(rank, "info")


async def get_weather_data() -> list[WeatherAlert]:
    """
    Fetch current weather data for all tracked Middle East cities.
    Generates weather alerts for notable conditions.

    Returns:
        List of WeatherAlert models for each tracked city.
    """
    cache_key = "weather_all"
    if cache_key in _weather_cache:
        logger.debug("Returning cached weather data")
        return _weather_cache[cache_key]

    alerts: list[WeatherAlert] = []

    for city_name, (lat, lon) in settings.TRACKED_CITIES.items():
        weather = await _fetch_city_weather(city_name, lat, lon)
        if weather:
            alerts.append(weather)

    _weather_cache[cache_key] = alerts
    logger.info("Fetched weather data for %d cities", len(alerts))
    return alerts


async def _fetch_city_weather(
    city_name: str, lat: float, lon: float
) -> WeatherAlert | None:
    """Fetch current weather for a single city."""
    params = {
        "latitude": str(lat),
        "longitude": str(lon),
        "current": "temperature_2m,wind_speed_10m,weather_code,relative_humidity_2m,apparent_temperature,wind_direction_10m,wind_gusts_10m",
        "timezone": "auto",
    }

    try:
        async with httpx.AsyncClient(timeout=settings.HTTP_TIMEOUT) as client:
            response = await client.get(settings.OPEN_METEO_API, params=params)
            response.raise_for_status()
            data = response.json()

            current = data.get("current", {})
            if not current:
                return None

            temperature = current.get("temperature_2m", 0)
            wind_speed = current.get("wind_speed_10m", 0)
            weather_code = current.get("weather_code", 0)
            humidity = current.get("relative_humidity_2m", 0)
            apparent_temp = current.get("apparent_temperature", temperature)
            wind_direction = current.get("wind_direction_10m", 0)
            wind_gusts = current.get("wind_gusts_10m", 0)

            if temperature is None:
                temperature = 0
            if wind_speed is None:
                wind_speed = 0
            if weather_code is None:
                weather_code = 0

            wmo_desc, _ = WMO_CODES.get(weather_code, ("Unknown", "info"))
            severity = _assess_severity(weather_code, wind_speed, temperature)

            # Build description
            desc_parts = [
                f"{wmo_desc}",
                f"Temperature: {temperature}C (feels like {apparent_temp}C)",
                f"Humidity: {humidity}%",
                f"Wind: {wind_speed} km/h (gusts {wind_gusts} km/h) from {wind_direction} degrees",
            ]

            # Add warnings for extreme conditions
            if temperature >= 45:
                desc_parts.append("EXTREME HEAT WARNING")
            if wind_speed >= 60:
                desc_parts.append("HIGH WIND WARNING")
            if weather_code >= 95:
                desc_parts.append("THUNDERSTORM WARNING")
            if weather_code in (65, 67, 82):
                desc_parts.append("HEAVY PRECIPITATION WARNING")

            return WeatherAlert(
                id=f"wx-{_generate_weather_id(city_name)}",
                city=city_name,
                lat=lat,
                lon=lon,
                event=wmo_desc,
                severity=severity,
                description=" | ".join(desc_parts),
                temperature=temperature,
                wind_speed=wind_speed,
                weather_code=weather_code,
                start=datetime.now(timezone.utc),
                end=None,
            )

    except httpx.HTTPStatusError as e:
        logger.error("Open-Meteo HTTP error for %s: %s", city_name, e.response.status_code)
    except httpx.RequestError as e:
        logger.error("Open-Meteo request error for %s: %s", city_name, str(e))
    except Exception as e:
        logger.error("Open-Meteo unexpected error for %s: %s", city_name, str(e))

    return None
