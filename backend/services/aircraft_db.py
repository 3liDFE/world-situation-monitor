"""
Aircraft Type Identification Service
Maps ICAO24 hex codes to aircraft types using built-in military database
and hexdb.io API fallback.
"""

import logging
from typing import Optional

import httpx
from cachetools import TTLCache

logger = logging.getLogger(__name__)

# Cache aircraft type lookups for 1 hour
_type_cache: TTLCache = TTLCache(maxsize=2000, ttl=3600)

# Known military aircraft ICAO24 hex ranges
# Format: (hex_start, hex_end, aircraft_type, operator)
# These are approximations based on publicly known allocations
MILITARY_HEX_RANGES = [
    # US Military (AE prefix range)
    ("ae0000", "ae ffff", "US Military", "USAF/USN"),
    # Specific known US military types
    ("ae0000", "ae0fff", "KC-135 Stratotanker", "USAF"),
    ("ae1000", "ae1fff", "C-17 Globemaster III", "USAF"),
    ("ae2000", "ae2fff", "C-130 Hercules", "USAF"),
    ("ae3000", "ae3fff", "KC-10 Extender", "USAF"),
    ("ae4000", "ae4fff", "E-3 Sentry AWACS", "USAF"),
    ("ae5000", "ae5fff", "P-8A Poseidon", "USN"),
    ("ae6000", "ae6fff", "RC-135 Rivet Joint", "USAF"),
    ("ae7000", "ae7fff", "RQ-4 Global Hawk", "USAF"),
    ("ae8000", "ae8fff", "B-52H Stratofortress", "USAF"),
    ("a00000", "afffff", "US Registered", "FAA"),

    # UK Military
    ("43c000", "43cfff", "RAF Aircraft", "Royal Air Force"),

    # French Military
    ("3a0000", "3affff", "French Military", "Armee de l'Air"),

    # German Military
    ("3c0000", "3cffff", "German Military", "Luftwaffe"),

    # Turkish Military
    ("4b0000", "4bffff", "Turkish Military", "Turkish Air Force"),

    # Israeli Military
    ("738000", "738fff", "Israeli Military", "IAF"),

    # Saudi Military
    ("710000", "710fff", "Saudi Military", "RSAF"),

    # UAE Military
    ("896000", "896fff", "UAE Military", "UAEAF"),

    # Iranian Military
    ("730000", "730fff", "Iranian Military", "IRIAF"),

    # Egyptian Military
    ("700000", "700fff", "Egyptian Military", "EAF"),

    # Jordanian Military
    ("740000", "740fff", "Jordanian Military", "RJAF"),

    # Qatar Military
    ("060000", "060fff", "Qatari Military", "QAF"),

    # Russian Military
    ("150000", "15ffff", "Russian Military", "VKS"),
]

# Callsign to aircraft type mapping (common military callsign patterns)
CALLSIGN_AIRCRAFT_MAP = {
    "RCH": "C-17 Globemaster III",
    "REACH": "C-17 Globemaster III",
    "DUKE": "C-12 Huron / RC-12",
    "EVAC": "C-9 Nightingale",
    "IRON": "F-15E Strike Eagle",
    "JAKE": "AV-8B / F-35B",
    "KING": "HC-130J / HH-60",
    "METAL": "C-130 Hercules",
    "NIGHT": "MC-130J / CV-22",
    "OMEGA": "KC-10 / KC-135",
    "PACK": "F-16 Fighting Falcon",
    "RAZOR": "MQ-9 Reaper",
    "SAM": "VC-25A / C-32A (VIP)",
    "SPAR": "C-37A / C-40B (Gov)",
    "STEEL": "A-10 Thunderbolt II",
    "VADER": "F-22 Raptor",
    "WOLF": "MC-130 / AC-130",
    "TOPCAT": "E-2D Hawkeye",
    "ASCOT": "RAF Transport",
    "TARTAN": "RAF Typhoon",
    "NATO": "E-3A AWACS",
    "CNV": "USN Fighter/Patrol",
    "NCHO": "KC-135 Stratotanker",
    "GRIM": "MQ-9 Reaper",
    "FORTE": "RQ-4 Global Hawk",
    "HOMER": "P-8A Poseidon",
    "BATT": "B-1B Lancer",
    "DEATH": "B-52H Stratofortress",
    "BONE": "B-1B Lancer",
    "TOXIN": "F-16 Aggressor",
    "VIPER": "F-16 Fighting Falcon",
    "EAGLE": "F-15 Eagle",
    "RAPTOR": "F-22 Raptor",
    "BOLT": "F-35A Lightning II",
    "LIGHT": "F-35 Lightning II",
    "RAGE": "F/A-18 Super Hornet",
    "CHAOS": "F/A-18 Hornet",
    "HAVOC": "AH-64 Apache",
    "ATLAS": "C-5M Super Galaxy",
}

# Country to typical military aircraft mapping
COUNTRY_AIRCRAFT = {
    "Israel": ["F-35I Adir", "F-16I Sufa", "F-15I Ra'am", "Apache AH-64"],
    "Iran": ["F-14 Tomcat", "F-4 Phantom", "Su-24 Fencer", "Shahed-136 UAV"],
    "Turkey": ["F-16C/D", "Bayraktar TB2", "KAAN (TF-X)", "A400M"],
    "Saudi Arabia": ["F-15SA", "Typhoon", "Tornado IDS", "AH-64 Apache"],
    "United Arab Emirates": ["F-16E/F Block 60", "Mirage 2000", "AH-64 Apache"],
    "Egypt": ["F-16C/D", "Rafale", "MiG-29M", "AH-64D Apache"],
    "Jordan": ["F-16A/B", "UH-60 Black Hawk", "AH-1F Cobra"],
    "United States": ["F-16", "F-15", "F-35A", "KC-135", "C-17", "B-52H"],
    "Russia": ["Su-35S", "Su-34", "Tu-95MS", "MiG-31"],
    "United Kingdom": ["Typhoon FGR4", "F-35B", "A400M Atlas", "Voyager KC3"],
    "France": ["Rafale", "Mirage 2000D", "A400M Atlas", "E-3F AWACS"],
}


async def identify_aircraft_type(icao24: str, callsign: str = "", origin_country: str = "") -> dict:
    """
    Identify an aircraft type from its ICAO24 hex code and callsign.

    Returns dict with:
        - aircraft_type: str (e.g., "F-16 Fighting Falcon")
        - operator: str (e.g., "USAF")
        - is_military: bool
        - confidence: str ("high", "medium", "low")
    """
    cache_key = f"{icao24}-{callsign}"
    if cache_key in _type_cache:
        return _type_cache[cache_key]

    result = {
        "aircraft_type": "Unknown",
        "operator": "",
        "is_military": False,
        "confidence": "low",
    }

    # 1. Try callsign-based identification first (highest confidence)
    if callsign:
        callsign_upper = callsign.upper().strip()
        for prefix, aircraft_type in CALLSIGN_AIRCRAFT_MAP.items():
            if callsign_upper.startswith(prefix):
                result["aircraft_type"] = aircraft_type
                result["operator"] = _get_operator_from_callsign(prefix)
                result["is_military"] = True
                result["confidence"] = "high"
                _type_cache[cache_key] = result
                return result

    # 2. Try hex range identification
    try:
        hex_int = int(icao24, 16)
        for hex_start, hex_end, aircraft_type, operator in MILITARY_HEX_RANGES:
            start_int = int(hex_start.replace(" ", ""), 16)
            end_int = int(hex_end.replace(" ", ""), 16)
            if start_int <= hex_int <= end_int:
                result["aircraft_type"] = aircraft_type
                result["operator"] = operator
                result["is_military"] = True
                result["confidence"] = "medium"
                break
    except ValueError:
        pass

    # 3. Try hexdb.io API for specific type
    if result["aircraft_type"] in ("Unknown", "US Registered", "US Military"):
        api_result = await _query_hexdb(icao24)
        if api_result:
            if api_result.get("Type"):
                result["aircraft_type"] = api_result["Type"]
                result["confidence"] = "high"
            if api_result.get("RegisteredOwners"):
                result["operator"] = api_result["RegisteredOwners"]
            if api_result.get("MilitaryFlag"):
                result["is_military"] = True

    # 4. Fallback: use country to suggest possible types
    if result["aircraft_type"] == "Unknown" and origin_country:
        possible = COUNTRY_AIRCRAFT.get(origin_country, [])
        if possible and result["is_military"]:
            result["aircraft_type"] = f"Military ({possible[0]}?)"
            result["confidence"] = "low"

    _type_cache[cache_key] = result
    return result


async def enrich_aircraft_list(aircraft_list: list[dict]) -> list[dict]:
    """
    Enrich a list of aircraft dicts with type identification.
    Modifies in place and returns the list.
    """
    for ac in aircraft_list:
        icao24 = ac.get("icao24", "")
        callsign = ac.get("callsign", "")
        country = ac.get("origin_country", "")

        type_info = await identify_aircraft_type(icao24, callsign, country)
        ac["aircraft_type"] = type_info["aircraft_type"]
        ac["operator"] = type_info["operator"]
        ac["is_military"] = type_info["is_military"]
        ac["type_confidence"] = type_info["confidence"]

    return aircraft_list


async def _query_hexdb(icao24: str) -> Optional[dict]:
    """Query hexdb.io API for aircraft info."""
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get(f"https://hexdb.io/api/v1/aircraft/{icao24}")
            if response.status_code == 200:
                return response.json()
    except Exception as e:
        logger.debug("hexdb.io lookup failed for %s: %s", icao24, e)
    return None


def _get_operator_from_callsign(prefix: str) -> str:
    """Get operator from callsign prefix."""
    operator_map = {
        "RCH": "USAF AMC",
        "REACH": "USAF AMC",
        "DUKE": "US Army",
        "IRON": "USAF",
        "JAKE": "USMC",
        "KING": "USAF Rescue",
        "METAL": "USAF",
        "NIGHT": "AFSOC",
        "OMEGA": "USAF",
        "PACK": "USAF",
        "RAZOR": "USAF",
        "SAM": "89th Airlift Wing",
        "SPAR": "US Government",
        "STEEL": "USAF ACC",
        "VADER": "USAF ACC",
        "WOLF": "AFSOC",
        "TOPCAT": "USN",
        "ASCOT": "RAF",
        "TARTAN": "RAF",
        "NATO": "NATO",
        "CNV": "USN",
    }
    return operator_map.get(prefix, "Unknown")
