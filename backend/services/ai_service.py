"""
AI Intelligence Analysis Service - Generates situation analysis and insights
from collected geopolitical data. Uses structured analysis when no AI API key
is configured, or can leverage an external AI API for enhanced analysis.
"""

import hashlib
import logging
from collections import Counter
from datetime import datetime, timezone

from cachetools import TTLCache

from config import settings
from models import AIInsight, Aircraft, GeoEvent, MissileEvent

logger = logging.getLogger(__name__)

_insight_cache: TTLCache = TTLCache(maxsize=1, ttl=settings.CACHE_TTL_AI_INSIGHTS)


def _generate_id(text: str) -> str:
    return hashlib.md5(text.encode("utf-8", errors="replace")).hexdigest()[:12]


def _calculate_threat_level(
    conflicts: list[GeoEvent],
    missiles: list[MissileEvent],
    aircraft_count: int,
) -> tuple[str, float]:
    """
    Calculate overall regional threat level based on current data.

    Returns:
        Tuple of (threat_level_str, threat_score_float).
    """
    score = 0.0

    # Conflict severity scoring
    severity_weights = {"critical": 10, "high": 6, "medium": 3, "low": 1}
    for conflict in conflicts:
        score += severity_weights.get(conflict.severity, 1)

    # Missile event scoring
    status_weights = {"confirmed": 8, "reported": 4, "intercepted": 6}
    for missile in missiles:
        score += status_weights.get(missile.status, 3)

    # Military aircraft density scoring
    if aircraft_count > 200:
        score += 15
    elif aircraft_count > 100:
        score += 10
    elif aircraft_count > 50:
        score += 5

    # Normalize to 0-100 scale
    normalized = min(100.0, score)

    if normalized >= 75:
        return "CRITICAL", normalized
    elif normalized >= 50:
        return "HIGH", normalized
    elif normalized >= 25:
        return "ELEVATED", normalized
    elif normalized >= 10:
        return "GUARDED", normalized
    else:
        return "LOW", normalized


def _analyze_conflict_hotspots(conflicts: list[GeoEvent]) -> dict[str, int]:
    """Identify geographic hotspots from conflict data."""
    # Group by approximate region using coordinate buckets
    region_counts: Counter[str] = Counter()
    for conflict in conflicts:
        region = _coords_to_region(conflict.lat, conflict.lon)
        region_counts[region] += 1
    return dict(region_counts.most_common(10))


def _coords_to_region(lat: float, lon: float) -> str:
    """Map coordinates to a named region."""
    regions = {
        "Gaza/Southern Israel": (31.0, 31.8, 34.0, 34.8),
        "West Bank": (31.3, 32.6, 34.8, 35.6),
        "Northern Israel/Southern Lebanon": (32.8, 33.9, 34.5, 36.0),
        "Southern Lebanon": (33.0, 34.0, 35.0, 36.5),
        "Syria - Northwest (Idlib)": (35.5, 36.5, 36.0, 37.0),
        "Syria - Northeast": (35.0, 37.5, 38.0, 42.5),
        "Damascus Area": (33.0, 34.0, 35.5, 37.0),
        "Iraq - Baghdad": (33.0, 33.8, 44.0, 44.8),
        "Iraq - Northern (Kurdistan)": (35.5, 37.5, 43.0, 46.0),
        "Iraq - Western (Anbar)": (31.0, 35.0, 38.0, 44.0),
        "Yemen - Northern": (14.0, 17.0, 43.0, 46.0),
        "Yemen - Southern/Aden": (12.5, 14.0, 44.0, 46.0),
        "Red Sea/Bab el-Mandeb": (12.0, 15.0, 42.0, 44.0),
        "Iran - Western": (32.0, 37.0, 45.0, 49.0),
        "Iran - Central/Tehran": (34.5, 36.5, 50.0, 53.0),
        "Persian Gulf": (25.0, 28.0, 49.0, 55.0),
        "Saudi Arabia - North": (27.0, 32.0, 36.0, 42.0),
        "Egypt - Sinai": (28.0, 31.5, 32.5, 35.0),
        "Turkey - Southeast": (36.5, 39.0, 38.0, 44.0),
        "Afghanistan": (30.0, 38.5, 60.0, 74.0),
        "Pakistan - Northwest": (31.0, 37.0, 69.0, 74.0),
        "Strait of Hormuz": (25.5, 27.0, 55.5, 57.0),
        "Libya": (25.0, 33.0, 10.0, 25.0),
        "Sudan": (10.0, 22.0, 22.0, 38.0),
    }

    for region_name, (lat_min, lat_max, lon_min, lon_max) in regions.items():
        if lat_min <= lat <= lat_max and lon_min <= lon <= lon_max:
            return region_name

    return "Other/Unclassified"


def _analyze_missile_trends(missiles: list[MissileEvent]) -> dict:
    """Analyze missile event patterns."""
    if not missiles:
        return {"total": 0, "types": {}, "statuses": {}}

    type_counts = Counter(m.missile_type for m in missiles)
    status_counts = Counter(m.status for m in missiles)

    return {
        "total": len(missiles),
        "types": dict(type_counts.most_common()),
        "statuses": dict(status_counts.most_common()),
    }


def _generate_situation_briefing(
    conflicts: list[GeoEvent],
    missiles: list[MissileEvent],
    military_aircraft_count: int,
    threat_level: str,
    threat_score: float,
    hotspots: dict[str, int],
    missile_analysis: dict,
) -> str:
    """Generate a structured situation briefing text."""
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    lines = [
        f"SITUATION BRIEFING - {now}",
        f"{'=' * 50}",
        "",
        f"OVERALL THREAT LEVEL: {threat_level} (Score: {threat_score:.1f}/100)",
        "",
        "CONFLICT SUMMARY:",
        f"  Active conflict events tracked: {len(conflicts)}",
    ]

    severity_counts = Counter(c.severity for c in conflicts)
    for sev in ["critical", "high", "medium", "low"]:
        if severity_counts.get(sev, 0) > 0:
            lines.append(f"  - {sev.upper()}: {severity_counts[sev]} events")

    lines.append("")
    lines.append("GEOGRAPHIC HOTSPOTS:")
    if hotspots:
        for region, count in sorted(hotspots.items(), key=lambda x: -x[1])[:5]:
            lines.append(f"  - {region}: {count} events")
    else:
        lines.append("  No concentrated hotspots identified")

    lines.append("")
    lines.append("MISSILE/ROCKET ACTIVITY:")
    if missile_analysis["total"] > 0:
        lines.append(f"  Total events: {missile_analysis['total']}")
        for mtype, count in missile_analysis.get("types", {}).items():
            lines.append(f"  - {mtype}: {count}")
        for status, count in missile_analysis.get("statuses", {}).items():
            lines.append(f"  - Status {status}: {count}")
    else:
        lines.append("  No missile events currently tracked")

    lines.append("")
    lines.append("MILITARY AIR TRAFFIC:")
    lines.append(f"  Tracked military/government aircraft: {military_aircraft_count}")
    if military_aircraft_count > 100:
        lines.append("  NOTE: Elevated military air activity detected")

    lines.append("")
    lines.append("ASSESSMENT:")
    if threat_level == "CRITICAL":
        lines.append("  Active major hostilities detected in multiple regions.")
        lines.append("  High volume of conflict reporting with severe implications.")
        lines.append("  Regional escalation risk is VERY HIGH.")
    elif threat_level == "HIGH":
        lines.append("  Significant conflict activity across the region.")
        lines.append("  Multiple high-severity events require monitoring.")
        lines.append("  Regional escalation risk is HIGH.")
    elif threat_level == "ELEVATED":
        lines.append("  Moderate conflict activity with some areas of concern.")
        lines.append("  Situation bears close monitoring for escalation.")
        lines.append("  Regional escalation risk is MODERATE.")
    elif threat_level == "GUARDED":
        lines.append("  Low-level conflict activity reported.")
        lines.append("  No immediate major escalation indicators.")
        lines.append("  Regional escalation risk is LOW.")
    else:
        lines.append("  Minimal conflict activity detected.")
        lines.append("  Region appears relatively stable at current time.")

    return "\n".join(lines)


def _generate_regional_insights(
    conflicts: list[GeoEvent],
    hotspots: dict[str, int],
) -> list[AIInsight]:
    """Generate per-region analysis insights."""
    insights: list[AIInsight] = []
    now = datetime.now(timezone.utc)

    for region, count in sorted(hotspots.items(), key=lambda x: -x[1])[:5]:
        # Get conflicts for this region
        region_conflicts = [
            c for c in conflicts
            if _coords_to_region(c.lat, c.lon) == region
        ]

        severity_counts = Counter(c.severity for c in region_conflicts)
        critical = severity_counts.get("critical", 0)
        high = severity_counts.get("high", 0)

        if critical > 0:
            severity = "critical"
        elif high > 0:
            severity = "high"
        elif count > 5:
            severity = "medium"
        else:
            severity = "low"

        # Build analysis text
        sources = list(set(c.source for c in region_conflicts if c.source))[:5]
        recent_titles = [c.title for c in region_conflicts[:3]]

        analysis_lines = [
            f"Region: {region}",
            f"Active events: {count}",
            f"Severity breakdown: {dict(severity_counts)}",
            "",
            "Recent reports:",
        ]
        for title in recent_titles:
            analysis_lines.append(f"  - {title[:120]}")

        insight_id = _generate_id(f"regional-{region}-{now.isoformat()}")
        insights.append(AIInsight(
            id=f"insight-reg-{insight_id}",
            title=f"Regional Assessment: {region}",
            summary=f"{count} active events detected in {region}. "
                     f"{'CRITICAL situation - ' if critical > 0 else ''}"
                     f"{'High alert - ' if high > 0 else ''}"
                     f"Monitoring {len(sources)} sources.",
            analysis="\n".join(analysis_lines),
            severity=severity,
            region=region,
            generated_at=now,
            data_sources=sources[:5],
            confidence=min(0.5 + (count * 0.05), 0.95),
        ))

    return insights


async def generate_insights(
    conflicts: list[GeoEvent],
    missiles: list[MissileEvent],
    aircraft: list[Aircraft],
) -> list[AIInsight]:
    """
    Generate AI situation analysis from collected intelligence data.

    When no AI API key is configured, produces structured analytical
    insights from the data patterns. With an API key, could be extended
    to use an LLM for more nuanced analysis.

    Args:
        conflicts: Current conflict events.
        missiles: Current missile/rocket events.
        aircraft: Current military aircraft positions.

    Returns:
        List of AIInsight models with analysis and assessments.
    """
    cache_key = "ai_insights"
    if cache_key in _insight_cache:
        logger.debug("Returning cached AI insights")
        return _insight_cache[cache_key]

    now = datetime.now(timezone.utc)
    insights: list[AIInsight] = []

    # Calculate overall threat level
    threat_level, threat_score = _calculate_threat_level(
        conflicts, missiles, len(aircraft)
    )

    # Analyze hotspots
    hotspots = _analyze_conflict_hotspots(conflicts)

    # Analyze missile trends
    missile_analysis = _analyze_missile_trends(missiles)

    # Generate main situation briefing
    briefing = _generate_situation_briefing(
        conflicts, missiles, len(aircraft),
        threat_level, threat_score, hotspots, missile_analysis,
    )

    main_insight_id = _generate_id(f"main-briefing-{now.isoformat()}")
    insights.append(AIInsight(
        id=f"insight-main-{main_insight_id}",
        title=f"Situation Briefing - Threat Level: {threat_level}",
        summary=f"Regional threat level is {threat_level} (score {threat_score:.1f}/100). "
                f"Tracking {len(conflicts)} conflict events, {len(missiles)} missile events, "
                f"and {len(aircraft)} military aircraft.",
        analysis=briefing,
        severity="critical" if threat_level == "CRITICAL" else
                 "high" if threat_level == "HIGH" else
                 "medium" if threat_level == "ELEVATED" else "low",
        region="Middle East",
        generated_at=now,
        data_sources=["GDELT", "OpenSky Network", "USGS"],
        confidence=0.75,
    ))

    # Generate missile threat assessment if events exist
    if missiles:
        missile_insight_id = _generate_id(f"missile-assessment-{now.isoformat()}")

        missile_lines = [
            "MISSILE/ROCKET THREAT ASSESSMENT",
            f"{'=' * 40}",
            f"Total tracked events: {missile_analysis['total']}",
            "",
        ]

        confirmed = missile_analysis["statuses"].get("confirmed", 0)
        intercepted = missile_analysis["statuses"].get("intercepted", 0)
        reported = missile_analysis["statuses"].get("reported", 0)

        missile_lines.append(f"Confirmed strikes: {confirmed}")
        missile_lines.append(f"Intercepted: {intercepted}")
        missile_lines.append(f"Reported/Unverified: {reported}")
        missile_lines.append("")

        if intercepted > 0:
            intercept_rate = intercepted / (confirmed + intercepted) * 100 if (confirmed + intercepted) > 0 else 0
            missile_lines.append(f"Estimated interception rate: {intercept_rate:.0f}%")

        missile_lines.append("")
        missile_lines.append("Recent missile events:")
        for m in missiles[:5]:
            missile_lines.append(f"  - [{m.status.upper()}] {m.title[:100]}")

        missile_severity = "critical" if confirmed > 3 else "high" if len(missiles) > 5 else "medium"

        insights.append(AIInsight(
            id=f"insight-missile-{missile_insight_id}",
            title="Missile & Rocket Threat Assessment",
            summary=f"Tracking {len(missiles)} missile/rocket events. "
                    f"{confirmed} confirmed, {intercepted} intercepted, "
                    f"{reported} reported.",
            analysis="\n".join(missile_lines),
            severity=missile_severity,
            region="Middle East",
            generated_at=now,
            data_sources=["GDELT"],
            confidence=0.65,
        ))

    # Generate regional insights
    regional = _generate_regional_insights(conflicts, hotspots)
    insights.extend(regional)

    # Generate stability index insight
    stability_id = _generate_id(f"stability-{now.isoformat()}")
    stability_score = max(0, 100 - threat_score)

    stability_assessment = []
    if stability_score >= 75:
        stability_assessment.append("Regional stability index is GOOD.")
        stability_assessment.append("Major flashpoints are currently contained.")
    elif stability_score >= 50:
        stability_assessment.append("Regional stability index is MODERATE.")
        stability_assessment.append("Several areas of active conflict but not escalating significantly.")
    elif stability_score >= 25:
        stability_assessment.append("Regional stability index is POOR.")
        stability_assessment.append("Multiple active conflicts with risk of escalation.")
    else:
        stability_assessment.append("Regional stability index is CRITICAL.")
        stability_assessment.append("Widespread conflict activity with high escalation risk.")

    stability_assessment.append("")
    stability_assessment.append(f"Stability Score: {stability_score:.1f}/100")
    stability_assessment.append(f"Active hotspots: {len(hotspots)}")
    stability_assessment.append(f"Data points analyzed: {len(conflicts) + len(missiles) + len(aircraft)}")

    insights.append(AIInsight(
        id=f"insight-stability-{stability_id}",
        title=f"Regional Stability Index: {stability_score:.0f}/100",
        summary=f"Regional stability score is {stability_score:.0f}/100. "
                f"{'Situation is relatively stable.' if stability_score >= 60 else 'Elevated instability detected.'}",
        analysis="\n".join(stability_assessment),
        severity="low" if stability_score >= 75 else
                 "medium" if stability_score >= 50 else
                 "high" if stability_score >= 25 else "critical",
        region="Middle East",
        generated_at=now,
        data_sources=["GDELT", "OpenSky Network", "Aggregated OSINT"],
        confidence=0.70,
    ))

    _insight_cache[cache_key] = insights
    logger.info("Generated %d AI insights", len(insights))
    return insights
