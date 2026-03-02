"""
GDELT Service - Fetches conflict events, attack reports, and missile events
from the GDELT Project API v2 (DOC and GEO endpoints).
"""

import hashlib
import logging
import re
from datetime import datetime, timezone
from typing import Optional

import httpx
from cachetools import TTLCache

from config import settings
from models import GeoEvent, MissileEvent

logger = logging.getLogger(__name__)

_conflict_cache: TTLCache = TTLCache(maxsize=1, ttl=settings.CACHE_TTL_CONFLICTS)
_missile_cache: TTLCache = TTLCache(maxsize=1, ttl=settings.CACHE_TTL_MISSILES)
_geo_cache: TTLCache = TTLCache(maxsize=1, ttl=settings.CACHE_TTL_CONFLICTS)

MISSILE_KEYWORDS = re.compile(
    r"\b(missile|rocket|projectile|ballistic|cruise missile|drone strike|"
    r"intercepted|iron dome|patriot|s-300|s-400|hypersonic|icbm|scud|"
    r"houthi.*attack|shahab|fateh|qiam|zolfaghar|emad)\b",
    re.IGNORECASE,
)

CONFLICT_KEYWORDS = (
    "conflict OR attack OR missile OR airstrike OR bombing OR "
    "military strike OR shelling OR drone strike OR rocket"
)


def _generate_id(text: str) -> str:
    """Generate a deterministic short ID from text content."""
    return hashlib.md5(text.encode("utf-8", errors="replace")).hexdigest()[:12]


def _severity_from_tone(tone: Optional[float]) -> str:
    """Derive severity from GDELT tone score (negative = more severe)."""
    if tone is None:
        return "medium"
    if tone < -8:
        return "critical"
    if tone < -5:
        return "high"
    if tone < -2:
        return "medium"
    return "low"


def _parse_gdelt_date(date_str: str) -> datetime:
    """Parse GDELT date string to datetime."""
    try:
        if len(date_str) == 14:
            return datetime.strptime(date_str, "%Y%m%d%H%M%S").replace(tzinfo=timezone.utc)
        elif len(date_str) == 8:
            return datetime.strptime(date_str, "%Y%m%d").replace(tzinfo=timezone.utc)
        else:
            return datetime.fromisoformat(date_str.replace("Z", "+00:00"))
    except (ValueError, AttributeError):
        return datetime.now(timezone.utc)


async def get_conflicts() -> list[GeoEvent]:
    """
    Fetch real conflict events from Google News RSS + GDELT.
    Returns parsed GeoEvent models with location data.
    """
    cache_key = "conflicts"
    if cache_key in _conflict_cache:
        logger.debug("Returning cached conflict data")
        return _conflict_cache[cache_key]

    events: list[GeoEvent] = []

    # PRIMARY: Get real events from Google News RSS
    try:
        from services.google_news_service import fetch_conflict_news
        news_articles = await fetch_conflict_news()

        for article in news_articles:
            lat = article.get("lat")
            lon = article.get("lon")
            if lat is None or lon is None:
                continue

            title = article.get("title", "")
            source = article.get("source", "News")
            url = article.get("url", "")
            pub_date = article.get("published_at", "")
            location_name = article.get("location_name", "")

            try:
                timestamp = datetime.fromisoformat(pub_date.replace("Z", "+00:00")) if pub_date else datetime.now(timezone.utc)
            except (ValueError, AttributeError):
                timestamp = datetime.now(timezone.utc)

            event_id = article.get("id", _generate_id(title))

            # Severity from event type
            event_type = article.get("event_type", "military")
            if event_type in ("missile", "airstrike"):
                severity = "critical"
            elif event_type in ("drone", "rocket", "interception"):
                severity = "high"
            elif event_type in ("artillery", "naval"):
                severity = "medium"
            else:
                severity = "low"

            events.append(GeoEvent(
                id=f"live-{event_id}",
                type="conflict",
                lat=lat,
                lon=lon,
                title=title,
                description=f"Source: {source} | {location_name}",
                severity=severity,
                source=f"News/{source}",
                timestamp=timestamp,
                metadata={"url": url, "location": location_name, "event_type": event_type, "live": True},
            ))

    except Exception as e:
        logger.error("Google News conflict extraction failed: %s", e)

    # SECONDARY: Try GDELT APIs if available
    try:
        doc_events = await _fetch_gdelt_doc_events()
        events.extend(doc_events)
    except Exception:
        pass

    try:
        geo_events = await _fetch_gdelt_geo_events()
        events.extend(geo_events)
    except Exception:
        pass

    # Deduplicate by ID
    seen_ids: set[str] = set()
    unique_events: list[GeoEvent] = []
    for event in events:
        if event.id not in seen_ids:
            seen_ids.add(event.id)
            unique_events.append(event)

    _conflict_cache[cache_key] = unique_events
    logger.info("Fetched %d conflict events (News + GDELT)", len(unique_events))
    return unique_events


async def _fetch_gdelt_doc_events() -> list[GeoEvent]:
    """Fetch from GDELT DOC API and extract geolocated conflict events."""
    events: list[GeoEvent] = []
    params = {
        "query": f"{CONFLICT_KEYWORDS} (Iraq OR Syria OR Israel OR Iran OR Yemen OR Lebanon OR Gaza OR Palestine)",
        "mode": "artlist",
        "maxrecords": "100",
        "format": "json",
        "sort": "datedesc",
    }

    try:
        async with httpx.AsyncClient(timeout=settings.HTTP_TIMEOUT) as client:
            response = await client.get(settings.GDELT_DOC_API, params=params)
            response.raise_for_status()
            data = response.json()

            articles = data.get("articles", [])
            for article in articles:
                title = article.get("title", "")
                url = article.get("url", "")
                seendate = article.get("seendate", "")
                source = article.get("domain", "")
                language = article.get("language", "")
                socialimage = article.get("socialimage", "")
                tone = article.get("tone", None)

                # GDELT DOC API articles may not always have direct lat/lon.
                # We attempt to extract from the URL/source or use GDELT GEO for coords.
                # For DOC results, set approximate coords from context if available.
                lat = article.get("latitude", None)
                lon = article.get("longitude", None)

                # If no coordinates in article, try to infer from country mention
                if lat is None or lon is None:
                    coords = _infer_coordinates_from_text(title)
                    if coords:
                        lat, lon = coords
                    else:
                        continue  # Skip events without coordinates

                tone_val = None
                if tone is not None:
                    try:
                        if isinstance(tone, str):
                            tone_val = float(tone.split(",")[0]) if "," in tone else float(tone)
                        else:
                            tone_val = float(tone)
                    except (ValueError, TypeError):
                        tone_val = None

                event_id = _generate_id(f"{url}{seendate}")
                timestamp = _parse_gdelt_date(seendate) if seendate else datetime.now(timezone.utc)

                events.append(GeoEvent(
                    id=f"gdelt-doc-{event_id}",
                    type="conflict",
                    lat=lat,
                    lon=lon,
                    title=title,
                    description=f"Source: {source}",
                    severity=_severity_from_tone(tone_val),
                    source=f"GDELT/{source}",
                    timestamp=timestamp,
                    metadata={
                        "url": url,
                        "language": language,
                        "image": socialimage,
                        "tone": tone_val,
                    },
                ))

    except httpx.HTTPStatusError as e:
        logger.error("GDELT DOC API HTTP error: %s", e.response.status_code)
    except httpx.RequestError as e:
        logger.error("GDELT DOC API request error: %s", str(e))
    except Exception as e:
        logger.error("GDELT DOC API unexpected error: %s", str(e))

    return events


async def _fetch_gdelt_geo_events() -> list[GeoEvent]:
    """Fetch from GDELT GEO API for geolocated conflict events."""
    cache_key = "geo_events"
    if cache_key in _geo_cache:
        return _geo_cache[cache_key]

    events: list[GeoEvent] = []
    params = {
        "query": "conflict OR attack OR military OR bombing OR airstrike",
        "format": "GeoJSON",
        "timespan": "7d",
    }

    try:
        async with httpx.AsyncClient(timeout=settings.HTTP_TIMEOUT) as client:
            response = await client.get(settings.GDELT_GEO_API, params=params)
            response.raise_for_status()
            data = response.json()

            features = data.get("features", [])
            for feature in features:
                props = feature.get("properties", {})
                geometry = feature.get("geometry", {})
                coords = geometry.get("coordinates", [])

                if len(coords) < 2:
                    continue

                lon, lat = coords[0], coords[1]

                # Filter to Middle East bounding box
                if not (settings.ME_LAT_MIN <= lat <= settings.ME_LAT_MAX and
                        settings.ME_LON_MIN <= lon <= settings.ME_LON_MAX):
                    continue

                name = props.get("name", "Unknown Event")
                url = props.get("url", "")
                html = props.get("html", "")
                count = props.get("count", 0)
                shareimage = props.get("shareimage", "")

                event_id = _generate_id(f"{name}{lat}{lon}")

                # Determine severity from event count
                if count > 50:
                    severity = "critical"
                elif count > 20:
                    severity = "high"
                elif count > 5:
                    severity = "medium"
                else:
                    severity = "low"

                events.append(GeoEvent(
                    id=f"gdelt-geo-{event_id}",
                    type="conflict",
                    lat=lat,
                    lon=lon,
                    title=name,
                    description=f"Reported in {count} articles",
                    severity=severity,
                    source="GDELT GEO",
                    timestamp=datetime.now(timezone.utc),
                    metadata={
                        "url": url,
                        "html": html[:500] if html else "",
                        "count": count,
                        "image": shareimage,
                    },
                ))

            _geo_cache[cache_key] = events

    except httpx.HTTPStatusError as e:
        logger.error("GDELT GEO API HTTP error: %s", e.response.status_code)
    except httpx.RequestError as e:
        logger.error("GDELT GEO API request error: %s", str(e))
    except Exception as e:
        logger.error("GDELT GEO API unexpected error: %s", str(e))

    return events


async def get_missile_events() -> list[MissileEvent]:
    """
    Extract real missile/drone/strike events from Google News RSS + GDELT.
    Uses live news articles to detect current events and geolocate them on the map.
    """
    cache_key = "missiles"
    if cache_key in _missile_cache:
        logger.debug("Returning cached missile data")
        return _missile_cache[cache_key]

    missile_events: list[MissileEvent] = []

    # PRIMARY: Get real events from Google News RSS
    try:
        from services.google_news_service import fetch_conflict_news
        news_articles = await fetch_conflict_news()

        for article in news_articles:
            title = article.get("title", "")
            event_type = article.get("event_type", "")

            # Only include missile/drone/rocket/airstrike/interception events
            if event_type not in ("missile", "drone", "rocket", "airstrike", "interception", "artillery"):
                continue

            # Must have location to plot on map
            lat = article.get("lat")
            lon = article.get("lon")
            if lat is None or lon is None:
                continue

            event_id = article.get("id", _generate_id(title))
            source = article.get("source", "News")
            url = article.get("url", "")
            pub_date = article.get("published_at", "")
            status = article.get("status", "reported")
            location_name = article.get("location_name", "")

            try:
                timestamp = datetime.fromisoformat(pub_date.replace("Z", "+00:00")) if pub_date else datetime.now(timezone.utc)
            except (ValueError, AttributeError):
                timestamp = datetime.now(timezone.utc)

            missile_type = _classify_missile_type(title)

            missile_events.append(MissileEvent(
                id=f"live-{event_id}",
                launch_lat=lat,
                launch_lon=lon,
                target_lat=None,
                target_lon=None,
                missile_type=missile_type,
                status=status,
                source=f"News/{source}",
                title=title,
                description=f"Source: {source} | Location: {location_name}",
                timestamp=timestamp,
                metadata={"url": url, "location": location_name, "live": True},
            ))

    except Exception as e:
        logger.error("Google News missile extraction failed: %s", e)

    # SECONDARY: Try GDELT if available
    try:
        gdelt_missiles = await _fetch_gdelt_missiles()
        existing_titles = {m.title.lower()[:60] for m in missile_events}
        for gm in gdelt_missiles:
            if gm.title.lower()[:60] not in existing_titles:
                missile_events.append(gm)
    except Exception as e:
        logger.debug("GDELT missile fetch unavailable: %s", e)

    # Deduplicate by ID
    seen_ids: set[str] = set()
    unique: list[MissileEvent] = []
    for m in missile_events:
        if m.id not in seen_ids:
            seen_ids.add(m.id)
            unique.append(m)
    missile_events = unique

    _missile_cache[cache_key] = missile_events
    logger.info("Extracted %d real missile/strike events from live news", len(missile_events))
    return missile_events


async def _fetch_gdelt_missiles() -> list[MissileEvent]:
    """Try GDELT DOC API for missile events (may fail on cloud hosting)."""
    events: list[MissileEvent] = []
    queries = ["missile attack", "drone strike", "rocket launch intercept"]

    for query_text in queries:
        try:
            params = {
                "query": query_text,
                "mode": "artlist",
                "maxrecords": "20",
                "format": "json",
                "sort": "datedesc",
            }
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(settings.GDELT_DOC_API, params=params)
                response.raise_for_status()
                data = response.json()

                for article in data.get("articles", []):
                    title = article.get("title", "")
                    if not MISSILE_KEYWORDS.search(title):
                        continue
                    coords = _infer_coordinates_from_text(title)
                    if not coords:
                        continue
                    lat, lon = coords
                    url = article.get("url", "")
                    seendate = article.get("seendate", "")
                    source = article.get("domain", "")
                    event_id = _generate_id(f"gdelt-m-{url}{seendate}")
                    timestamp = _parse_gdelt_date(seendate) if seendate else datetime.now(timezone.utc)

                    events.append(MissileEvent(
                        id=f"gdelt-{event_id}",
                        launch_lat=lat, launch_lon=lon,
                        target_lat=None, target_lon=None,
                        missile_type=_classify_missile_type(title),
                        status=_classify_missile_status(title),
                        source=f"GDELT/{source}", title=title,
                        description=f"Source: {source}",
                        timestamp=timestamp,
                        metadata={"url": url},
                    ))
        except Exception:
            pass

    return events


def _get_curated_missile_events() -> list[MissileEvent]:
    """
    Generate curated missile/strike events based on known active conflicts.
    These represent the types of events actively occurring in the region.
    """
    now = datetime.now(timezone.utc)
    from datetime import timedelta

    events = [
        MissileEvent(
            id=_generate_id(f"curated-houthi-redsea-{now.strftime('%Y%m%d')}"),
            launch_lat=15.4, launch_lon=44.2,
            target_lat=13.5, target_lon=42.5,
            missile_type="ballistic_missile",
            status="reported",
            source="OSINT/CENTCOM",
            title="Houthi anti-ship ballistic missile targeting commercial vessel in Red Sea",
            description="Houthi forces launched ASBM toward commercial shipping near Bab el-Mandeb strait",
            timestamp=now - timedelta(hours=2),
            metadata={"region": "Red Sea", "threat_actor": "Ansar Allah (Houthis)"},
        ),
        MissileEvent(
            id=_generate_id(f"curated-houthi-drone-{now.strftime('%Y%m%d')}"),
            launch_lat=15.5, launch_lon=44.3,
            target_lat=20.5, target_lon=39.8,
            missile_type="drone",
            status="intercepted",
            source="OSINT/Coalition",
            title="Houthi drone swarm intercepted over Saudi airspace near Jizan",
            description="Coalition air defenses intercepted multiple Qasef-2K UAVs launched from Houthi-controlled territory",
            timestamp=now - timedelta(hours=5),
            metadata={"region": "Saudi Arabia", "threat_actor": "Ansar Allah (Houthis)"},
        ),
        MissileEvent(
            id=_generate_id(f"curated-hezbollah-rocket-{now.strftime('%Y%m%d')}"),
            launch_lat=33.4, launch_lon=35.4,
            target_lat=33.0, target_lon=35.2,
            missile_type="rocket",
            status="confirmed",
            source="OSINT/IDF",
            title="Hezbollah rocket barrage targeting northern Israel from southern Lebanon",
            description="Multiple 122mm Grad rockets launched from positions south of Litani River",
            timestamp=now - timedelta(hours=3),
            metadata={"region": "Lebanon-Israel border", "threat_actor": "Hezbollah"},
        ),
        MissileEvent(
            id=_generate_id(f"curated-idf-airstrike-{now.strftime('%Y%m%d')}"),
            launch_lat=32.1, launch_lon=34.8,
            target_lat=33.9, target_lon=35.6,
            missile_type="cruise_missile",
            status="confirmed",
            source="OSINT/IDF",
            title="IDF precision airstrike on Hezbollah weapons depot in Bekaa Valley",
            description="Israeli Air Force F-35I conducted precision strike using Delilah cruise missile",
            timestamp=now - timedelta(hours=4),
            metadata={"region": "Bekaa Valley, Lebanon", "threat_actor": "IDF"},
        ),
        MissileEvent(
            id=_generate_id(f"curated-gaza-rocket-{now.strftime('%Y%m%d')}"),
            launch_lat=31.4, launch_lon=34.4,
            target_lat=31.8, target_lon=34.6,
            missile_type="rocket",
            status="intercepted",
            source="OSINT/IDF",
            title="Rocket barrage from Gaza intercepted by Iron Dome over Ashkelon",
            description="Multiple Qassam rockets launched from Gaza Strip, Iron Dome activated",
            timestamp=now - timedelta(hours=6),
            metadata={"region": "Gaza-Israel", "threat_actor": "Palestinian factions"},
        ),
        MissileEvent(
            id=_generate_id(f"curated-iran-test-{now.strftime('%Y%m%d')}"),
            launch_lat=35.2, launch_lon=53.5,
            target_lat=30.0, target_lon=57.0,
            missile_type="ballistic_missile",
            status="reported",
            source="OSINT/Satellite",
            title="Iran IRGC ballistic missile test detected from Semnan launch facility",
            description="Satellite imagery confirms test launch of medium-range ballistic missile from Semnan",
            timestamp=now - timedelta(hours=12),
            metadata={"region": "Iran", "threat_actor": "IRGC"},
        ),
        MissileEvent(
            id=_generate_id(f"curated-syria-strike-{now.strftime('%Y%m%d')}"),
            launch_lat=32.0, launch_lon=34.9,
            target_lat=35.3, target_lon=40.1,
            missile_type="cruise_missile",
            status="confirmed",
            source="OSINT/SOHR",
            title="Coalition airstrike on Iranian militia position near Deir ez-Zor, Syria",
            description="US-led coalition struck Iranian-backed militia weapons cache along Iraq-Syria border",
            timestamp=now - timedelta(hours=8),
            metadata={"region": "Eastern Syria", "threat_actor": "Coalition"},
        ),
        MissileEvent(
            id=_generate_id(f"curated-yemen-coast-{now.strftime('%Y%m%d')}"),
            launch_lat=14.8, launch_lon=42.9,
            target_lat=12.8, target_lon=43.5,
            missile_type="missile",
            status="reported",
            source="OSINT/Maritime",
            title="Anti-ship missile launched from Hodeidah coast toward Gulf of Aden shipping",
            description="Houthi forces fired anti-ship cruise missile at commercial tanker near Aden",
            timestamp=now - timedelta(hours=10),
            metadata={"region": "Gulf of Aden", "threat_actor": "Ansar Allah (Houthis)"},
        ),
    ]

    return events


def _classify_missile_type(text: str) -> str:
    """Classify the type of missile/projectile from text."""
    text_lower = text.lower()
    if "ballistic" in text_lower:
        return "ballistic_missile"
    if "cruise missile" in text_lower:
        return "cruise_missile"
    if "drone" in text_lower or "uav" in text_lower:
        return "drone"
    if "rocket" in text_lower:
        return "rocket"
    if "projectile" in text_lower:
        return "projectile"
    if "hypersonic" in text_lower:
        return "hypersonic"
    return "missile"


def _classify_missile_status(text: str) -> str:
    """Classify missile event status from text."""
    text_lower = text.lower()
    if any(w in text_lower for w in ["intercept", "iron dome", "shot down", "destroyed", "neutralized"]):
        return "intercepted"
    if any(w in text_lower for w in ["confirmed", "struck", "hit", "killed", "casualties"]):
        return "confirmed"
    return "reported"


# Country/region to approximate coordinates mapping for Middle East
_LOCATION_COORDS: dict[str, tuple[float, float]] = {
    "iraq": (33.3, 44.4),
    "baghdad": (33.3, 44.4),
    "mosul": (36.3, 43.1),
    "basra": (30.5, 47.8),
    "erbil": (36.2, 44.0),
    "syria": (34.8, 38.9),
    "damascus": (33.5, 36.3),
    "aleppo": (36.2, 37.2),
    "idlib": (35.9, 36.6),
    "deir ez-zor": (35.3, 40.1),
    "raqqa": (35.9, 39.0),
    "homs": (34.7, 36.7),
    "iran": (32.4, 53.7),
    "tehran": (35.7, 51.4),
    "isfahan": (32.7, 51.7),
    "tabriz": (38.1, 46.3),
    "israel": (31.5, 34.8),
    "tel aviv": (32.1, 34.8),
    "jerusalem": (31.8, 35.2),
    "gaza": (31.4, 34.4),
    "gaza strip": (31.4, 34.4),
    "west bank": (31.9, 35.3),
    "haifa": (32.8, 35.0),
    "beersheba": (31.3, 34.8),
    "yemen": (15.6, 48.5),
    "sanaa": (15.4, 44.2),
    "aden": (12.8, 45.0),
    "hodeidah": (14.8, 42.9),
    "marib": (15.5, 45.3),
    "saudi arabia": (23.9, 45.1),
    "riyadh": (24.7, 46.7),
    "jeddah": (21.5, 39.2),
    "lebanon": (33.9, 35.5),
    "beirut": (33.9, 35.5),
    "turkey": (39.9, 32.9),
    "ankara": (39.9, 32.9),
    "istanbul": (41.0, 29.0),
    "egypt": (30.0, 31.2),
    "cairo": (30.0, 31.2),
    "sinai": (29.5, 33.8),
    "libya": (32.9, 13.2),
    "tripoli": (32.9, 13.2),
    "jordan": (31.9, 35.9),
    "amman": (31.9, 35.9),
    "afghanistan": (34.5, 69.2),
    "kabul": (34.5, 69.2),
    "kandahar": (31.6, 65.7),
    "pakistan": (30.4, 69.3),
    "islamabad": (33.7, 73.0),
    "uae": (24.5, 54.4),
    "abu dhabi": (24.5, 54.4),
    "dubai": (25.2, 55.3),
    "qatar": (25.3, 51.5),
    "doha": (25.3, 51.5),
    "bahrain": (26.0, 50.6),
    "kuwait": (29.4, 48.0),
    "oman": (23.6, 58.4),
    "muscat": (23.6, 58.4),
    "red sea": (20.0, 38.5),
    "strait of hormuz": (26.6, 56.3),
    "persian gulf": (27.0, 51.0),
    "arabian sea": (15.0, 60.0),
    "ukraine": (48.4, 31.2),
    "kyiv": (50.4, 30.5),
    "kharkiv": (49.9, 36.2),
    "donbas": (48.0, 38.0),
    "crimea": (45.3, 34.1),
    "sudan": (15.6, 32.5),
    "khartoum": (15.6, 32.5),
    "somalia": (5.2, 46.2),
    "mogadishu": (2.0, 45.3),
    "palestine": (31.9, 35.2),
    "rafah": (31.3, 34.2),
    "khan younis": (31.3, 34.3),
    "nablus": (32.2, 35.3),
    "jenin": (32.5, 35.3),
    "golan": (33.0, 35.8),
    "golan heights": (33.0, 35.8),
    "houthi": (15.4, 44.2),
    "hezbollah": (33.9, 35.5),
}


def _infer_coordinates_from_text(text: str) -> Optional[tuple[float, float]]:
    """Attempt to infer geographic coordinates from text by matching known locations."""
    text_lower = text.lower()
    # Try to match the most specific location first (cities before countries)
    # Sort by length descending so longer names match first
    sorted_locations = sorted(_LOCATION_COORDS.keys(), key=len, reverse=True)
    for location in sorted_locations:
        if location in text_lower:
            return _LOCATION_COORDS[location]
    return None
