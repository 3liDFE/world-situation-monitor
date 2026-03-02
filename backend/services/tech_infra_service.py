"""
Tech Infrastructure Monitor Service - Tracks cloud provider outages,
internet disruptions, undersea cable status, and data center health.
Classifies incidents as war-related, cyber attack, natural disaster, or technical.
"""

import hashlib
import html
import logging
import re
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from typing import Optional
from xml.etree import ElementTree

import httpx
from cachetools import TTLCache

logger = logging.getLogger(__name__)

_infra_cache: TTLCache = TTLCache(maxsize=10, ttl=120)

# ============================================================================
# Static Data: Cloud Data Centers in/near Middle East + key global hubs
# ============================================================================

DATA_CENTERS = [
    {
        "id": "dc-aws-bahrain", "provider": "AWS", "region": "me-south-1",
        "name": "AWS Middle East (Bahrain)", "lat": 26.07, "lon": 50.56,
        "country": "Bahrain", "services": ["EC2", "S3", "RDS", "CloudFront"],
    },
    {
        "id": "dc-aws-uae", "provider": "AWS", "region": "me-central-1",
        "name": "AWS Middle East (UAE)", "lat": 24.45, "lon": 54.65,
        "country": "UAE", "services": ["EC2", "S3", "RDS", "Lambda"],
    },
    {
        "id": "dc-azure-uae-north", "provider": "Azure", "region": "uaenorth",
        "name": "Azure UAE North (Dubai)", "lat": 25.27, "lon": 55.31,
        "country": "UAE", "services": ["VMs", "Storage", "SQL", "AKS"],
    },
    {
        "id": "dc-azure-uae-central", "provider": "Azure", "region": "uaecentral",
        "name": "Azure UAE Central (Abu Dhabi)", "lat": 24.45, "lon": 54.65,
        "country": "UAE", "services": ["VMs", "Storage"],
    },
    {
        "id": "dc-azure-qatar", "provider": "Azure", "region": "qatarcentral",
        "name": "Azure Qatar Central (Doha)", "lat": 25.29, "lon": 51.53,
        "country": "Qatar", "services": ["VMs", "Storage", "SQL"],
    },
    {
        "id": "dc-gcp-doha", "provider": "GCP", "region": "me-central1",
        "name": "GCP Doha", "lat": 25.29, "lon": 51.53,
        "country": "Qatar", "services": ["Compute", "Storage", "BigQuery"],
    },
    {
        "id": "dc-gcp-dammam", "provider": "GCP", "region": "me-central2",
        "name": "GCP Dammam", "lat": 26.39, "lon": 49.98,
        "country": "Saudi Arabia", "services": ["Compute", "Storage"],
    },
    {
        "id": "dc-gcp-tel-aviv", "provider": "GCP", "region": "me-west1",
        "name": "GCP Tel Aviv", "lat": 32.09, "lon": 34.78,
        "country": "Israel", "services": ["Compute", "Storage", "AI"],
    },
    {
        "id": "dc-aws-mumbai", "provider": "AWS", "region": "ap-south-1",
        "name": "AWS Mumbai (ME traffic hub)", "lat": 19.08, "lon": 72.88,
        "country": "India", "services": ["EC2", "S3", "CloudFront"],
    },
    {
        "id": "dc-aws-frankfurt", "provider": "AWS", "region": "eu-central-1",
        "name": "AWS Frankfurt (EU-ME link)", "lat": 50.11, "lon": 8.68,
        "country": "Germany", "services": ["EC2", "S3", "RDS"],
    },
    {
        "id": "dc-oracle-jeddah", "provider": "Oracle", "region": "me-jeddah-1",
        "name": "Oracle Cloud Jeddah", "lat": 21.49, "lon": 39.19,
        "country": "Saudi Arabia", "services": ["Compute", "Storage"],
    },
    {
        "id": "dc-alibaba-dubai", "provider": "Alibaba", "region": "me-east-1",
        "name": "Alibaba Cloud Dubai", "lat": 25.20, "lon": 55.27,
        "country": "UAE", "services": ["ECS", "OSS"],
    },
]

# ============================================================================
# Static Data: Undersea Cable Landing Points
# ============================================================================

UNDERSEA_CABLES = [
    {
        "id": "cable-seamewe5", "name": "SEA-ME-WE 5",
        "lat": 30.04, "lon": 31.24, "country": "Egypt",
        "description": "Major Europe-Asia cable via Suez (20Tbps)",
        "connects": "Singapore → Egypt → France",
    },
    {
        "id": "cable-seamewe6", "name": "SEA-ME-WE 6",
        "lat": 30.04, "lon": 31.24, "country": "Egypt",
        "description": "Next-gen Europe-Asia backbone (100Tbps+)",
        "connects": "Singapore → Oman → Djibouti → Egypt → France",
    },
    {
        "id": "cable-aae1", "name": "AAE-1 (Asia Africa Europe)",
        "lat": 12.60, "lon": 43.15, "country": "Djibouti",
        "description": "25,000km system connecting ME to Asia/Europe",
        "connects": "Hong Kong → UAE → Djibouti → Egypt → France",
    },
    {
        "id": "cable-falcon", "name": "FLAG/FALCON",
        "lat": 25.27, "lon": 55.27, "country": "UAE",
        "description": "Major India-ME-Europe cable via Dubai",
        "connects": "India → UAE → Egypt → UK",
    },
    {
        "id": "cable-imewe", "name": "IMEWE (India-ME-Western Europe)",
        "lat": 25.37, "lon": 55.41, "country": "UAE",
        "description": "India to Western Europe via ME landing",
        "connects": "Mumbai → Fujairah → Jeddah → Marseille",
    },
    {
        "id": "cable-epeg", "name": "EPEG (Europe-Persia Express Gateway)",
        "lat": 25.37, "lon": 55.41, "country": "UAE",
        "description": "Direct Europe to Persian Gulf connectivity",
        "connects": "Frankfurt → UAE → Oman",
    },
    {
        "id": "cable-gulf-bridge", "name": "Gulf Bridge International",
        "lat": 26.07, "lon": 50.56, "country": "Bahrain",
        "description": "Interconnects all Gulf states",
        "connects": "Kuwait → Bahrain → Qatar → UAE → Oman → Iraq → Saudi Arabia",
    },
    {
        "id": "cable-tgn-eurasia", "name": "TGN-Eurasia",
        "lat": 41.01, "lon": 28.98, "country": "Turkey",
        "description": "Connects Europe to Asia via Turkey",
        "connects": "UK → Turkey → India",
    },
]

# ============================================================================
# News-based infrastructure monitoring
# ============================================================================

INFRA_NEWS_QUERIES = [
    "AWS outage service disruption",
    "Azure outage service disruption",
    "Google Cloud GCP outage disruption",
    "internet outage disruption Middle East",
    "undersea cable damage cut submarine",
    "data center outage fire damage",
    "cloud service downtime major outage",
    "internet blackout country shutdown",
    "cyber attack infrastructure DDoS",
    "telecom outage network disruption",
]

_GOOGLE_NEWS_RSS = "https://news.google.com/rss/search?q={query}&hl=en-US&gl=US&ceid=US:en"


# ============================================================================
# Classification logic
# ============================================================================

# Keywords for classifying outage causes
_WAR_KEYWORDS = {
    "missile", "strike", "bomb", "attack", "military", "war", "conflict",
    "shelling", "airstrike", "explosion", "sabotage", "destroyed",
}
_CYBER_KEYWORDS = {
    "cyber", "hack", "ddos", "ransomware", "breach", "malware", "phishing",
    "apt", "vulnerability", "exploit", "zero-day",
}
_NATURAL_KEYWORDS = {
    "earthquake", "flood", "storm", "hurricane", "typhoon", "fire",
    "lightning", "heat", "power outage", "natural disaster",
}

# Region lookup for news
_REGION_KEYWORDS = {
    "bahrain": ("Bahrain", 26.07, 50.56),
    "uae": ("UAE", 24.45, 54.65),
    "emirates": ("UAE", 24.45, 54.65),
    "dubai": ("UAE", 25.20, 55.27),
    "abu dhabi": ("UAE", 24.45, 54.65),
    "qatar": ("Qatar", 25.29, 51.53),
    "doha": ("Qatar", 25.29, 51.53),
    "saudi": ("Saudi Arabia", 24.71, 46.68),
    "riyadh": ("Saudi Arabia", 24.71, 46.68),
    "jeddah": ("Saudi Arabia", 21.49, 39.19),
    "dammam": ("Saudi Arabia", 26.39, 49.98),
    "israel": ("Israel", 32.09, 34.78),
    "tel aviv": ("Israel", 32.09, 34.78),
    "egypt": ("Egypt", 30.04, 31.24),
    "cairo": ("Egypt", 30.04, 31.24),
    "iran": ("Iran", 35.69, 51.39),
    "tehran": ("Iran", 35.69, 51.39),
    "turkey": ("Turkey", 41.01, 28.98),
    "istanbul": ("Turkey", 41.01, 28.98),
    "iraq": ("Iraq", 33.31, 44.37),
    "mumbai": ("India", 19.08, 72.88),
    "india": ("India", 19.08, 72.88),
    "frankfurt": ("Germany", 50.11, 8.68),
    "europe": ("Europe", 48.86, 2.35),
    "oman": ("Oman", 23.59, 58.38),
    "kuwait": ("Kuwait", 29.38, 47.98),
    "jordan": ("Jordan", 31.95, 35.93),
    "yemen": ("Yemen", 15.37, 44.19),
    "syria": ("Syria", 33.51, 36.28),
    "lebanon": ("Lebanon", 33.89, 35.50),
    "pakistan": ("Pakistan", 33.69, 73.04),
    "djibouti": ("Djibouti", 11.59, 43.15),
    "sudan": ("Sudan", 15.50, 32.56),
    "libya": ("Libya", 32.90, 13.18),
    "ukraine": ("Ukraine", 50.45, 30.52),
    "russia": ("Russia", 55.76, 37.62),
}

_PROVIDER_KEYWORDS = {
    "aws": "AWS", "amazon web services": "AWS", "amazon cloud": "AWS",
    "azure": "Azure", "microsoft cloud": "Azure", "microsoft azure": "Azure",
    "google cloud": "GCP", "gcp": "GCP", "google compute": "GCP",
    "oracle cloud": "Oracle", "alibaba cloud": "Alibaba",
    "cloudflare": "Cloudflare", "akamai": "Akamai",
}


def classify_outage(title: str, description: str = "") -> tuple[str, str]:
    """
    Classify an outage's cause and severity.
    Returns (cause, severity) where:
      cause: war_related, cyber_attack, natural_disaster, technical, unknown
      severity: critical, severe, moderate, info
    """
    text = f"{title} {description}".lower()

    # Check cause
    war_score = sum(1 for kw in _WAR_KEYWORDS if kw in text)
    cyber_score = sum(1 for kw in _CYBER_KEYWORDS if kw in text)
    natural_score = sum(1 for kw in _NATURAL_KEYWORDS if kw in text)

    if war_score >= 2:
        cause = "war_related"
    elif cyber_score >= 2:
        cause = "cyber_attack"
    elif natural_score >= 2:
        cause = "natural_disaster"
    elif war_score >= 1:
        cause = "war_related"
    elif cyber_score >= 1:
        cause = "cyber_attack"
    elif natural_score >= 1:
        cause = "natural_disaster"
    else:
        cause = "technical"

    # Severity based on keywords
    if any(w in text for w in ["major outage", "complete outage", "total failure", "destroyed", "critical"]):
        severity = "critical"
    elif any(w in text for w in ["outage", "disruption", "failure", "down", "unavailable"]):
        severity = "severe"
    elif any(w in text for w in ["degraded", "slow", "intermittent", "partial"]):
        severity = "moderate"
    else:
        severity = "info"

    return cause, severity


def _detect_provider(text: str) -> str:
    """Detect cloud provider from text."""
    text_lower = text.lower()
    for keyword, provider in _PROVIDER_KEYWORDS.items():
        if keyword in text_lower:
            return provider
    return "ISP"


def _detect_region(text: str) -> tuple[str, float, float]:
    """Detect geographic region from text. Returns (country, lat, lon)."""
    text_lower = text.lower()
    for keyword, (country, lat, lon) in _REGION_KEYWORDS.items():
        if keyword in text_lower:
            return country, lat, lon
    return "Global", 30.0, 45.0  # default to ME center


# ============================================================================
# Cloud provider status fetching
# ============================================================================

async def _fetch_aws_status() -> list[dict]:
    """Fetch AWS service health from status data JSON."""
    outages = []
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get("https://health.aws.amazon.com/health/status")
            if resp.status_code == 200:
                # AWS returns HTML - check for current issues mentioned
                text = resp.text.lower()
                if "service is operating normally" not in text or "issue" in text:
                    # Try to parse any active events from the page
                    pass  # HTML parsing complex - rely on news instead
    except Exception as e:
        logger.debug("AWS status check: %s", e)

    # Try RSS feed for service events
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            # AWS publishes RSS for specific services
            for region_code, region_name, lat, lon, country in [
                ("me-south-1", "AWS Bahrain", 26.07, 50.56, "Bahrain"),
                ("me-central-1", "AWS UAE", 24.45, 54.65, "UAE"),
            ]:
                url = f"https://status.aws.amazon.com/rss/ec2-{region_code}.rss"
                try:
                    resp = await client.get(url)
                    if resp.status_code == 200 and "<item>" in resp.text:
                        root = ElementTree.fromstring(resp.text)
                        for item in root.iter("item"):
                            title_el = item.find("title")
                            desc_el = item.find("description")
                            pub_el = item.find("pubDate")
                            if title_el is not None and title_el.text:
                                title = html.unescape(title_el.text.strip())
                                desc = html.unescape(desc_el.text.strip()) if desc_el is not None and desc_el.text else ""
                                cause, severity = classify_outage(title, desc)
                                ts = None
                                if pub_el is not None and pub_el.text:
                                    try:
                                        ts = parsedate_to_datetime(pub_el.text.strip())
                                    except Exception:
                                        pass
                                outages.append({
                                    "id": f"aws-{region_code}-{hashlib.md5(title.encode()).hexdigest()[:8]}",
                                    "provider": "AWS",
                                    "service": "EC2",
                                    "region": region_code,
                                    "lat": lat, "lon": lon,
                                    "country": country,
                                    "status": "outage" if "disruption" in title.lower() or "issue" in title.lower() else "degraded",
                                    "title": title,
                                    "description": desc[:300],
                                    "cause": cause,
                                    "severity": severity,
                                    "start_time": ts.isoformat() if ts else None,
                                    "last_update": datetime.now(timezone.utc).isoformat(),
                                    "url": f"https://health.aws.amazon.com/health/status",
                                })
                except Exception:
                    pass
    except Exception as e:
        logger.debug("AWS RSS check: %s", e)

    return outages


async def _fetch_gcp_status() -> list[dict]:
    """Fetch GCP incident data from public incidents JSON."""
    outages = []
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get("https://status.cloud.google.com/incidents.json")
            if resp.status_code == 200:
                incidents = resp.json()
                # Only recent/active incidents
                for inc in incidents[:10]:
                    if inc.get("end") and inc.get("severity") == "low":
                        continue  # Skip resolved low-severity
                    title = inc.get("external_desc", inc.get("service_name", "GCP Incident"))
                    affected = inc.get("affected_products", [])
                    service = affected[0].get("title", "Unknown") if affected else "Multiple"
                    severity_map = {"high": "critical", "medium": "severe", "low": "moderate"}
                    sev = severity_map.get(inc.get("severity", ""), "info")
                    is_active = inc.get("end") is None

                    # Check if this affects ME regions
                    me_regions = ["me-central1", "me-central2", "me-west1"]
                    region_match = False
                    for prod in affected:
                        for loc in prod.get("locations", []):
                            if any(r in loc.lower() for r in me_regions):
                                region_match = True
                                break

                    if is_active or region_match:
                        outages.append({
                            "id": f"gcp-{inc.get('number', 'unk')}",
                            "provider": "GCP",
                            "service": service,
                            "region": "me-central1" if region_match else "global",
                            "lat": 25.29 if region_match else 37.42,
                            "lon": 51.53 if region_match else -122.08,
                            "country": "Qatar" if region_match else "US",
                            "status": "outage" if is_active else "resolved",
                            "title": title[:200],
                            "description": inc.get("status_impact", "")[:300],
                            "cause": "technical",
                            "severity": sev,
                            "start_time": inc.get("begin"),
                            "last_update": inc.get("modified", datetime.now(timezone.utc).isoformat()),
                            "url": f"https://status.cloud.google.com/incidents/{inc.get('number', '')}",
                        })
    except Exception as e:
        logger.debug("GCP status check: %s", e)

    return outages


async def _fetch_infra_news() -> list[dict]:
    """Fetch infrastructure-related news from Google News RSS."""
    all_incidents = []

    async with httpx.AsyncClient(timeout=10.0, follow_redirects=True) as client:
        for query in INFRA_NEWS_QUERIES:
            cache_key = f"infra_news_{query}"
            if cache_key in _infra_cache:
                all_incidents.extend(_infra_cache[cache_key])
                continue

            url = _GOOGLE_NEWS_RSS.format(query=query.replace(" ", "+"))
            try:
                resp = await client.get(url)
                if resp.status_code != 200:
                    continue

                items = []
                root = ElementTree.fromstring(resp.text)
                for item in root.iter("item"):
                    title_el = item.find("title")
                    link_el = item.find("link")
                    pub_el = item.find("pubDate")
                    source_el = item.find("source")

                    if title_el is None or not title_el.text:
                        continue

                    title = html.unescape(title_el.text.strip())
                    url_link = link_el.text.strip() if link_el is not None and link_el.text else ""
                    source_name = source_el.text.strip() if source_el is not None and source_el.text else "News"

                    ts = None
                    if pub_el is not None and pub_el.text:
                        try:
                            ts = parsedate_to_datetime(pub_el.text.strip())
                        except Exception:
                            ts = datetime.now(timezone.utc)

                    provider = _detect_provider(title)
                    country, lat, lon = _detect_region(title)
                    cause, severity = classify_outage(title)

                    item_id = hashlib.md5(title.encode()).hexdigest()[:10]
                    items.append({
                        "id": f"infra-news-{item_id}",
                        "provider": provider,
                        "service": "",
                        "region": "",
                        "lat": lat, "lon": lon,
                        "country": country,
                        "status": "reported",
                        "title": title[:200],
                        "description": f"Source: {source_name}",
                        "cause": cause,
                        "severity": severity,
                        "start_time": ts.isoformat() if ts else None,
                        "last_update": datetime.now(timezone.utc).isoformat(),
                        "url": url_link,
                    })

                _infra_cache[cache_key] = items[:3]
                all_incidents.extend(items[:3])

            except Exception as e:
                logger.debug("Infra news query '%s' failed: %s", query, e)
                continue

    return all_incidents


# ============================================================================
# Public API
# ============================================================================

async def get_infra_outages() -> list[dict]:
    """Get all current infrastructure outages and incidents."""
    cache_key = "all_outages"
    if cache_key in _infra_cache:
        return _infra_cache[cache_key]

    # Fetch from multiple sources concurrently
    import asyncio
    results = await asyncio.gather(
        _fetch_aws_status(),
        _fetch_gcp_status(),
        _fetch_infra_news(),
        return_exceptions=True,
    )

    all_outages = []
    for result in results:
        if isinstance(result, list):
            all_outages.extend(result)
        elif isinstance(result, Exception):
            logger.warning("Infra source failed: %s", result)

    # Deduplicate by title similarity
    seen_titles: set[str] = set()
    unique_outages: list[dict] = []
    for outage in all_outages:
        key = outage["title"].lower()[:50]
        if key not in seen_titles:
            seen_titles.add(key)
            unique_outages.append(outage)

    # Sort by severity (critical first) then recency
    severity_order = {"critical": 0, "severe": 1, "moderate": 2, "info": 3}
    unique_outages.sort(key=lambda o: (severity_order.get(o.get("severity", "info"), 3), o.get("start_time", "") or ""))

    _infra_cache[cache_key] = unique_outages[:50]
    logger.info("Infrastructure monitor: %d incidents found", len(unique_outages))
    return unique_outages[:50]


def get_data_centers() -> list[dict]:
    """Get all monitored data center locations with current status."""
    centers = []
    for dc in DATA_CENTERS:
        centers.append({
            **dc,
            "status": "operational",
            "active_incidents": 0,
        })
    return centers


def get_undersea_cables() -> list[dict]:
    """Get undersea cable landing points with status."""
    cables = []
    for cable in UNDERSEA_CABLES:
        cables.append({
            **cable,
            "status": "operational",
        })
    return cables


async def get_all_infra_status() -> dict:
    """Get complete infrastructure status: data centers, cables, outages."""
    outages = await get_infra_outages()
    centers = get_data_centers()
    cables = get_undersea_cables()

    # Merge outage status into data centers
    for outage in outages:
        provider = outage.get("provider", "")
        region = outage.get("region", "")
        country = outage.get("country", "")
        for dc in centers:
            if dc["provider"] == provider and (dc["region"] == region or dc["country"] == country):
                if outage.get("status") in ("outage", "disrupted"):
                    dc["status"] = "outage"
                elif outage.get("status") == "degraded" and dc["status"] != "outage":
                    dc["status"] = "degraded"
                dc["active_incidents"] = dc.get("active_incidents", 0) + 1

    return {
        "outages": outages,
        "data_centers": centers,
        "cables": cables,
    }
