"""
World Situation Monitor - Main FastAPI Application

A geopolitical intelligence dashboard backend that aggregates data from
multiple OSINT sources including GDELT, OpenSky Network, USGS, and Open-Meteo
to provide real-time situational awareness for the Middle East region.
"""

import asyncio
import json
import logging
import time
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import Optional

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from fastapi import FastAPI, Query, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

from config import settings
from models import (
    Aircraft,
    GeoEvent,
    LiveFeed,
    MilitaryBase,
    MissileEvent,
    NewsItem,
    NuclearSite,
    OsintPost,
    SystemStatus,
    Vessel,
    Waterway,
    WeatherAlert,
    AIInsight,
)
from services import gdelt_service, opensky_service, usgs_service, weather_service
from services import military_data, news_service, ai_service, ais_service
from services import database, osint_service, aircraft_db

# ============================================================================
# Logging configuration
# ============================================================================

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("wsm")

# ============================================================================
# In-memory data store
# ============================================================================

_data_store: dict[str, object] = {
    "conflicts": [],
    "aircraft": [],
    "military_aircraft": [],
    "missiles": [],
    "earthquakes": [],
    "weather": [],
    "news": [],
    "military_bases": [],
    "nuclear_sites": [],
    "waterways": [],
    "vessels": [],
    "military_vessels": [],
    "ai_insights": [],
    "x_intelligence": [],
    "telegram_intelligence": [],
    "osint_other": [],
    "last_update": {},
    "errors": [],
}

_start_time: float = time.time()

# ============================================================================
# WebSocket connection manager
# ============================================================================


class ConnectionManager:
    """Manages WebSocket connections and layer subscriptions."""

    def __init__(self):
        self.active_connections: list[WebSocket] = []
        self.subscriptions: dict[WebSocket, set[str]] = {}

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)
        self.subscriptions[websocket] = set()
        logger.info(
            "WebSocket connected. Active connections: %d",
            len(self.active_connections)
        )

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
        self.subscriptions.pop(websocket, None)
        logger.info(
            "WebSocket disconnected. Active connections: %d",
            len(self.active_connections)
        )

    def subscribe(self, websocket: WebSocket, layers: list[str]):
        if websocket in self.subscriptions:
            self.subscriptions[websocket].update(layers)
            logger.info("WebSocket subscribed to: %s", layers)

    def unsubscribe(self, websocket: WebSocket, layers: list[str]):
        if websocket in self.subscriptions:
            self.subscriptions[websocket].difference_update(layers)

    async def broadcast(self, layer: str, data: object):
        """Broadcast data to all clients subscribed to a layer."""
        disconnected: list[WebSocket] = []
        for ws in self.active_connections:
            # Send to all connections or those subscribed to this layer
            subs = self.subscriptions.get(ws, set())
            if not subs or layer in subs or "all" in subs:
                try:
                    message = {
                        "type": layer,
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                        "data": _serialize(data),
                    }
                    await ws.send_json(message)
                except Exception:
                    disconnected.append(ws)

        for ws in disconnected:
            self.disconnect(ws)


manager = ConnectionManager()


def _serialize(obj: object) -> object:
    """Serialize Pydantic models and other objects for JSON transmission."""
    if isinstance(obj, list):
        return [_serialize(item) for item in obj]
    if hasattr(obj, "model_dump"):
        d = obj.model_dump()
        # Convert datetime objects to ISO strings
        for key, value in d.items():
            if isinstance(value, datetime):
                d[key] = value.isoformat()
        return d
    if isinstance(obj, datetime):
        return obj.isoformat()
    return obj


# ============================================================================
# Background data refresh tasks
# ============================================================================


async def refresh_conflicts():
    """Refresh conflict events from live news + GDELT."""
    try:
        conflicts = await gdelt_service.get_conflicts()
        _data_store["conflicts"] = conflicts
        _data_store["last_update"]["conflicts"] = datetime.now(timezone.utc)
        await manager.broadcast("conflicts", conflicts)
        await _generate_alerts_from_data()
        logger.info("Refreshed conflicts: %d events", len(conflicts))
    except Exception as e:
        error_msg = f"Failed to refresh conflicts: {e}"
        logger.error(error_msg)
        _record_error(error_msg)


async def refresh_missiles():
    """Refresh missile events from live news + GDELT."""
    try:
        missiles = await gdelt_service.get_missile_events()
        _data_store["missiles"] = missiles
        _data_store["last_update"]["missiles"] = datetime.now(timezone.utc)
        await manager.broadcast("missiles", missiles)
        await _generate_alerts_from_data()
        logger.info("Refreshed missiles: %d events", len(missiles))
    except Exception as e:
        error_msg = f"Failed to refresh missiles: {e}"
        logger.error(error_msg)
        _record_error(error_msg)


async def refresh_aircraft():
    """Refresh aircraft positions from OpenSky with type identification."""
    try:
        aircraft = await opensky_service.get_aircraft()
        mil_aircraft = await opensky_service.get_military_aircraft()
        # Enrich with aircraft type identification
        try:
            aircraft_dicts = [_serialize(a) for a in aircraft]
            enriched = await aircraft_db.enrich_aircraft_list(aircraft_dicts)
            # Update aircraft objects with type info
            for ac, enriched_data in zip(aircraft, enriched):
                ac.aircraft_type = enriched_data.get("aircraft_type", "")
                ac.operator = enriched_data.get("operator", "")
                ac.is_military = enriched_data.get("is_military", False)
                ac.type_confidence = enriched_data.get("type_confidence", "")
        except Exception as e:
            logger.warning("Aircraft type enrichment failed: %s", e)
        _data_store["aircraft"] = aircraft
        _data_store["military_aircraft"] = mil_aircraft
        _data_store["last_update"]["aircraft"] = datetime.now(timezone.utc)
        await manager.broadcast("aircraft", aircraft)
        # Persist position history for trails
        try:
            await database.store_aircraft_positions(
                [_serialize(a) for a in aircraft if a.lat is not None]
            )
        except Exception:
            pass
        logger.info(
            "Refreshed aircraft: %d total, %d military",
            len(aircraft), len(mil_aircraft)
        )
    except Exception as e:
        error_msg = f"Failed to refresh aircraft: {e}"
        logger.error(error_msg)
        _record_error(error_msg)


async def refresh_earthquakes():
    """Refresh earthquake data from USGS."""
    try:
        earthquakes = await usgs_service.get_earthquakes()
        _data_store["earthquakes"] = earthquakes
        _data_store["last_update"]["earthquakes"] = datetime.now(timezone.utc)
        if earthquakes:
            await manager.broadcast("earthquakes", earthquakes)
        logger.info("Refreshed earthquakes: %d events", len(earthquakes))
    except Exception as e:
        error_msg = f"Failed to refresh earthquakes: {e}"
        logger.error(error_msg)
        _record_error(error_msg)


async def refresh_weather():
    """Refresh weather data from Open-Meteo."""
    try:
        weather = await weather_service.get_weather_data()
        _data_store["weather"] = weather
        _data_store["last_update"]["weather"] = datetime.now(timezone.utc)
        await manager.broadcast("weather", weather)
        logger.info("Refreshed weather: %d cities", len(weather))
    except Exception as e:
        error_msg = f"Failed to refresh weather: {e}"
        logger.error(error_msg)
        _record_error(error_msg)


async def refresh_news():
    """Refresh news from GDELT."""
    try:
        news = await news_service.get_news()
        _data_store["news"] = news
        _data_store["last_update"]["news"] = datetime.now(timezone.utc)
        await manager.broadcast("news", news)
        logger.info("Refreshed news: %d items", len(news))
    except Exception as e:
        error_msg = f"Failed to refresh news: {e}"
        logger.error(error_msg)
        _record_error(error_msg)


async def refresh_ai_insights():
    """Refresh AI-generated insights."""
    try:
        insights = await ai_service.generate_insights(
            conflicts=_data_store.get("conflicts", []),
            missiles=_data_store.get("missiles", []),
            aircraft=_data_store.get("military_aircraft", []),
        )
        _data_store["ai_insights"] = insights
        _data_store["last_update"]["ai_insights"] = datetime.now(timezone.utc)
        await manager.broadcast("ai_insights", insights)
        logger.info("Refreshed AI insights: %d insights", len(insights))
    except Exception as e:
        error_msg = f"Failed to refresh AI insights: {e}"
        logger.error(error_msg)
        _record_error(error_msg)


async def refresh_vessels():
    """Refresh vessel positions from AIS data."""
    try:
        vessels = await ais_service.get_vessels()
        _data_store["vessels"] = vessels
        _data_store["last_update"]["vessels"] = datetime.now(timezone.utc)
        await manager.broadcast("vessels", vessels)
        # Persist to database
        try:
            await database.store_vessel_positions(
                [_serialize(v) for v in vessels]
            )
        except Exception:
            pass
        logger.info("Refreshed vessels: %d tracked", len(vessels))
    except Exception as e:
        error_msg = f"Failed to refresh vessels: {e}"
        logger.error(error_msg)
        _record_error(error_msg)


async def refresh_osint():
    """Refresh OSINT intelligence from X, Telegram, and other sources."""
    try:
        x_intel = await osint_service.get_x_intelligence()
        _data_store["x_intelligence"] = x_intel
        _data_store["last_update"]["x_intelligence"] = datetime.now(timezone.utc)
        await manager.broadcast("x_intelligence", x_intel)
        logger.info("Refreshed X intelligence: %d posts", len(x_intel))
    except Exception as e:
        error_msg = f"Failed to refresh X intelligence: {e}"
        logger.error(error_msg)
        _record_error(error_msg)

    try:
        tg_intel = await osint_service.get_telegram_intelligence()
        _data_store["telegram_intelligence"] = tg_intel
        _data_store["last_update"]["telegram_intelligence"] = datetime.now(timezone.utc)
        await manager.broadcast("telegram_intelligence", tg_intel)
        logger.info("Refreshed Telegram intelligence: %d posts", len(tg_intel))
    except Exception as e:
        error_msg = f"Failed to refresh Telegram intelligence: {e}"
        logger.error(error_msg)
        _record_error(error_msg)

    try:
        other_intel = await osint_service.get_other_osint()
        _data_store["osint_other"] = other_intel
        _data_store["last_update"]["osint_other"] = datetime.now(timezone.utc)
        await manager.broadcast("osint_other", other_intel)
        logger.info("Refreshed other OSINT: %d items", len(other_intel))
    except Exception as e:
        error_msg = f"Failed to refresh other OSINT: {e}"
        logger.error(error_msg)
        _record_error(error_msg)


def _record_error(msg: str):
    """Record an error message, keeping only last 50."""
    errors = _data_store.get("errors", [])
    errors.append(f"[{datetime.now(timezone.utc).isoformat()}] {msg}")
    _data_store["errors"] = errors[-50:]


# Track previously seen event IDs to detect new events for alerts
_seen_conflict_ids: set[str] = set()
_seen_missile_ids: set[str] = set()


_alert_title_keys: set[str] = set()  # Track seen alert titles to prevent duplicates


async def _generate_alerts_from_data():
    """Generate alerts only for truly significant new events. Quality over quantity."""
    global _seen_conflict_ids, _seen_missile_ids, _alert_title_keys

    now = datetime.now(timezone.utc)
    new_alerts: list[dict] = []

    # Alert-worthy keywords (only alert on genuinely important events)
    ALERT_KEYWORDS = {
        "breaking", "killed", "casualties", "intercepted", "launched",
        "struck", "explosion", "declared", "invaded", "emergency",
        "escalation", "retaliation", "war", "ceasefire",
    }

    # Check for new conflict events - ONLY critical severity with alert keywords
    conflicts = _data_store.get("conflicts", [])
    for c in conflicts:
        cid = c.id if hasattr(c, "id") else c.get("id", "")
        if cid and cid not in _seen_conflict_ids:
            _seen_conflict_ids.add(cid)
            severity = c.severity if hasattr(c, "severity") else c.get("severity", "medium")
            title = c.title if hasattr(c, "title") else c.get("title", "")
            metadata = c.metadata if hasattr(c, "metadata") else c.get("metadata", {})
            location = metadata.get("location", "") if isinstance(metadata, dict) else ""

            # Only alert on critical events with significant keywords
            if severity != "critical":
                continue
            title_lower = title.lower()
            if not any(kw in title_lower for kw in ALERT_KEYWORDS):
                continue
            # Deduplicate similar alerts (same first 50 chars)
            title_key = title_lower[:50]
            if title_key in _alert_title_keys:
                continue
            _alert_title_keys.add(title_key)

            new_alerts.append({
                "id": f"alert-{cid}",
                "title": f"BREAKING: {title[:120]}",
                "description": f"Source: {c.source if hasattr(c, 'source') else c.get('source', 'News')}" + (f" | {location}" if location else ""),
                "severity": "critical",
                "type": metadata.get("event_type", "conflict") if isinstance(metadata, dict) else "conflict",
                "timestamp": now.isoformat(),
                "region": location,
            })

    # Check for new missile events - only confirmed/intercepted (not every "reported")
    missiles = _data_store.get("missiles", [])
    for m in missiles:
        mid = m.id if hasattr(m, "id") else m.get("id", "")
        if mid and mid not in _seen_missile_ids:
            _seen_missile_ids.add(mid)
            title = m.title if hasattr(m, "title") else m.get("title", "")
            status = m.status if hasattr(m, "status") else m.get("status", "reported")
            metadata = m.metadata if hasattr(m, "metadata") else m.get("metadata", {})
            location = metadata.get("location", "") if isinstance(metadata, dict) else ""

            # Only alert on confirmed or intercepted missile events
            if status not in ("confirmed", "intercepted"):
                continue
            title_key = title.lower()[:50]
            if title_key in _alert_title_keys:
                continue
            _alert_title_keys.add(title_key)

            new_alerts.append({
                "id": f"alert-{mid}",
                "title": f"MISSILE/STRIKE: {title[:120]}",
                "description": f"Status: {status.upper()}" + (f" | {location}" if location else ""),
                "severity": "critical" if status == "confirmed" else "high",
                "type": "missile",
                "timestamp": now.isoformat(),
                "region": location,
            })

    # Broadcast max 5 new alerts at a time (prevent spam)
    for alert in new_alerts[:5]:
        await manager.broadcast("alert", alert)

    # Keep alert keys set from growing forever
    if len(_alert_title_keys) > 500:
        _alert_title_keys.clear()

    return new_alerts


async def initial_data_load():
    """Load all data on startup with timeout protection."""
    logger.info("Starting initial data load...")

    # Load static data immediately (no API calls, instant)
    _data_store["military_bases"] = military_data.get_military_bases()
    _data_store["nuclear_sites"] = military_data.get_nuclear_sites()
    _data_store["waterways"] = military_data.get_waterways()
    _data_store["last_update"]["military_bases"] = datetime.now(timezone.utc)
    _data_store["last_update"]["nuclear_sites"] = datetime.now(timezone.utc)
    _data_store["last_update"]["waterways"] = datetime.now(timezone.utc)

    # Fetch live data concurrently with a global timeout
    # This prevents startup from hanging if external APIs are slow
    tasks = [
        refresh_conflicts(),
        refresh_missiles(),
        refresh_aircraft(),
        refresh_vessels(),
        refresh_earthquakes(),
        refresh_weather(),
        refresh_news(),
        refresh_osint(),
    ]
    try:
        await asyncio.wait_for(
            asyncio.gather(*tasks, return_exceptions=True),
            timeout=25.0,  # 25s max for all API calls during startup
        )
    except asyncio.TimeoutError:
        logger.warning("Initial data load timed out after 25s - some data may load later via scheduler")

    # Generate insights after data is loaded (quick, local computation)
    try:
        await asyncio.wait_for(refresh_ai_insights(), timeout=5.0)
    except asyncio.TimeoutError:
        logger.warning("AI insights generation timed out during startup")

    logger.info("Initial data load complete.")


# ============================================================================
# Application lifecycle
# ============================================================================

scheduler = AsyncIOScheduler()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application startup and shutdown lifecycle."""
    global _start_time
    _start_time = time.time()

    # Initialize database
    await database.init_db()
    logger.info("Database initialized")

    # Initial data load
    await initial_data_load()

    # Schedule periodic refreshes
    scheduler.add_job(refresh_conflicts, "interval", seconds=settings.SCHEDULER_CONFLICTS, id="conflicts")
    scheduler.add_job(refresh_missiles, "interval", seconds=settings.SCHEDULER_CONFLICTS, id="missiles")
    scheduler.add_job(refresh_aircraft, "interval", seconds=5, id="aircraft")
    scheduler.add_job(refresh_earthquakes, "interval", seconds=settings.SCHEDULER_EARTHQUAKES, id="earthquakes")
    scheduler.add_job(refresh_weather, "interval", seconds=settings.SCHEDULER_WEATHER, id="weather")
    scheduler.add_job(refresh_news, "interval", seconds=settings.SCHEDULER_NEWS, id="news")
    scheduler.add_job(refresh_vessels, "interval", seconds=30, id="vessels")
    scheduler.add_job(refresh_ai_insights, "interval", seconds=settings.SCHEDULER_AI_INSIGHTS, id="ai_insights")
    scheduler.add_job(refresh_osint, "interval", seconds=60, id="osint")

    # Daily database cleanup
    scheduler.add_job(
        lambda: asyncio.create_task(database.cleanup_old_data(7)),
        "interval", hours=24, id="db_cleanup"
    )

    scheduler.start()
    logger.info("Background scheduler started with %d jobs", len(scheduler.get_jobs()))

    yield

    # Shutdown
    scheduler.shutdown(wait=False)
    await database.close_db()
    logger.info("Application shutdown complete.")


# ============================================================================
# FastAPI application
# ============================================================================

app = FastAPI(
    title="World Situation Monitor API",
    description="Geopolitical intelligence dashboard backend aggregating OSINT data for Middle East situational awareness.",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS middleware - allow all origins for development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ============================================================================
# REST API Endpoints
# ============================================================================


@app.get("/api/conflicts", response_model=list[GeoEvent], tags=["Events"])
async def get_conflicts():
    """Get current conflict and attack events from GDELT."""
    data = _data_store.get("conflicts", [])
    if not data:
        data = await gdelt_service.get_conflicts()
        _data_store["conflicts"] = data
    return data


@app.get("/api/aircraft", response_model=list[Aircraft], tags=["Tracking"])
async def get_aircraft(
    lamin: Optional[float] = Query(None, description="Minimum latitude"),
    lomin: Optional[float] = Query(None, description="Minimum longitude"),
    lamax: Optional[float] = Query(None, description="Maximum latitude"),
    lomax: Optional[float] = Query(None, description="Maximum longitude"),
    military_only: bool = Query(False, description="Filter for military aircraft only"),
):
    """Get live aircraft positions from OpenSky Network."""
    if military_only:
        data = _data_store.get("military_aircraft", [])
        if not data:
            data = await opensky_service.get_military_aircraft()
        return data

    if all(v is not None for v in [lamin, lomin, lamax, lomax]):
        bbox = (lamin, lomin, lamax, lomax)
        return await opensky_service.get_aircraft(bbox)

    data = _data_store.get("aircraft", [])
    if not data:
        data = await opensky_service.get_aircraft()
        _data_store["aircraft"] = data
    return data


@app.get("/api/vessels", response_model=list[Vessel], tags=["Tracking"])
async def get_vessels(
    military_only: bool = Query(False, description="Filter for military vessels only"),
):
    """Get vessel positions from AIS data and simulation."""
    if military_only:
        data = _data_store.get("military_vessels", [])
        if not data:
            data = await ais_service.get_military_vessels()
        return data

    data = _data_store.get("vessels", [])
    if not data:
        data = await ais_service.get_vessels()
        _data_store["vessels"] = data
    return data


@app.get("/api/aircraft/trails/{icao24}", tags=["Tracking"])
async def get_aircraft_trail(icao24: str, limit: int = Query(50, le=200)):
    """Get position history for a specific aircraft."""
    trail = await database.get_aircraft_trails(icao24, limit=limit)
    return trail


@app.get("/api/historical/{layer}", tags=["Historical"])
async def get_historical_data(
    layer: str,
    hours: int = Query(24, le=168, description="Hours of history to return"),
):
    """Get historical event counts for charts/trends."""
    counts = await database.get_historical_counts(layer, hours=hours)
    return counts


@app.get("/api/missiles", response_model=list[MissileEvent], tags=["Events"])
async def get_missiles():
    """Get reported missile and rocket events."""
    data = _data_store.get("missiles", [])
    if not data:
        data = await gdelt_service.get_missile_events()
        _data_store["missiles"] = data
    return data


@app.get("/api/earthquakes", response_model=list[GeoEvent], tags=["Events"])
async def get_earthquakes():
    """Get recent earthquake events from USGS."""
    data = _data_store.get("earthquakes", [])
    if not data:
        data = await usgs_service.get_earthquakes()
        _data_store["earthquakes"] = data
    return data


@app.get("/api/weather", response_model=list[WeatherAlert], tags=["Environment"])
async def get_weather():
    """Get weather data and alerts for tracked Middle East cities."""
    data = _data_store.get("weather", [])
    if not data:
        data = await weather_service.get_weather_data()
        _data_store["weather"] = data
    return data


@app.get("/api/military-bases", response_model=list[MilitaryBase], tags=["Static Data"])
async def get_military_bases():
    """Get known military installations in the Middle East region."""
    data = _data_store.get("military_bases", [])
    if not data:
        data = military_data.get_military_bases()
        _data_store["military_bases"] = data
    return data


@app.get("/api/nuclear", response_model=list[NuclearSite], tags=["Static Data"])
async def get_nuclear():
    """Get known nuclear facilities in the Middle East region."""
    data = _data_store.get("nuclear_sites", [])
    if not data:
        data = military_data.get_nuclear_sites()
        _data_store["nuclear_sites"] = data
    return data


@app.get("/api/waterways", response_model=list[Waterway], tags=["Static Data"])
async def get_waterways():
    """Get strategic waterways and chokepoints."""
    data = _data_store.get("waterways", [])
    if not data:
        data = military_data.get_waterways()
        _data_store["waterways"] = data
    return data


@app.get("/api/news", response_model=list[NewsItem], tags=["News"])
async def get_news(
    country: Optional[str] = Query(None, description="Filter news by country")
):
    """Get Middle East news articles from GDELT."""
    if country:
        return await news_service.get_news(country=country)

    data = _data_store.get("news", [])
    if not data:
        data = await news_service.get_news()
        _data_store["news"] = data
    return data


@app.get("/api/live-feeds", response_model=list[LiveFeed], tags=["News"])
async def get_live_feeds(
    country: Optional[str] = Query(None, description="Filter feeds by country")
):
    """Get curated live news stream URLs for Middle East coverage."""
    return news_service.get_live_feeds(country=country)


@app.get("/api/ai-insights", response_model=list[AIInsight], tags=["Analysis"])
async def get_ai_insights():
    """Get AI-generated situation analysis and insights."""
    data = _data_store.get("ai_insights", [])
    if not data:
        data = await ai_service.generate_insights(
            conflicts=_data_store.get("conflicts", []),
            missiles=_data_store.get("missiles", []),
            aircraft=_data_store.get("military_aircraft", []),
        )
        _data_store["ai_insights"] = data
    return data


@app.get("/api/osint/x", tags=["OSINT"])
async def get_x_intelligence():
    """Get intelligence from X/Twitter OSINT accounts."""
    data = _data_store.get("x_intelligence", [])
    if not data:
        data = await osint_service.get_x_intelligence()
        _data_store["x_intelligence"] = data
    return data


@app.get("/api/osint/telegram", tags=["OSINT"])
async def get_telegram_intelligence():
    """Get intelligence from public Telegram OSINT channels."""
    data = _data_store.get("telegram_intelligence", [])
    if not data:
        data = await osint_service.get_telegram_intelligence()
        _data_store["telegram_intelligence"] = data
    return data


@app.get("/api/osint/other", tags=["OSINT"])
async def get_other_osint():
    """Get intelligence from other OSINT sources (ReliefWeb, briefings)."""
    data = _data_store.get("osint_other", [])
    if not data:
        data = await osint_service.get_other_osint()
        _data_store["osint_other"] = data
    return data


@app.get("/api/all-layers", tags=["Combined"])
async def get_all_layers():
    """
    Get combined GeoJSON-style response with all layer data.
    Useful for initial map load to get everything in one request.
    """
    return {
        "type": "FeatureCollection",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "layers": {
            "conflicts": {
                "type": "events",
                "count": len(_data_store.get("conflicts", [])),
                "data": _serialize(_data_store.get("conflicts", [])),
            },
            "aircraft": {
                "type": "tracking",
                "count": len(_data_store.get("aircraft", [])),
                "military_count": len(_data_store.get("military_aircraft", [])),
                "data": _serialize(_data_store.get("aircraft", [])),
            },
            "vessels": {
                "type": "tracking",
                "count": len(_data_store.get("vessels", [])),
                "data": _serialize(_data_store.get("vessels", [])),
            },
            "missiles": {
                "type": "events",
                "count": len(_data_store.get("missiles", [])),
                "data": _serialize(_data_store.get("missiles", [])),
            },
            "earthquakes": {
                "type": "events",
                "count": len(_data_store.get("earthquakes", [])),
                "data": _serialize(_data_store.get("earthquakes", [])),
            },
            "weather": {
                "type": "environment",
                "count": len(_data_store.get("weather", [])),
                "data": _serialize(_data_store.get("weather", [])),
            },
            "military_bases": {
                "type": "static",
                "count": len(_data_store.get("military_bases", [])),
                "data": _serialize(_data_store.get("military_bases", [])),
            },
            "nuclear_sites": {
                "type": "static",
                "count": len(_data_store.get("nuclear_sites", [])),
                "data": _serialize(_data_store.get("nuclear_sites", [])),
            },
            "waterways": {
                "type": "static",
                "count": len(_data_store.get("waterways", [])),
                "data": _serialize(_data_store.get("waterways", [])),
            },
            "news": {
                "type": "feed",
                "count": len(_data_store.get("news", [])),
                "data": _serialize(_data_store.get("news", [])),
            },
        },
        "meta": {
            "bounding_box": {
                "lat_min": settings.ME_LAT_MIN,
                "lat_max": settings.ME_LAT_MAX,
                "lon_min": settings.ME_LON_MIN,
                "lon_max": settings.ME_LON_MAX,
            },
        },
    }


@app.get("/api/status", response_model=SystemStatus, tags=["System"])
async def get_status():
    """Get system health, data freshness, and layer counts."""
    now = datetime.now(timezone.utc)
    uptime = time.time() - _start_time

    last_update = _data_store.get("last_update", {})

    data_freshness = {}
    for layer in ["conflicts", "aircraft", "vessels", "missiles", "earthquakes", "weather", "news",
                  "military_bases", "nuclear_sites", "waterways", "ai_insights",
                  "x_intelligence", "telegram_intelligence", "osint_other"]:
        ts = last_update.get(layer)
        data_freshness[layer] = ts

    layer_counts = {
        "conflicts": len(_data_store.get("conflicts", [])),
        "aircraft": len(_data_store.get("aircraft", [])),
        "military_aircraft": len(_data_store.get("military_aircraft", [])),
        "vessels": len(_data_store.get("vessels", [])),
        "missiles": len(_data_store.get("missiles", [])),
        "earthquakes": len(_data_store.get("earthquakes", [])),
        "weather": len(_data_store.get("weather", [])),
        "news": len(_data_store.get("news", [])),
        "military_bases": len(_data_store.get("military_bases", [])),
        "nuclear_sites": len(_data_store.get("nuclear_sites", [])),
        "waterways": len(_data_store.get("waterways", [])),
        "ai_insights": len(_data_store.get("ai_insights", [])),
        "x_intelligence": len(_data_store.get("x_intelligence", [])),
        "telegram_intelligence": len(_data_store.get("telegram_intelligence", [])),
        "osint_other": len(_data_store.get("osint_other", [])),
    }

    errors = _data_store.get("errors", [])

    # Determine overall status
    total_data = sum(layer_counts.values())
    if total_data == 0:
        status = "initializing"
    elif len(errors) > 10:
        status = "degraded"
    else:
        status = "operational"

    return SystemStatus(
        status=status,
        uptime_seconds=uptime,
        last_update=now,
        data_freshness=data_freshness,
        layer_counts=layer_counts,
        errors=errors[-10:],
    )


# ============================================================================
# WebSocket endpoint
# ============================================================================


@app.websocket("/ws/live")
async def websocket_endpoint(websocket: WebSocket):
    """
    WebSocket endpoint for real-time data updates.

    Clients can subscribe to specific layers by sending:
    {"action": "subscribe", "layers": ["conflicts", "aircraft", "missiles"]}

    Or subscribe to all updates:
    {"action": "subscribe", "layers": ["all"]}

    Unsubscribe:
    {"action": "unsubscribe", "layers": ["aircraft"]}
    """
    await manager.connect(websocket)

    # Send initial connection acknowledgment
    try:
        await websocket.send_json({
            "type": "connected",
            "message": "Connected to World Situation Monitor live feed",
            "available_layers": [
                "conflicts", "aircraft", "vessels", "missiles", "earthquakes",
                "weather", "news", "ai_insights", "x_intelligence",
                "telegram_intelligence", "osint_other", "all"
            ],
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })
    except Exception:
        manager.disconnect(websocket)
        return

    try:
        while True:
            data = await websocket.receive_text()
            try:
                message = json.loads(data)
                action = message.get("action", "")
                layers = message.get("layers", [])

                if action == "subscribe":
                    manager.subscribe(websocket, layers)
                    await websocket.send_json({
                        "type": "subscribed",
                        "layers": layers,
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                    })

                elif action == "unsubscribe":
                    manager.unsubscribe(websocket, layers)
                    await websocket.send_json({
                        "type": "unsubscribed",
                        "layers": layers,
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                    })

                elif action == "ping":
                    await websocket.send_json({
                        "type": "pong",
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                    })

                elif action == "get_snapshot":
                    # Send current data for requested layers
                    for layer in layers:
                        layer_data = _data_store.get(layer, [])
                        if layer_data:
                            await websocket.send_json({
                                "type": "snapshot",
                                "layer": layer,
                                "data": _serialize(layer_data),
                                "timestamp": datetime.now(timezone.utc).isoformat(),
                            })

                else:
                    await websocket.send_json({
                        "type": "error",
                        "message": f"Unknown action: {action}",
                    })

            except json.JSONDecodeError:
                await websocket.send_json({
                    "type": "error",
                    "message": "Invalid JSON message",
                })

    except WebSocketDisconnect:
        manager.disconnect(websocket)
    except Exception as e:
        logger.error("WebSocket error: %s", str(e))
        manager.disconnect(websocket)


# ============================================================================
# Run with uvicorn
# ============================================================================

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=True,
        log_level="info",
    )
