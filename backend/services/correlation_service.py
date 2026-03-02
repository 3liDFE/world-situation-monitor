"""
Event Correlation Service - Links related events across layers
by temporal proximity, geographic proximity, and keyword similarity.
Produces event chains showing how incidents cascade across the region.
"""

import hashlib
import logging
import math
from collections import defaultdict
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

# ============================================================================
# Keyword groups for thematic correlation
# ============================================================================

KEYWORD_GROUPS = {
    "iran_missile": {"iran", "missile", "ballistic", "irgc", "tehran", "iranian"},
    "israel_defense": {"iron dome", "intercepted", "israel", "idf", "defense", "tel aviv"},
    "houthi_shipping": {"houthi", "red sea", "shipping", "vessel", "tanker", "aden", "bab al-mandab"},
    "flight_diversion": {"flight", "rerouted", "diverted", "airspace", "notam", "closed airspace"},
    "oil_energy": {"oil", "crude", "brent", "energy", "price", "opec", "pipeline", "refinery"},
    "hezbollah_lebanon": {"hezbollah", "lebanon", "beirut", "nasrallah", "south lebanon"},
    "gaza_conflict": {"gaza", "hamas", "palestinian", "rafah", "khan younis", "ceasefire"},
    "syria_airstrike": {"syria", "damascus", "aleppo", "airstrike", "rebel", "assad"},
    "ukraine_war": {"ukraine", "kyiv", "donetsk", "kherson", "zaporizhzhia", "russian", "frontline"},
    "cyber_infra": {"cyber", "hack", "outage", "disruption", "internet", "cable", "aws", "cloud"},
    "nuclear_threat": {"nuclear", "enrichment", "uranium", "iaea", "centrifuge", "plutonium"},
    "naval_tension": {"navy", "naval", "destroyer", "carrier", "strait", "hormuz", "warship"},
    "drone_strike": {"drone", "uav", "unmanned", "kamikaze", "shahed"},
    "evacuation_humanitarian": {"evacuation", "humanitarian", "refugees", "displaced", "aid", "corridor"},
    "sanctions_diplomacy": {"sanctions", "diplomacy", "treaty", "agreement", "summit", "talks"},
}


def _haversine(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Calculate distance in km between two lat/lon points."""
    R = 6371.0
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = math.sin(dlat / 2) ** 2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon / 2) ** 2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def _parse_timestamp(ts) -> datetime | None:
    """Parse various timestamp formats to datetime."""
    if ts is None:
        return None
    if isinstance(ts, datetime):
        return ts
    if isinstance(ts, str):
        for fmt in [
            "%Y-%m-%dT%H:%M:%S.%f",
            "%Y-%m-%dT%H:%M:%S",
            "%Y-%m-%dT%H:%M:%S%z",
            "%Y-%m-%dT%H:%M:%S.%f%z",
        ]:
            try:
                return datetime.strptime(ts.replace("+00:00", "").replace("Z", ""), fmt.replace("%z", ""))
            except ValueError:
                continue
    return None


def _extract_text(event: dict | object, field: str, default: str = "") -> str:
    """Extract text field from dict or Pydantic model."""
    if isinstance(event, dict):
        return str(event.get(field, default))
    return str(getattr(event, field, default))


def _extract_float(event: dict | object, field: str, default: float = 0.0) -> float:
    """Extract float field from dict or Pydantic model."""
    if isinstance(event, dict):
        val = event.get(field, default)
    else:
        val = getattr(event, field, default)
    try:
        return float(val) if val is not None else default
    except (ValueError, TypeError):
        return default


def _normalize_events(conflicts, missiles, news, infra_outages) -> list[dict]:
    """Normalize all events to a common format for correlation."""
    normalized = []

    for c in (conflicts or []):
        metadata = c.metadata if hasattr(c, "metadata") else (c.get("metadata", {}) if isinstance(c, dict) else {})
        location = metadata.get("location", "") if isinstance(metadata, dict) else ""
        normalized.append({
            "id": _extract_text(c, "id"),
            "type": "conflict",
            "lat": _extract_float(c, "lat"),
            "lon": _extract_float(c, "lon"),
            "timestamp": _parse_timestamp(_extract_text(c, "timestamp")),
            "title": _extract_text(c, "title"),
            "severity": _extract_text(c, "severity", "medium"),
            "location": location,
        })

    for m in (missiles or []):
        normalized.append({
            "id": _extract_text(m, "id"),
            "type": "missile",
            "lat": _extract_float(m, "launch_lat"),
            "lon": _extract_float(m, "launch_lon"),
            "timestamp": _parse_timestamp(_extract_text(m, "timestamp")),
            "title": _extract_text(m, "title"),
            "severity": "high",
            "location": "",
        })

    for n in (news or []):
        normalized.append({
            "id": _extract_text(n, "id"),
            "type": "news",
            "lat": _extract_float(n, "lat") if (isinstance(n, dict) and "lat" in n) else 0.0,
            "lon": _extract_float(n, "lon") if (isinstance(n, dict) and "lon" in n) else 0.0,
            "timestamp": _parse_timestamp(_extract_text(n, "published_at")),
            "title": _extract_text(n, "title"),
            "severity": "info",
            "location": _extract_text(n, "country"),
        })

    for io in (infra_outages or []):
        normalized.append({
            "id": _extract_text(io, "id"),
            "type": "infrastructure",
            "lat": _extract_float(io, "lat"),
            "lon": _extract_float(io, "lon"),
            "timestamp": _parse_timestamp(
                _extract_text(io, "start_time") or _extract_text(io, "last_update")
            ),
            "title": _extract_text(io, "title"),
            "severity": _extract_text(io, "severity", "info"),
            "location": _extract_text(io, "country"),
        })

    return normalized


def _keyword_overlap(text_a: str, text_b: str) -> float:
    """Calculate keyword group overlap between two texts (0.0 to 1.0)."""
    a_lower = text_a.lower()
    b_lower = text_b.lower()

    a_groups = set()
    b_groups = set()

    for group_name, keywords in KEYWORD_GROUPS.items():
        if any(kw in a_lower for kw in keywords):
            a_groups.add(group_name)
        if any(kw in b_lower for kw in keywords):
            b_groups.add(group_name)

    if not a_groups or not b_groups:
        return 0.0

    intersection = a_groups & b_groups
    union = a_groups | b_groups
    return len(intersection) / len(union) if union else 0.0


def _correlation_score(a: dict, b: dict) -> float:
    """Score how related two events are (0.0 to 1.0)."""
    score = 0.0

    # Temporal proximity (0-0.4)
    if a["timestamp"] and b["timestamp"]:
        try:
            dt = abs((a["timestamp"] - b["timestamp"]).total_seconds())
            if dt < 3600:
                score += 0.4   # within 1 hour
            elif dt < 21600:
                score += 0.25  # within 6 hours
            elif dt < 86400:
                score += 0.1   # within 24 hours
        except Exception:
            pass

    # Geographic proximity (0-0.3)
    if a["lat"] and b["lat"] and a["lon"] and b["lon"]:
        try:
            dist = _haversine(a["lat"], a["lon"], b["lat"], b["lon"])
            if dist < 50:
                score += 0.3
            elif dist < 200:
                score += 0.2
            elif dist < 500:
                score += 0.1
        except Exception:
            pass

    # Keyword overlap (0-0.3)
    overlap = _keyword_overlap(a["title"], b["title"])
    score += overlap * 0.3

    return min(score, 1.0)


def _find_chains(events: list[dict], edges: list[tuple]) -> list[dict]:
    """Find connected components (event chains) from correlation edges."""
    if not edges:
        return []

    # Union-Find
    parent = list(range(len(events)))

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(x, y):
        px, py = find(x), find(y)
        if px != py:
            parent[px] = py

    for i, j, _ in edges:
        union(i, j)

    # Group by root
    groups: dict[int, list[int]] = defaultdict(list)
    for idx in range(len(events)):
        groups[find(idx)].append(idx)

    # Build chains (only groups with 2+ events)
    chains = []
    for group_indices in groups.values():
        if len(group_indices) < 2:
            continue

        chain_events = [events[i] for i in group_indices]
        # Sort by timestamp
        chain_events.sort(key=lambda e: e["timestamp"] or datetime.min)

        # Determine chain characteristics
        types = set(e["type"] for e in chain_events)
        regions = list(set(e["location"] for e in chain_events if e["location"]))
        severities = [e["severity"] for e in chain_events]

        # Chain type
        if "missile" in types and "conflict" in types:
            chain_type = "escalation"
        elif "infrastructure" in types:
            chain_type = "cascade"
        elif len(types) > 2:
            chain_type = "cascade"
        else:
            chain_type = "related"

        # Chain severity (worst of any event)
        sev_order = {"critical": 4, "high": 3, "severe": 3, "medium": 2, "moderate": 2, "low": 1, "info": 0}
        max_sev = max((sev_order.get(s, 0) for s in severities), default=0)
        sev_map = {4: "critical", 3: "high", 2: "medium", 1: "low", 0: "info"}
        chain_severity = sev_map.get(max_sev, "medium")

        # Title from the most severe event
        main_event = max(chain_events, key=lambda e: sev_order.get(e["severity"], 0))
        chain_title = main_event["title"][:100]

        # Timestamps
        ts_start = chain_events[0]["timestamp"]
        ts_end = chain_events[-1]["timestamp"]

        chain_id = hashlib.md5(
            "-".join(e["id"] for e in chain_events[:3]).encode()
        ).hexdigest()[:10]

        chains.append({
            "id": f"chain-{chain_id}",
            "title": chain_title,
            "events": [
                {
                    "id": e["id"],
                    "type": e["type"],
                    "title": e["title"][:120],
                    "lat": e["lat"],
                    "lon": e["lon"],
                    "timestamp": e["timestamp"].isoformat() if e["timestamp"] else "",
                    "severity": e["severity"],
                }
                for e in chain_events
            ],
            "chain_type": chain_type,
            "severity": chain_severity,
            "timestamp_start": ts_start.isoformat() if ts_start else "",
            "timestamp_end": ts_end.isoformat() if ts_end else "",
            "regions": regions[:5],
            "summary": f"{len(chain_events)} related events across {', '.join(regions[:3]) or 'multiple regions'}",
        })

    # Sort chains by severity then event count
    chains.sort(key=lambda c: (
        -{"critical": 4, "high": 3, "medium": 2, "low": 1, "info": 0}.get(c["severity"], 0),
        -len(c["events"]),
    ))

    return chains[:20]  # Top 20 chains


def correlate_events(
    conflicts=None, missiles=None, news=None, infra_outages=None
) -> list[dict]:
    """
    Find correlated event chains across all layers.
    Returns list of event chain dicts.
    """
    all_events = _normalize_events(conflicts, missiles, news, infra_outages)

    if len(all_events) < 2:
        return []

    # Limit to most recent 150 events for performance (O(n^2))
    all_events.sort(key=lambda e: e["timestamp"] or datetime.min, reverse=True)
    all_events = all_events[:150]

    # Build correlation graph
    edges = []
    threshold = 0.35
    for i in range(len(all_events)):
        for j in range(i + 1, len(all_events)):
            score = _correlation_score(all_events[i], all_events[j])
            if score >= threshold:
                edges.append((i, j, score))

    chains = _find_chains(all_events, edges)
    logger.info(
        "Correlated %d events into %d chains (from %d edges)",
        len(all_events), len(chains), len(edges),
    )
    return chains
