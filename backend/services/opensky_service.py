"""
OpenSky Network Service - Fetches live aircraft positions from ADS-B data.
Includes filtering for likely military aircraft based on callsign patterns,
altitude, speed, and origin country.
"""

import logging
from typing import Optional

import httpx
from cachetools import TTLCache

from config import settings
from models import Aircraft

logger = logging.getLogger(__name__)

_aircraft_cache: TTLCache = TTLCache(maxsize=10, ttl=settings.CACHE_TTL_AIRCRAFT)

# Military callsign prefixes and patterns
MILITARY_CALLSIGN_PREFIXES = {
    # US Military
    "RCH", "REACH",  # US Air Mobility Command
    "DUKE",  # US Army
    "EVAC",  # US Aeromedical Evacuation
    "GOLD",  # US VIP
    "IRON",  # US Air Force
    "JAKE",  # US Marine Corps
    "KING",  # US Air Force Rescue
    "METAL",  # US Military
    "NIGHT",  # US Special Operations
    "OMEGA",  # US Navy Tanker
    "PACK",  # US Air Force
    "RAZOR",  # US Military
    "SAM",  # Special Air Mission (VIP)
    "SPAR",  # US Government
    "STEEL",  # US Military
    "TOPCAT",  # US Navy
    "VADER",  # US Air Force
    "WOLF",  # US Special Operations
    # NATO/Allied
    "NATO",  # NATO aircraft
    "ASCOT",  # RAF
    "TARTAN",  # RAF
    "RAFR",  # RAF Rescue
    "GAF",  # German Air Force
    "IAM",  # Italian Air Force
    "FAF",  # French Air Force
    "BAF",  # Belgian Air Force
    "HAF",  # Hellenic Air Force
    "TAF",  # Turkish Air Force
    "TUAF",  # Turkish Air Force
    "THY",  # (excluded - Turkish Airlines commercial)
    "RFR",  # French Air Force
    "CNV",  # US Navy
    # Regional/ME Military
    "UAE",  # UAE Air Force
    "RSAF",  # Royal Saudi Air Force
    "QAF",  # Qatar Air Force
    "KAF",  # Kuwait Air Force
    "BAH",  # Bahrain Air Force
    "OMAN",  # Oman Air Force
    "IRGC",  # Iran Revolutionary Guard
    "IRI",  # Islamic Republic of Iran
    "IAF",  # Israeli Air Force / Indian Air Force
    "EGY",  # Egyptian Air Force
    "JOR",  # Jordanian Air Force
    "PAF",  # Pakistan Air Force
    "RJF",  # Royal Jordanian Air Force
}

# Countries known for military flights in the Middle East region
MILITARY_INTEREST_COUNTRIES = {
    "United States", "Russia", "Israel", "Iran", "Turkey",
    "Saudi Arabia", "United Arab Emirates", "France", "United Kingdom",
    "Qatar", "Bahrain", "Kuwait", "Egypt", "Jordan", "Pakistan",
    "India", "Germany", "Italy",
}


async def get_aircraft(
    bbox: Optional[tuple[float, float, float, float]] = None
) -> list[Aircraft]:
    """
    Fetch live aircraft positions from OpenSky Network.

    Args:
        bbox: Optional (lamin, lomin, lamax, lomax) bounding box.
              Defaults to Middle East region.

    Returns:
        List of Aircraft models with current positions.
    """
    if bbox is None:
        bbox = (
            settings.ME_LAT_MIN,
            settings.ME_LON_MIN,
            settings.ME_LAT_MAX,
            settings.ME_LON_MAX,
        )

    cache_key = f"aircraft_{bbox}"
    if cache_key in _aircraft_cache:
        logger.debug("Returning cached aircraft data for bbox %s", bbox)
        return _aircraft_cache[cache_key]

    lamin, lomin, lamax, lomax = bbox
    params = {
        "lamin": str(lamin),
        "lomin": str(lomin),
        "lamax": str(lamax),
        "lomax": str(lomax),
    }

    aircraft_list: list[Aircraft] = []

    try:
        async with httpx.AsyncClient(timeout=settings.HTTP_TIMEOUT) as client:
            response = await client.get(settings.OPENSKY_API, params=params)
            response.raise_for_status()
            data = response.json()

            states = data.get("states", [])
            if states is None:
                states = []

            for state in states:
                # OpenSky state vector indices:
                # 0: icao24, 1: callsign, 2: origin_country, 3: time_position,
                # 4: last_contact, 5: longitude, 6: latitude, 7: baro_altitude,
                # 8: on_ground, 9: velocity, 10: true_track, 11: vertical_rate,
                # 12: sensors, 13: geo_altitude, 14: squawk, 15: spi, 16: position_source
                if len(state) < 17:
                    continue

                icao24 = state[0] or ""
                callsign = (state[1] or "").strip()
                origin_country = state[2] or ""
                lon = state[5]
                lat = state[6]
                baro_alt = state[7]
                on_ground = bool(state[8])
                velocity = state[9]
                heading = state[10]
                geo_alt = state[13]
                squawk = state[14]
                last_contact = state[4]

                # Skip aircraft without position data
                if lat is None or lon is None:
                    continue

                aircraft_list.append(Aircraft(
                    icao24=icao24,
                    callsign=callsign,
                    lat=float(lat),
                    lon=float(lon),
                    altitude=float(baro_alt) if baro_alt is not None else None,
                    velocity=float(velocity) if velocity is not None else None,
                    heading=float(heading) if heading is not None else None,
                    on_ground=on_ground,
                    origin_country=origin_country,
                    baro_altitude=float(baro_alt) if baro_alt is not None else None,
                    geo_altitude=float(geo_alt) if geo_alt is not None else None,
                    squawk=squawk,
                    last_contact=int(last_contact) if last_contact is not None else None,
                ))

        _aircraft_cache[cache_key] = aircraft_list
        logger.info("Fetched %d aircraft from OpenSky", len(aircraft_list))

    except httpx.HTTPStatusError as e:
        logger.error("OpenSky API HTTP error: %s", e.response.status_code)
        # Return cached data if available from any previous call
        for key in list(_aircraft_cache.keys()):
            if key.startswith("aircraft_"):
                return _aircraft_cache[key]
    except httpx.RequestError as e:
        logger.error("OpenSky API request error: %s", str(e))
    except Exception as e:
        logger.error("OpenSky API unexpected error: %s", str(e))

    return aircraft_list


async def get_military_aircraft() -> list[Aircraft]:
    """
    Fetch aircraft and filter for likely military flights.

    Filtering criteria:
    - Callsign matches known military prefixes
    - No callsign (often military/government)
    - Origin country is a military interest nation
    - Military squawk codes (7600, 7700, etc.)
    - High altitude (>12000m) with no callsign could be military
    """
    cache_key = "military_aircraft"
    if cache_key in _aircraft_cache:
        return _aircraft_cache[cache_key]

    all_aircraft = await get_aircraft()
    military: list[Aircraft] = []

    for ac in all_aircraft:
        if _is_likely_military(ac):
            military.append(ac)

    _aircraft_cache[cache_key] = military
    logger.info(
        "Filtered %d military aircraft from %d total",
        len(military), len(all_aircraft)
    )
    return military


def _is_likely_military(ac: Aircraft) -> bool:
    """
    Determine if an aircraft is likely military based on multiple signals.
    """
    callsign_upper = ac.callsign.upper().strip()

    # Check callsign prefixes
    for prefix in MILITARY_CALLSIGN_PREFIXES:
        if callsign_upper.startswith(prefix):
            return True

    # Check for no callsign from military interest countries
    if not callsign_upper and ac.origin_country in MILITARY_INTEREST_COUNTRIES:
        # Additional heuristic: must be airborne and have reasonable altitude
        if not ac.on_ground and ac.altitude is not None and ac.altitude > 1000:
            return True

    # Check for specific squawk codes
    if ac.squawk in ("7700", "7600", "7500"):
        return True

    # Military tankers/AWACS often fly high, slow patterns
    if (ac.origin_country in MILITARY_INTEREST_COUNTRIES and
            ac.altitude is not None and ac.altitude > 8000 and
            ac.velocity is not None and ac.velocity < 200):
        # Possible refueling/surveillance pattern
        if not callsign_upper or not any(c.isdigit() for c in callsign_upper[:3]):
            return True

    # Check for origin countries that primarily operate military flights in the region
    if ac.origin_country in ("Israel", "Iran") and not ac.on_ground:
        # Many Israeli/Iranian flights in this airspace are military
        if not callsign_upper.startswith(("ELY", "EL AL", "IRA", "IRM", "IRC")):
            return True

    return False
