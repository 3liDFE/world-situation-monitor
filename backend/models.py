"""
Pydantic models for the World Situation Monitor.
Defines data structures for all geopolitical intelligence layers.
"""

from datetime import datetime
from typing import Any, Optional
from pydantic import BaseModel, Field


class GeoEvent(BaseModel):
    """Generic geopolitical or natural event with location."""
    id: str
    type: str = Field(description="Event type: conflict, earthquake, weather, etc.")
    lat: float
    lon: float
    title: str
    description: str = ""
    severity: str = Field(default="low", description="low, medium, high, critical")
    source: str = ""
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    metadata: dict[str, Any] = Field(default_factory=dict)


class Aircraft(BaseModel):
    """Live aircraft position from ADS-B transponder data."""
    icao24: str = Field(description="Unique ICAO 24-bit transponder address")
    callsign: str = ""
    lat: Optional[float] = None
    lon: Optional[float] = None
    altitude: Optional[float] = Field(default=None, description="Barometric altitude in meters")
    velocity: Optional[float] = Field(default=None, description="Ground speed in m/s")
    heading: Optional[float] = Field(default=None, description="True track in degrees")
    on_ground: bool = False
    origin_country: str = ""
    baro_altitude: Optional[float] = None
    geo_altitude: Optional[float] = None
    squawk: Optional[str] = None
    last_contact: Optional[int] = None
    aircraft_type: str = Field(default="", description="Identified aircraft type (e.g., F-16, C-17)")
    operator: str = Field(default="", description="Aircraft operator (e.g., USAF, RAF)")
    is_military: bool = False
    type_confidence: str = Field(default="", description="Type identification confidence: high, medium, low")


class Vessel(BaseModel):
    """Naval vessel position."""
    mmsi: str = Field(description="Maritime Mobile Service Identity")
    name: str = ""
    lat: float = 0.0
    lon: float = 0.0
    speed: Optional[float] = Field(default=None, description="Speed over ground in knots")
    course: Optional[float] = Field(default=None, description="Course over ground in degrees")
    vessel_type: str = ""
    flag: str = ""
    destination: str = ""
    last_update: datetime = Field(default_factory=datetime.utcnow)


class MissileEvent(BaseModel):
    """Reported missile or rocket event."""
    id: str
    launch_lat: Optional[float] = None
    launch_lon: Optional[float] = None
    target_lat: Optional[float] = None
    target_lon: Optional[float] = None
    missile_type: str = Field(default="unknown", description="missile, rocket, projectile, drone")
    status: str = Field(default="reported", description="reported, confirmed, intercepted")
    source: str = ""
    title: str = ""
    description: str = ""
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    metadata: dict[str, Any] = Field(default_factory=dict)


class ConflictZone(BaseModel):
    """Active conflict zone with defined area."""
    id: str
    name: str
    lat: float
    lon: float
    radius: float = Field(description="Approximate radius in km")
    intensity: str = Field(default="low", description="low, medium, high, critical")
    parties: list[str] = Field(default_factory=list)
    description: str = ""
    last_updated: datetime = Field(default_factory=datetime.utcnow)


class MilitaryBase(BaseModel):
    """Known military installation."""
    id: str
    name: str
    lat: float
    lon: float
    country: str
    type: str = Field(description="air_base, naval_base, army_base, combined, missile_base")
    branch: str = Field(default="", description="air_force, navy, army, marines, combined")
    status: str = Field(default="active", description="active, inactive, limited")
    operator: str = Field(default="", description="Operating nation if different from host country")
    description: str = ""


class NuclearSite(BaseModel):
    """Known nuclear facility."""
    id: str
    name: str
    lat: float
    lon: float
    country: str
    type: str = Field(description="reactor, enrichment, research, weapons, power_plant")
    status: str = Field(default="active", description="active, inactive, under_construction, decommissioned")
    description: str = ""


class Waterway(BaseModel):
    """Strategic waterway or chokepoint."""
    id: str
    name: str
    lat: float
    lon: float
    type: str = Field(default="strait", description="strait, canal, passage")
    description: str = ""
    daily_traffic: str = ""
    strategic_importance: str = Field(default="high", description="medium, high, critical")
    controlled_by: str = ""
    coordinates: list[list[float]] = Field(default_factory=list, description="Polyline coordinates [[lat,lon],...]")


class NewsItem(BaseModel):
    """News article from feeds."""
    id: str
    title: str
    description: str = ""
    url: str = ""
    image_url: str = ""
    source: str = ""
    country: str = ""
    published_at: datetime = Field(default_factory=datetime.utcnow)
    keywords: list[str] = Field(default_factory=list)
    sentiment: str = Field(default="neutral", description="positive, neutral, negative")


class WeatherAlert(BaseModel):
    """Weather data or alert for a tracked city."""
    id: str
    city: str = ""
    lat: float = 0.0
    lon: float = 0.0
    event: str = ""
    severity: str = Field(default="info", description="info, moderate, severe, extreme")
    description: str = ""
    temperature: Optional[float] = None
    wind_speed: Optional[float] = None
    weather_code: Optional[int] = None
    start: Optional[datetime] = None
    end: Optional[datetime] = None


class AIInsight(BaseModel):
    """AI-generated intelligence analysis."""
    id: str
    title: str
    summary: str
    analysis: str
    severity: str = Field(default="medium", description="low, medium, high, critical")
    region: str = ""
    generated_at: datetime = Field(default_factory=datetime.utcnow)
    data_sources: list[str] = Field(default_factory=list)
    confidence: float = Field(default=0.7, ge=0.0, le=1.0)


class LiveFeed(BaseModel):
    """Live news stream URL."""
    country: str
    channel_name: str
    stream_url: str
    language: str = ""
    category: str = Field(default="news", description="news, military, general")


class OsintPost(BaseModel):
    """OSINT intelligence post from X/Twitter, Telegram, or other sources."""
    id: str
    source: str = Field(description="x_twitter, telegram, osint_brief, reliefweb")
    channel: str = ""
    handle: str = ""
    text: str = ""
    timestamp: str = ""
    url: str = ""
    focus: str = ""
    category: str = Field(default="general", description="missile, strike, drone, naval, aviation, etc.")
    verified: bool = False
    classification: str = Field(default="OSINT", description="Intelligence classification level")


class SystemStatus(BaseModel):
    """System health and data freshness."""
    status: str = "operational"
    uptime_seconds: float = 0.0
    last_update: datetime = Field(default_factory=datetime.utcnow)
    data_freshness: dict[str, Optional[datetime]] = Field(default_factory=dict)
    layer_counts: dict[str, int] = Field(default_factory=dict)
    errors: list[str] = Field(default_factory=list)
