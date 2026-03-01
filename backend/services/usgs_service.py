"""
USGS Earthquake Service - Fetches recent seismic events from the
United States Geological Survey earthquake feed.
"""

import logging
from datetime import datetime, timezone

import httpx
from cachetools import TTLCache

from config import settings
from models import GeoEvent

logger = logging.getLogger(__name__)

_earthquake_cache: TTLCache = TTLCache(maxsize=1, ttl=settings.CACHE_TTL_EARTHQUAKES)


def _magnitude_to_severity(mag: float) -> str:
    """Convert earthquake magnitude to severity level."""
    if mag >= 7.0:
        return "critical"
    if mag >= 5.5:
        return "high"
    if mag >= 4.0:
        return "medium"
    return "low"


async def get_earthquakes() -> list[GeoEvent]:
    """
    Fetch recent M2.5+ earthquakes from USGS GeoJSON feed.
    Filters to Middle East bounding box.

    Returns:
        List of GeoEvent models for seismic activity.
    """
    cache_key = "earthquakes"
    if cache_key in _earthquake_cache:
        logger.debug("Returning cached earthquake data")
        return _earthquake_cache[cache_key]

    events: list[GeoEvent] = []

    try:
        async with httpx.AsyncClient(timeout=settings.HTTP_TIMEOUT) as client:
            response = await client.get(settings.USGS_EARTHQUAKE_API)
            response.raise_for_status()
            data = response.json()

            features = data.get("features", [])
            for feature in features:
                props = feature.get("properties", {})
                geometry = feature.get("geometry", {})
                coords = geometry.get("coordinates", [])

                if len(coords) < 3:
                    continue

                lon = coords[0]
                lat = coords[1]
                depth = coords[2]

                # Filter to broader Middle East / Central Asia region
                # Using slightly expanded bbox to catch nearby events
                if not (settings.ME_LAT_MIN - 5 <= lat <= settings.ME_LAT_MAX + 5 and
                        settings.ME_LON_MIN - 10 <= lon <= settings.ME_LON_MAX + 10):
                    continue

                mag = props.get("mag", 0)
                if mag is None:
                    mag = 0
                place = props.get("place", "Unknown location")
                time_ms = props.get("time", 0)
                url = props.get("url", "")
                felt = props.get("felt", 0)
                tsunami = props.get("tsunami", 0)
                alert = props.get("alert", None)
                sig = props.get("sig", 0)
                event_type = props.get("type", "earthquake")
                title = props.get("title", f"M{mag} - {place}")
                event_id = feature.get("id", f"usgs-{time_ms}")

                timestamp = datetime.fromtimestamp(
                    time_ms / 1000, tz=timezone.utc
                ) if time_ms else datetime.now(timezone.utc)

                # Use USGS alert level if available, otherwise derive from magnitude
                if alert:
                    severity_map = {"green": "low", "yellow": "medium", "orange": "high", "red": "critical"}
                    severity = severity_map.get(alert, _magnitude_to_severity(mag))
                else:
                    severity = _magnitude_to_severity(mag)

                description_parts = [
                    f"Magnitude: {mag}",
                    f"Depth: {depth:.1f} km",
                    f"Location: {place}",
                ]
                if felt and felt > 0:
                    description_parts.append(f"Felt reports: {felt}")
                if tsunami:
                    description_parts.append("TSUNAMI WARNING ISSUED")
                if alert:
                    description_parts.append(f"USGS Alert: {alert.upper()}")

                events.append(GeoEvent(
                    id=f"usgs-{event_id}",
                    type="earthquake",
                    lat=lat,
                    lon=lon,
                    title=title,
                    description=" | ".join(description_parts),
                    severity=severity,
                    source="USGS",
                    timestamp=timestamp,
                    metadata={
                        "magnitude": mag,
                        "depth_km": depth,
                        "place": place,
                        "felt": felt or 0,
                        "tsunami": tsunami,
                        "alert": alert,
                        "significance": sig,
                        "type": event_type,
                        "url": f"https://earthquake.usgs.gov{url}" if url and not url.startswith("http") else url,
                    },
                ))

        # Sort by magnitude descending
        events.sort(key=lambda e: e.metadata.get("magnitude", 0), reverse=True)

        _earthquake_cache[cache_key] = events
        logger.info("Fetched %d earthquakes in ME region from USGS", len(events))

    except httpx.HTTPStatusError as e:
        logger.error("USGS API HTTP error: %s", e.response.status_code)
    except httpx.RequestError as e:
        logger.error("USGS API request error: %s", str(e))
    except Exception as e:
        logger.error("USGS API unexpected error: %s", str(e))

    return events
