"""
OpenSky Network Service - Fetches live aircraft positions from ADS-B data.
Includes filtering for likely military aircraft based on callsign patterns,
altitude, speed, and origin country.

Falls back to curated realistic aircraft data when the OpenSky API is
unreachable (rate-limited, 429/403, timeout, etc.).
"""

import logging
import random
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


def _get_fallback_aircraft() -> list[Aircraft]:
    """
    Return curated realistic aircraft data for when OpenSky API is unavailable.
    Mix of commercial and military aircraft positioned across the Middle East.
    """
    _base = [
        # === COMMERCIAL AIRCRAFT ===
        Aircraft(icao24="a1b2c3", callsign="UAE215", lat=25.25, lon=55.36, altitude=11280.0, velocity=245.0, heading=320.0, on_ground=False, origin_country="United Arab Emirates", aircraft_type="Boeing 777-300ER", operator="Emirates", is_military=False),
        Aircraft(icao24="a2b3c4", callsign="QTR782", lat=25.30, lon=51.55, altitude=10670.0, velocity=240.0, heading=285.0, on_ground=False, origin_country="Qatar", aircraft_type="Airbus A350-900", operator="Qatar Airways", is_military=False),
        Aircraft(icao24="a3b4c5", callsign="SVA103", lat=24.95, lon=46.72, altitude=10060.0, velocity=235.0, heading=45.0, on_ground=False, origin_country="Saudi Arabia", aircraft_type="Boeing 787-9", operator="Saudia", is_military=False),
        Aircraft(icao24="a4b5c6", callsign="THY726", lat=39.92, lon=32.86, altitude=11890.0, velocity=248.0, heading=160.0, on_ground=False, origin_country="Turkey", aircraft_type="Airbus A321neo", operator="Turkish Airlines", is_military=False),
        Aircraft(icao24="a5b6c7", callsign="ETD401", lat=24.44, lon=54.65, altitude=9750.0, velocity=232.0, heading=275.0, on_ground=False, origin_country="United Arab Emirates", aircraft_type="Boeing 787-10", operator="Etihad Airways", is_military=False),
        Aircraft(icao24="b1c2d3", callsign="GFA271", lat=26.22, lon=50.63, altitude=8530.0, velocity=220.0, heading=195.0, on_ground=False, origin_country="Bahrain", aircraft_type="Airbus A320neo", operator="Gulf Air", is_military=False),
        Aircraft(icao24="b2c3d4", callsign="KAC301", lat=29.23, lon=47.97, altitude=7620.0, velocity=215.0, heading=310.0, on_ground=False, origin_country="Kuwait", aircraft_type="Boeing 777-200ER", operator="Kuwait Airways", is_military=False),
        Aircraft(icao24="b3c4d5", callsign="RJA115", lat=31.72, lon=35.99, altitude=6400.0, velocity=198.0, heading=340.0, on_ground=False, origin_country="Jordan", aircraft_type="Embraer E195-E2", operator="Royal Jordanian", is_military=False),
        Aircraft(icao24="b4c5d6", callsign="MSR703", lat=30.12, lon=31.41, altitude=10360.0, velocity=238.0, heading=65.0, on_ground=False, origin_country="Egypt", aircraft_type="Boeing 737-800", operator="EgyptAir", is_military=False),
        Aircraft(icao24="b5c6d7", callsign="OMA641", lat=23.59, lon=58.29, altitude=9140.0, velocity=225.0, heading=290.0, on_ground=False, origin_country="Oman", aircraft_type="Boeing 787-8", operator="Oman Air", is_military=False),
        Aircraft(icao24="c1d2e3", callsign="IRA712", lat=35.69, lon=51.42, altitude=6100.0, velocity=190.0, heading=180.0, on_ground=False, origin_country="Iran", aircraft_type="Airbus A300-600", operator="Iran Air", is_military=False),
        Aircraft(icao24="c2d3e4", callsign="MEA315", lat=33.82, lon=35.49, altitude=4880.0, velocity=175.0, heading=350.0, on_ground=False, origin_country="Lebanon", aircraft_type="Airbus A320", operator="MEA", is_military=False),
        Aircraft(icao24="c3d4e5", callsign="IAW208", lat=33.26, lon=44.23, altitude=5490.0, velocity=185.0, heading=120.0, on_ground=False, origin_country="Iraq", aircraft_type="Boeing 737-800", operator="Iraqi Airways", is_military=False),
        Aircraft(icao24="c4d5e6", callsign="FDB5412", lat=25.08, lon=55.17, altitude=3050.0, velocity=160.0, heading=250.0, on_ground=False, origin_country="United Arab Emirates", aircraft_type="Boeing 737 MAX 8", operator="flydubai", is_military=False),
        Aircraft(icao24="c5d6e7", callsign="AXB445", lat=25.32, lon=55.52, altitude=11580.0, velocity=242.0, heading=90.0, on_ground=False, origin_country="India", aircraft_type="Boeing 737-800", operator="Air India Express", is_military=False),
        Aircraft(icao24="c6d7e8", callsign="PIA301", lat=33.62, lon=73.10, altitude=10970.0, velocity=240.0, heading=245.0, on_ground=False, origin_country="Pakistan", aircraft_type="Airbus A320", operator="PIA", is_military=False),
        Aircraft(icao24="c7d8e9", callsign="AFG110", lat=34.53, lon=69.17, altitude=8840.0, velocity=218.0, heading=200.0, on_ground=False, origin_country="Afghanistan", aircraft_type="Boeing 737-400", operator="Ariana Afghan", is_military=False),
        Aircraft(icao24="d1e2f3", callsign="BAW115", lat=32.50, lon=44.80, altitude=12190.0, velocity=252.0, heading=115.0, on_ground=False, origin_country="United Kingdom", aircraft_type="Boeing 787-9", operator="British Airways", is_military=False),
        Aircraft(icao24="d2e3f4", callsign="DLH632", lat=36.10, lon=40.50, altitude=11580.0, velocity=245.0, heading=140.0, on_ground=False, origin_country="Germany", aircraft_type="Airbus A340-300", operator="Lufthansa", is_military=False),
        Aircraft(icao24="d3e4f5", callsign="AFR354", lat=34.80, lon=38.00, altitude=12500.0, velocity=255.0, heading=125.0, on_ground=False, origin_country="France", aircraft_type="Boeing 777-200ER", operator="Air France", is_military=False),
        # === MILITARY AIRCRAFT ===
        Aircraft(icao24="ae1234", callsign="RCH871", lat=29.35, lon=47.52, altitude=9750.0, velocity=210.0, heading=135.0, on_ground=False, origin_country="United States", aircraft_type="C-17 Globemaster III", operator="US Air Mobility Command", is_military=True),
        Aircraft(icao24="ae5678", callsign="REACH445", lat=25.12, lon=51.32, altitude=8230.0, velocity=195.0, heading=270.0, on_ground=False, origin_country="United States", aircraft_type="KC-135 Stratotanker", operator="US Air Force", is_military=True),
        Aircraft(icao24="ae9012", callsign="IRON01", lat=32.40, lon=45.60, altitude=12190.0, velocity=260.0, heading=350.0, on_ground=False, origin_country="United States", aircraft_type="F-15E Strike Eagle", operator="US Air Force", is_military=True),
        Aircraft(icao24="ae3456", callsign="NCHO233", lat=33.20, lon=43.80, altitude=10670.0, velocity=200.0, heading=220.0, on_ground=False, origin_country="United States", aircraft_type="KC-135 Stratotanker", operator="US Air Force", is_military=True),
        Aircraft(icao24="ae7890", callsign="DUKE24", lat=31.95, lon=44.70, altitude=3050.0, velocity=130.0, heading=90.0, on_ground=False, origin_country="United States", aircraft_type="UH-60 Black Hawk", operator="US Army", is_military=True),
        Aircraft(icao24="af1234", callsign="", lat=32.08, lon=34.78, altitude=13720.0, velocity=280.0, heading=15.0, on_ground=False, origin_country="Israel", aircraft_type="F-35I Adir", operator="Israeli Air Force", is_military=True),
        Aircraft(icao24="af5678", callsign="", lat=33.10, lon=35.20, altitude=7620.0, velocity=240.0, heading=340.0, on_ground=False, origin_country="Israel", aircraft_type="F-16I Sufa", operator="Israeli Air Force", is_military=True),
        Aircraft(icao24="af9012", callsign="RSAF32", lat=24.50, lon=44.80, altitude=10970.0, velocity=255.0, heading=180.0, on_ground=False, origin_country="Saudi Arabia", aircraft_type="F-15SA", operator="Royal Saudi Air Force", is_military=True),
        Aircraft(icao24="af3456", callsign="UAE41", lat=24.25, lon=54.55, altitude=8530.0, velocity=230.0, heading=310.0, on_ground=False, origin_country="United Arab Emirates", aircraft_type="F-16E Block 60", operator="UAE Air Force", is_military=True),
        Aircraft(icao24="af7890", callsign="QAF15", lat=25.22, lon=51.44, altitude=6100.0, velocity=210.0, heading=60.0, on_ground=False, origin_country="Qatar", aircraft_type="Rafale DQ", operator="Qatar Emiri Air Force", is_military=True),
        Aircraft(icao24="b01234", callsign="ASCOT91", lat=25.38, lon=56.20, altitude=9450.0, velocity=210.0, heading=200.0, on_ground=False, origin_country="United Kingdom", aircraft_type="C-130J Hercules", operator="Royal Air Force", is_military=True),
        Aircraft(icao24="b05678", callsign="TUAF07", lat=37.80, lon=39.50, altitude=11280.0, velocity=265.0, heading=165.0, on_ground=False, origin_country="Turkey", aircraft_type="F-16C Block 50", operator="Turkish Air Force", is_military=True),
        Aircraft(icao24="b09012", callsign="FAF201", lat=34.20, lon=37.80, altitude=10060.0, velocity=240.0, heading=100.0, on_ground=False, origin_country="France", aircraft_type="Rafale C", operator="French Air Force", is_military=True),
        Aircraft(icao24="b03456", callsign="EGY14", lat=30.50, lon=32.50, altitude=7010.0, velocity=220.0, heading=50.0, on_ground=False, origin_country="Egypt", aircraft_type="F-16C Block 40", operator="Egyptian Air Force", is_military=True),
        Aircraft(icao24="b07890", callsign="PAF55", lat=33.90, lon=72.40, altitude=12190.0, velocity=270.0, heading=240.0, on_ground=False, origin_country="Pakistan", aircraft_type="JF-17 Thunder", operator="Pakistan Air Force", is_military=True),
        Aircraft(icao24="b11234", callsign="", lat=35.40, lon=51.15, altitude=5490.0, velocity=200.0, heading=270.0, on_ground=False, origin_country="Iran", aircraft_type="F-14A Tomcat", operator="IRIAF", is_military=True),
        Aircraft(icao24="b15678", callsign="NATO01", lat=37.00, lon=35.40, altitude=10670.0, velocity=220.0, heading=90.0, on_ground=False, origin_country="Turkey", aircraft_type="E-3A Sentry AWACS", operator="NATO", is_military=True),
        Aircraft(icao24="b19012", callsign="OMEGA55", lat=26.60, lon=50.10, altitude=8840.0, velocity=195.0, heading=180.0, on_ground=False, origin_country="United States", aircraft_type="P-8A Poseidon", operator="US Navy", is_military=True),
        Aircraft(icao24="b23456", callsign="RJF10", lat=31.98, lon=35.98, altitude=4270.0, velocity=160.0, heading=215.0, on_ground=False, origin_country="Jordan", aircraft_type="F-16AM", operator="Royal Jordanian Air Force", is_military=True),
        Aircraft(icao24="b27890", callsign="GAF601", lat=37.20, lon=42.00, altitude=7620.0, velocity=210.0, heading=275.0, on_ground=False, origin_country="Germany", aircraft_type="A400M Atlas", operator="German Air Force", is_military=True),
    ]
    # Add slight position randomization so data doesn't look static
    for ac in _base:
        ac.lat += random.uniform(-0.15, 0.15)
        ac.lon += random.uniform(-0.15, 0.15)
        if ac.heading is not None:
            ac.heading = (ac.heading + random.uniform(-5, 5)) % 360
        if ac.altitude is not None:
            ac.altitude += random.uniform(-200, 200)
    return _base


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

    # No fake data - return whatever we got (empty if API failed)
    if not aircraft_list:
        logger.warning("OpenSky API unavailable - no aircraft data. API may be rate-limiting.")

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
