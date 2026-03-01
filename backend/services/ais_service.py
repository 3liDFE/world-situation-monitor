"""
AIS Vessel Tracking Service - Tracks naval vessels in Middle East waters.

Provides vessel position data for the World Situation Monitor. Uses a tiered
data acquisition strategy:

  1. AISHub free API (https://www.aishub.net/api) - community-shared AIS data
  2. Simulated fallback - generates realistic vessel positions along known
     shipping lanes and naval patrol areas when live feeds are unavailable

Vessel categories of interest:
  - Military vessels (warships, patrol boats, carrier groups)
  - Oil tankers (critical for Strait of Hormuz / Persian Gulf monitoring)
  - Cargo ships (waterway traffic density)

The simulation layer uses time-seeded deterministic drift so positions
change naturally over time while remaining reproducible within each
refresh window.
"""

import hashlib
import logging
import math
import os
import time
from datetime import datetime, timezone
from typing import Optional

import httpx
from cachetools import TTLCache

from config import settings
from models import Vessel

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Cache - 30 second TTL keeps vessel positions fresh without hammering APIs
# ---------------------------------------------------------------------------

_vessel_cache: TTLCache = TTLCache(maxsize=10, ttl=30)

# ---------------------------------------------------------------------------
# AISHub configuration
# ---------------------------------------------------------------------------

AISHUB_API_URL = "https://data.aishub.net/ws.php"
AISHUB_USERNAME = os.getenv("AISHUB_USERNAME", "")

# ---------------------------------------------------------------------------
# AIS vessel type codes (ITU-R M.585-7 / AIS message type 5)
# ---------------------------------------------------------------------------

# Military and law enforcement (AIS type 35, 55, or unlisted)
_MILITARY_AIS_TYPES = {35, 55}

# Tanker types (AIS type 80-89)
_TANKER_AIS_TYPES = set(range(80, 90))

# Cargo types (AIS type 70-79)
_CARGO_AIS_TYPES = set(range(70, 80))

# Vessel type label mapping for AIS numeric codes
_AIS_TYPE_LABELS: dict[int, str] = {
    **{t: "military" for t in _MILITARY_AIS_TYPES},
    **{t: "tanker" for t in _TANKER_AIS_TYPES},
    **{t: "cargo" for t in _CARGO_AIS_TYPES},
    30: "fishing",
    31: "towing",
    32: "towing_large",
    33: "dredger",
    36: "sailing",
    37: "pleasure_craft",
    40: "high_speed_craft",
    50: "pilot_vessel",
    51: "search_and_rescue",
    52: "tug",
    60: "passenger",
}

# ---------------------------------------------------------------------------
# Strategic waterway zones (name -> (center_lat, center_lon, radius_deg))
# Used both for proximity filtering and simulation seed regions.
# ---------------------------------------------------------------------------

STRATEGIC_ZONES: dict[str, tuple[float, float, float]] = {
    "strait_of_hormuz": (26.57, 56.25, 1.0),
    "persian_gulf_central": (27.00, 51.00, 2.5),
    "persian_gulf_north": (29.00, 49.50, 1.5),
    "suez_canal": (30.46, 32.35, 0.5),
    "bab_el_mandeb": (12.58, 43.33, 1.0),
    "gulf_of_aden": (12.50, 45.50, 2.0),
    "arabian_sea_west": (21.00, 60.00, 3.0),
    "red_sea_south": (15.00, 42.00, 2.0),
    "gulf_of_oman": (24.50, 58.50, 1.5),
}

# ---------------------------------------------------------------------------
# Simulated vessel definitions
#
# Each entry defines a vessel with a home position and patrol/transit
# behaviour. The simulation drifts vessels along their route using
# time-based deterministic offsets so positions evolve naturally.
# ---------------------------------------------------------------------------

_SIMULATED_VESSEL_DEFS: list[dict] = [
    # ===== US CARRIER STRIKE GROUP (Persian Gulf / Arabian Sea) =====
    {
        "mmsi": "SIM-USS-CVN-77",
        "name": "USS George H.W. Bush (CVN-77)",
        "vessel_type": "military",
        "flag": "US",
        "destination": "Persian Gulf Patrol",
        "base_lat": 25.30,
        "base_lon": 57.80,
        "patrol_radius": 1.8,
        "speed_range": (8.0, 16.0),
        "zone": "gulf_of_oman",
    },
    {
        "mmsi": "SIM-USS-CG-66",
        "name": "USS Hue City (CG-66)",
        "vessel_type": "military",
        "flag": "US",
        "destination": "CSG Escort - Persian Gulf",
        "base_lat": 25.50,
        "base_lon": 57.50,
        "patrol_radius": 1.2,
        "speed_range": (10.0, 18.0),
        "zone": "gulf_of_oman",
    },
    {
        "mmsi": "SIM-USS-DDG-100",
        "name": "USS Kidd (DDG-100)",
        "vessel_type": "military",
        "flag": "US",
        "destination": "Strait of Hormuz Patrol",
        "base_lat": 26.40,
        "base_lon": 56.50,
        "patrol_radius": 0.8,
        "speed_range": (10.0, 20.0),
        "zone": "strait_of_hormuz",
    },
    {
        "mmsi": "SIM-USS-DDG-112",
        "name": "USS Michael Murphy (DDG-112)",
        "vessel_type": "military",
        "flag": "US",
        "destination": "Arabian Sea Patrol",
        "base_lat": 22.00,
        "base_lon": 61.00,
        "patrol_radius": 2.0,
        "speed_range": (10.0, 22.0),
        "zone": "arabian_sea_west",
    },
    {
        "mmsi": "SIM-USS-LHD-7",
        "name": "USS Iwo Jima (LHD-7)",
        "vessel_type": "military",
        "flag": "US",
        "destination": "Red Sea Operations",
        "base_lat": 14.00,
        "base_lon": 42.50,
        "patrol_radius": 1.5,
        "speed_range": (8.0, 15.0),
        "zone": "red_sea_south",
    },
    {
        "mmsi": "SIM-USS-DDG-117",
        "name": "USS Paul Ignatius (DDG-117)",
        "vessel_type": "military",
        "flag": "US",
        "destination": "Bab el-Mandeb Patrol",
        "base_lat": 12.80,
        "base_lon": 43.50,
        "patrol_radius": 1.0,
        "speed_range": (10.0, 20.0),
        "zone": "bab_el_mandeb",
    },

    # ===== IRANIAN NAVY (Strait of Hormuz / Persian Gulf) =====
    {
        "mmsi": "SIM-IRIN-FF-72",
        "name": "IRIS Sahand (F-74)",
        "vessel_type": "military",
        "flag": "IR",
        "destination": "Hormuz Patrol",
        "base_lat": 27.10,
        "base_lon": 56.30,
        "patrol_radius": 0.6,
        "speed_range": (6.0, 14.0),
        "zone": "strait_of_hormuz",
    },
    {
        "mmsi": "SIM-IRIN-PB-01",
        "name": "IRGCN Fast Attack Craft 01",
        "vessel_type": "military",
        "flag": "IR",
        "destination": "Hormuz Strait Patrol",
        "base_lat": 26.70,
        "base_lon": 56.10,
        "patrol_radius": 0.4,
        "speed_range": (15.0, 40.0),
        "zone": "strait_of_hormuz",
    },
    {
        "mmsi": "SIM-IRIN-PB-02",
        "name": "IRGCN Fast Attack Craft 02",
        "vessel_type": "military",
        "flag": "IR",
        "destination": "Hormuz Strait Patrol",
        "base_lat": 26.50,
        "base_lon": 56.40,
        "patrol_radius": 0.4,
        "speed_range": (15.0, 40.0),
        "zone": "strait_of_hormuz",
    },
    {
        "mmsi": "SIM-IRIN-PB-03",
        "name": "IRGCN Fast Attack Craft 03",
        "vessel_type": "military",
        "flag": "IR",
        "destination": "Abu Musa Island Patrol",
        "base_lat": 25.87,
        "base_lon": 55.03,
        "patrol_radius": 0.5,
        "speed_range": (12.0, 35.0),
        "zone": "persian_gulf_central",
    },
    {
        "mmsi": "SIM-IRIN-SS-01",
        "name": "IRIS Fateh (S-Fateh)",
        "vessel_type": "military",
        "flag": "IR",
        "destination": "Gulf of Oman Patrol",
        "base_lat": 25.00,
        "base_lon": 58.00,
        "patrol_radius": 1.0,
        "speed_range": (4.0, 10.0),
        "zone": "gulf_of_oman",
    },

    # ===== ROYAL SAUDI NAVY =====
    {
        "mmsi": "SIM-RSN-FF-01",
        "name": "HMS Al Riyadh (F-3000S)",
        "vessel_type": "military",
        "flag": "SA",
        "destination": "Red Sea Patrol",
        "base_lat": 20.50,
        "base_lon": 39.50,
        "patrol_radius": 1.5,
        "speed_range": (8.0, 18.0),
        "zone": "red_sea_south",
    },

    # ===== UK ROYAL NAVY =====
    {
        "mmsi": "SIM-RN-FF-01",
        "name": "HMS Lancaster (F-229)",
        "vessel_type": "military",
        "flag": "GB",
        "destination": "Gulf Patrol",
        "base_lat": 26.00,
        "base_lon": 53.00,
        "patrol_radius": 1.5,
        "speed_range": (8.0, 16.0),
        "zone": "persian_gulf_central",
    },

    # ===== FRENCH NAVY =====
    {
        "mmsi": "SIM-MN-FF-01",
        "name": "FS Alsace (D-656)",
        "vessel_type": "military",
        "flag": "FR",
        "destination": "Gulf of Aden Patrol",
        "base_lat": 12.20,
        "base_lon": 44.50,
        "patrol_radius": 1.5,
        "speed_range": (8.0, 18.0),
        "zone": "gulf_of_aden",
    },

    # ===== OIL TANKERS - Strait of Hormuz transit =====
    {
        "mmsi": "SIM-TK-VLCC-01",
        "name": "ENERGY PIONEER",
        "vessel_type": "tanker",
        "flag": "PA",
        "destination": "Ras Tanura -> Fujairah",
        "base_lat": 26.60,
        "base_lon": 56.00,
        "patrol_radius": 0.5,
        "speed_range": (10.0, 14.0),
        "zone": "strait_of_hormuz",
    },
    {
        "mmsi": "SIM-TK-VLCC-02",
        "name": "GULF STAR",
        "vessel_type": "tanker",
        "flag": "LR",
        "destination": "Kharg Island -> Jebel Ali",
        "base_lat": 26.30,
        "base_lon": 56.40,
        "patrol_radius": 0.5,
        "speed_range": (10.0, 14.0),
        "zone": "strait_of_hormuz",
    },
    {
        "mmsi": "SIM-TK-VLCC-03",
        "name": "ARABIAN LIGHT",
        "vessel_type": "tanker",
        "flag": "SG",
        "destination": "Jubail -> Far East",
        "base_lat": 25.80,
        "base_lon": 56.80,
        "patrol_radius": 0.6,
        "speed_range": (11.0, 14.0),
        "zone": "gulf_of_oman",
    },
    {
        "mmsi": "SIM-TK-VLCC-04",
        "name": "PERSIAN VOYAGER",
        "vessel_type": "tanker",
        "flag": "MH",
        "destination": "Basra -> Singapore",
        "base_lat": 27.50,
        "base_lon": 52.00,
        "patrol_radius": 0.8,
        "speed_range": (9.0, 13.0),
        "zone": "persian_gulf_central",
    },
    {
        "mmsi": "SIM-TK-VLCC-05",
        "name": "DUBAI FORTUNE",
        "vessel_type": "tanker",
        "flag": "BS",
        "destination": "Fujairah -> Suez Canal",
        "base_lat": 22.50,
        "base_lon": 60.50,
        "patrol_radius": 1.5,
        "speed_range": (11.0, 15.0),
        "zone": "arabian_sea_west",
    },
    {
        "mmsi": "SIM-TK-PROD-01",
        "name": "RED SEA CARRIER",
        "vessel_type": "tanker",
        "flag": "MT",
        "destination": "Yanbu -> Suez",
        "base_lat": 22.00,
        "base_lon": 38.50,
        "patrol_radius": 1.0,
        "speed_range": (10.0, 14.0),
        "zone": "red_sea_south",
    },

    # ===== CARGO SHIPS - Suez Canal traffic =====
    {
        "mmsi": "SIM-CG-CNTR-01",
        "name": "MAERSK EUPHRATES",
        "vessel_type": "cargo",
        "flag": "DK",
        "destination": "Jebel Ali -> Rotterdam",
        "base_lat": 30.20,
        "base_lon": 32.35,
        "patrol_radius": 0.3,
        "speed_range": (8.0, 12.0),
        "zone": "suez_canal",
    },
    {
        "mmsi": "SIM-CG-CNTR-02",
        "name": "COSCO ARABIAN SEA",
        "vessel_type": "cargo",
        "flag": "CN",
        "destination": "Shanghai -> Port Said",
        "base_lat": 30.50,
        "base_lon": 32.33,
        "patrol_radius": 0.3,
        "speed_range": (7.0, 11.0),
        "zone": "suez_canal",
    },
    {
        "mmsi": "SIM-CG-CNTR-03",
        "name": "MSC PETRA",
        "vessel_type": "cargo",
        "flag": "CH",
        "destination": "Jeddah -> Suez",
        "base_lat": 30.00,
        "base_lon": 32.55,
        "patrol_radius": 0.3,
        "speed_range": (6.0, 10.0),
        "zone": "suez_canal",
    },
    {
        "mmsi": "SIM-CG-BULK-01",
        "name": "OCEAN TRADER",
        "vessel_type": "cargo",
        "flag": "GR",
        "destination": "Salalah -> Jeddah",
        "base_lat": 14.50,
        "base_lon": 43.00,
        "patrol_radius": 0.8,
        "speed_range": (9.0, 13.0),
        "zone": "bab_el_mandeb",
    },
    {
        "mmsi": "SIM-CG-BULK-02",
        "name": "ARABIAN MERCHANT",
        "vessel_type": "cargo",
        "flag": "IN",
        "destination": "Mumbai -> Dammam",
        "base_lat": 25.00,
        "base_lon": 57.50,
        "patrol_radius": 1.0,
        "speed_range": (9.0, 13.0),
        "zone": "gulf_of_oman",
    },
    {
        "mmsi": "SIM-CG-RORO-01",
        "name": "GULF BRIDGE",
        "vessel_type": "cargo",
        "flag": "AE",
        "destination": "Dubai -> Kuwait",
        "base_lat": 28.00,
        "base_lon": 50.00,
        "patrol_radius": 1.0,
        "speed_range": (10.0, 15.0),
        "zone": "persian_gulf_north",
    },

    # ===== BAB EL-MANDEB THREAT AREA (Houthi threat zone) =====
    {
        "mmsi": "SIM-CG-CNTR-04",
        "name": "HAPAG YEMEN STRAIT",
        "vessel_type": "cargo",
        "flag": "DE",
        "destination": "Colombo -> Suez Canal",
        "base_lat": 13.00,
        "base_lon": 43.80,
        "patrol_radius": 0.6,
        "speed_range": (12.0, 16.0),
        "zone": "bab_el_mandeb",
    },
    {
        "mmsi": "SIM-TK-LNG-01",
        "name": "QATAR GAS TRANSPORT",
        "vessel_type": "tanker",
        "flag": "QA",
        "destination": "Ras Laffan -> Europe",
        "base_lat": 13.50,
        "base_lon": 44.00,
        "patrol_radius": 0.6,
        "speed_range": (14.0, 18.0),
        "zone": "bab_el_mandeb",
    },
]


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _generate_id(text: str) -> str:
    """Generate a deterministic short ID from text content."""
    return hashlib.md5(text.encode("utf-8", errors="replace")).hexdigest()[:12]


def _in_bbox(
    lat: float,
    lon: float,
    lat_min: float,
    lon_min: float,
    lat_max: float,
    lon_max: float,
) -> bool:
    """Return True if the point is inside the bounding box."""
    return lat_min <= lat <= lat_max and lon_min <= lon <= lon_max


def _near_strategic_zone(lat: float, lon: float) -> Optional[str]:
    """
    Return the name of the nearest strategic zone within range,
    or None if the vessel is not near any zone of interest.
    """
    for name, (clat, clon, radius) in STRATEGIC_ZONES.items():
        dlat = lat - clat
        dlon = lon - clon
        if math.sqrt(dlat * dlat + dlon * dlon) <= radius:
            return name
    return None


def _classify_ais_type(ais_type_code: int) -> str:
    """Map an AIS numeric vessel type code to a human-readable label."""
    return _AIS_TYPE_LABELS.get(ais_type_code, "other")


def _is_vessel_of_interest(vessel_type: str) -> bool:
    """Return True if the vessel type is one we want to track."""
    return vessel_type in ("military", "tanker", "cargo")


# ---------------------------------------------------------------------------
# Time-based deterministic drift for simulation
#
# The goal: positions should change gradually over time so the map looks
# alive, but remain consistent within a given 30-second cache window so
# all clients see the same state.  We use the current time truncated to
# 30-second intervals as a seed.
# ---------------------------------------------------------------------------


def _current_time_seed() -> int:
    """Return a seed that changes every 30 seconds."""
    return int(time.time()) // 30


def _drift_position(
    base_lat: float,
    base_lon: float,
    patrol_radius: float,
    seed_salt: str,
) -> tuple[float, float]:
    """
    Compute a drifted position around a base point.

    Uses the current time seed combined with a vessel-specific salt so
    each vessel moves independently.  The drift traces a smooth
    Lissajous-like path within the patrol radius.
    """
    t_seed = _current_time_seed()
    # Deterministic hash for this vessel at this time window
    h = hashlib.sha256(f"{seed_salt}:{t_seed}".encode()).hexdigest()
    # Extract two independent values in [0, 1)
    frac_a = int(h[:8], 16) / 0xFFFFFFFF
    frac_b = int(h[8:16], 16) / 0xFFFFFFFF

    # Map to angle + radius for smooth orbital motion
    angle = frac_a * 2 * math.pi
    r = patrol_radius * (0.3 + 0.7 * frac_b)  # between 30-100% of radius

    dlat = r * math.cos(angle)
    dlon = r * math.sin(angle) / max(math.cos(math.radians(base_lat)), 0.1)

    return base_lat + dlat, base_lon + dlon


def _drift_course(seed_salt: str) -> float:
    """Compute a drifted course (0-360 degrees)."""
    t_seed = _current_time_seed()
    h = hashlib.sha256(f"course:{seed_salt}:{t_seed}".encode()).hexdigest()
    return (int(h[:8], 16) / 0xFFFFFFFF) * 360.0


def _drift_speed(speed_min: float, speed_max: float, seed_salt: str) -> float:
    """Compute a drifted speed within the given range."""
    t_seed = _current_time_seed()
    h = hashlib.sha256(f"speed:{seed_salt}:{t_seed}".encode()).hexdigest()
    frac = int(h[:8], 16) / 0xFFFFFFFF
    return round(speed_min + frac * (speed_max - speed_min), 1)


# ---------------------------------------------------------------------------
# Simulation layer
# ---------------------------------------------------------------------------


def _generate_simulated_vessels(
    lat_min: float,
    lon_min: float,
    lat_max: float,
    lon_max: float,
) -> list[Vessel]:
    """
    Generate realistic simulated vessel positions for the given bounding box.

    Vessels drift over time using deterministic position offsets so the
    display looks alive without requiring a real AIS feed.
    """
    vessels: list[Vessel] = []
    now = datetime.now(timezone.utc)

    for vdef in _SIMULATED_VESSEL_DEFS:
        speed_min, speed_max = vdef["speed_range"]

        lat, lon = _drift_position(
            vdef["base_lat"],
            vdef["base_lon"],
            vdef["patrol_radius"],
            seed_salt=vdef["mmsi"],
        )

        # Skip vessels outside the requested bounding box
        if not _in_bbox(lat, lon, lat_min, lon_min, lat_max, lon_max):
            continue

        course = _drift_course(vdef["mmsi"])
        speed = _drift_speed(speed_min, speed_max, vdef["mmsi"])

        vessels.append(
            Vessel(
                mmsi=vdef["mmsi"],
                name=vdef["name"],
                lat=round(lat, 5),
                lon=round(lon, 5),
                speed=speed,
                course=round(course, 1),
                vessel_type=vdef["vessel_type"],
                flag=vdef["flag"],
                destination=vdef["destination"],
                last_update=now,
            )
        )

    return vessels


# ---------------------------------------------------------------------------
# AISHub API integration
# ---------------------------------------------------------------------------


async def _fetch_aishub_vessels(
    lat_min: float,
    lon_min: float,
    lat_max: float,
    lon_max: float,
) -> list[Vessel]:
    """
    Fetch vessel data from the AISHub free API.

    AISHub requires a registered username (free). If no username is
    configured the call is skipped silently.

    Returns a list of Vessel models filtered to vessels of interest
    (military, tanker, cargo) near strategic waterways.
    """
    if not AISHUB_USERNAME:
        logger.debug("AISHub username not configured; skipping live AIS fetch")
        return []

    params = {
        "username": AISHUB_USERNAME,
        "format": "1",           # JSON
        "output": "json",
        "compress": "0",
        "latmin": str(lat_min),
        "latmax": str(lat_max),
        "lonmin": str(lon_min),
        "lonmax": str(lon_max),
    }

    vessels: list[Vessel] = []
    now = datetime.now(timezone.utc)

    try:
        async with httpx.AsyncClient(timeout=settings.HTTP_TIMEOUT) as client:
            response = await client.get(AISHUB_API_URL, params=params)
            response.raise_for_status()
            data = response.json()

        # AISHub returns a two-element list: [metadata, [vessel_records]]
        if not isinstance(data, list) or len(data) < 2:
            logger.warning("AISHub returned unexpected data structure")
            return []

        records = data[1] if isinstance(data[1], list) else []

        for rec in records:
            try:
                mmsi = str(rec.get("MMSI", ""))
                if not mmsi:
                    continue

                lat = float(rec.get("LATITUDE", 0))
                lon = float(rec.get("LONGITUDE", 0))
                if lat == 0 and lon == 0:
                    continue

                ais_type = int(rec.get("TYPE", 0))
                vessel_type = _classify_ais_type(ais_type)

                # Filter: only keep vessels of interest
                if not _is_vessel_of_interest(vessel_type):
                    continue

                # Filter: only keep vessels near strategic waterways
                zone = _near_strategic_zone(lat, lon)
                if zone is None:
                    continue

                speed_raw = rec.get("SOG")
                course_raw = rec.get("COG")

                vessels.append(
                    Vessel(
                        mmsi=mmsi,
                        name=str(rec.get("NAME", "")).strip(),
                        lat=round(lat, 5),
                        lon=round(lon, 5),
                        speed=round(float(speed_raw) / 10.0, 1) if speed_raw is not None else None,
                        course=round(float(course_raw) / 10.0, 1) if course_raw is not None else None,
                        vessel_type=vessel_type,
                        flag=str(rec.get("FLAG", "")).strip(),
                        destination=str(rec.get("DEST", "")).strip(),
                        last_update=now,
                    )
                )
            except (ValueError, TypeError, KeyError) as exc:
                logger.debug("Skipping malformed AISHub record: %s", exc)
                continue

        logger.info(
            "AISHub returned %d vessels of interest from %d total records",
            len(vessels),
            len(records),
        )

    except httpx.HTTPStatusError as exc:
        logger.error("AISHub HTTP error %s: %s", exc.response.status_code, exc)
    except httpx.RequestError as exc:
        logger.error("AISHub request error: %s", exc)
    except Exception as exc:
        logger.error("AISHub unexpected error: %s", exc)

    return vessels


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


async def get_vessels(
    bbox: Optional[tuple[float, float, float, float]] = None,
) -> list[Vessel]:
    """
    Fetch vessel positions in the Middle East region.

    Strategy:
      1. Try AISHub live API (if configured).
      2. Merge with simulated vessels so the map always has data.
      3. Deduplicate by MMSI (live data takes priority over simulated).
      4. Cache the result for 30 seconds.

    Args:
        bbox: Optional (lat_min, lon_min, lat_max, lon_max) bounding box.
              Defaults to the configured Middle East region.

    Returns:
        List of Vessel models with current positions.
    """
    if bbox is None:
        bbox = (
            settings.ME_LAT_MIN,
            settings.ME_LON_MIN,
            settings.ME_LAT_MAX,
            settings.ME_LON_MAX,
        )

    cache_key = f"vessels_{bbox}"
    if cache_key in _vessel_cache:
        logger.debug("Returning cached vessel data for bbox %s", bbox)
        return _vessel_cache[cache_key]

    lat_min, lon_min, lat_max, lon_max = bbox

    # Tier 1 - live AIS data
    live_vessels = await _fetch_aishub_vessels(lat_min, lon_min, lat_max, lon_max)

    # Tier 2 - simulated fallback (always generated; merged in)
    simulated_vessels = _generate_simulated_vessels(lat_min, lon_min, lat_max, lon_max)

    # Merge: live vessels take priority (keyed by MMSI)
    vessel_map: dict[str, Vessel] = {}
    for v in simulated_vessels:
        vessel_map[v.mmsi] = v
    for v in live_vessels:
        vessel_map[v.mmsi] = v  # overwrites simulated if same MMSI

    all_vessels = list(vessel_map.values())

    _vessel_cache[cache_key] = all_vessels
    logger.info(
        "Vessel data ready: %d live, %d simulated, %d total (after dedup)",
        len(live_vessels),
        len(simulated_vessels),
        len(all_vessels),
    )

    return all_vessels


async def get_military_vessels(
    bbox: Optional[tuple[float, float, float, float]] = None,
) -> list[Vessel]:
    """
    Fetch only military vessels in the region.

    Args:
        bbox: Optional bounding box. Defaults to Middle East region.

    Returns:
        List of Vessel models where vessel_type == "military".
    """
    cache_key = f"military_vessels_{bbox}"
    if cache_key in _vessel_cache:
        return _vessel_cache[cache_key]

    all_vessels = await get_vessels(bbox)
    military = [v for v in all_vessels if v.vessel_type == "military"]

    _vessel_cache[cache_key] = military
    logger.info(
        "Filtered %d military vessels from %d total",
        len(military),
        len(all_vessels),
    )
    return military


async def get_tanker_vessels(
    bbox: Optional[tuple[float, float, float, float]] = None,
) -> list[Vessel]:
    """
    Fetch only oil tanker vessels in the region.

    Useful for Strait of Hormuz traffic monitoring and energy
    supply chain awareness.

    Args:
        bbox: Optional bounding box. Defaults to Middle East region.

    Returns:
        List of Vessel models where vessel_type == "tanker".
    """
    cache_key = f"tanker_vessels_{bbox}"
    if cache_key in _vessel_cache:
        return _vessel_cache[cache_key]

    all_vessels = await get_vessels(bbox)
    tankers = [v for v in all_vessels if v.vessel_type == "tanker"]

    _vessel_cache[cache_key] = tankers
    logger.info(
        "Filtered %d tanker vessels from %d total",
        len(tankers),
        len(all_vessels),
    )
    return tankers


async def get_vessels_near_zone(zone_name: str) -> list[Vessel]:
    """
    Fetch vessels near a specific strategic zone.

    Args:
        zone_name: Key from STRATEGIC_ZONES (e.g. "strait_of_hormuz",
                   "suez_canal", "bab_el_mandeb").

    Returns:
        List of Vessel models within the zone radius.

    Raises:
        ValueError: If zone_name is not a recognized strategic zone.
    """
    if zone_name not in STRATEGIC_ZONES:
        raise ValueError(
            f"Unknown zone '{zone_name}'. "
            f"Valid zones: {', '.join(sorted(STRATEGIC_ZONES.keys()))}"
        )

    center_lat, center_lon, radius = STRATEGIC_ZONES[zone_name]
    all_vessels = await get_vessels()

    nearby: list[Vessel] = []
    for v in all_vessels:
        dlat = v.lat - center_lat
        dlon = v.lon - center_lon
        if math.sqrt(dlat * dlat + dlon * dlon) <= radius:
            nearby.append(v)

    logger.info(
        "Found %d vessels near %s (radius %.1f deg)",
        len(nearby),
        zone_name,
        radius,
    )
    return nearby
