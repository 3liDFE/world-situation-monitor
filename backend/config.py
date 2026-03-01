"""
Configuration module for World Situation Monitor backend.
Loads environment variables and defines application settings.
"""

import os
from dotenv import load_dotenv

load_dotenv()


class Settings:
    """Application settings loaded from environment variables."""

    # Server
    HOST: str = os.getenv("HOST", "0.0.0.0")
    PORT: int = int(os.getenv("PORT", "8000"))

    # API Keys (optional)
    NEWSDATA_API_KEY: str = os.getenv("NEWSDATA_API_KEY", "")
    ANTHROPIC_API_KEY: str = os.getenv("ANTHROPIC_API_KEY", "")

    # GDELT API
    GDELT_DOC_API: str = "https://api.gdeltproject.org/api/v2/doc/doc"
    GDELT_GEO_API: str = "https://api.gdeltproject.org/api/v2/geo/geo"

    # OpenSky Network API
    OPENSKY_API: str = "https://opensky-network.org/api/states/all"

    # USGS Earthquake API
    USGS_EARTHQUAKE_API: str = (
        "https://earthquake.usgs.gov/earthquakes/feed/v1.0/summary/2.5_day.geojson"
    )

    # Open-Meteo API
    OPEN_METEO_API: str = "https://api.open-meteo.com/v1/forecast"

    # NewsData API
    NEWSDATA_API: str = "https://newsdata.io/api/1/news"

    # Middle East bounding box
    ME_LAT_MIN: float = 12.0
    ME_LAT_MAX: float = 42.0
    ME_LON_MIN: float = 25.0
    ME_LON_MAX: float = 65.0

    # Cache TTL (seconds)
    CACHE_TTL_CONFLICTS: int = 60
    CACHE_TTL_AIRCRAFT: int = 10
    CACHE_TTL_EARTHQUAKES: int = 300
    CACHE_TTL_WEATHER: int = 600
    CACHE_TTL_NEWS: int = 120
    CACHE_TTL_MISSILES: int = 60
    CACHE_TTL_AI_INSIGHTS: int = 300

    # Scheduler intervals (seconds)
    SCHEDULER_CONFLICTS: int = 60
    SCHEDULER_AIRCRAFT: int = 5
    SCHEDULER_EARTHQUAKES: int = 300
    SCHEDULER_WEATHER: int = 600
    SCHEDULER_NEWS: int = 120
    SCHEDULER_AI_INSIGHTS: int = 300

    # Major Middle East cities for weather tracking
    TRACKED_CITIES: dict[str, tuple[float, float]] = {
        "Tehran": (35.6892, 51.3890),
        "Baghdad": (33.3152, 44.3661),
        "Damascus": (33.5138, 36.2765),
        "Riyadh": (24.7136, 46.6753),
        "Tel Aviv": (32.0853, 34.7818),
        "Cairo": (30.0444, 31.2357),
        "Ankara": (39.9334, 32.8597),
        "Kabul": (34.5553, 69.2075),
        "Beirut": (33.8938, 35.5018),
        "Sanaa": (15.3694, 44.1910),
        "Abu Dhabi": (24.4539, 54.3773),
        "Doha": (25.2854, 51.5310),
        "Kuwait City": (29.3759, 47.9774),
        "Amman": (31.9454, 35.9284),
        "Muscat": (23.5880, 58.3829),
    }

    # HTTP client settings
    HTTP_TIMEOUT: float = 15.0
    HTTP_MAX_RETRIES: int = 2


settings = Settings()
