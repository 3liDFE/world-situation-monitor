"""
Google News RSS Service - Fetches real-time news from Google News RSS feeds.
Primary source for breaking conflict/military news when GDELT is unavailable.
"""

import hashlib
import html
import logging
import re
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from typing import Optional

import httpx
from cachetools import TTLCache

logger = logging.getLogger(__name__)

_news_cache: TTLCache = TTLCache(maxsize=20, ttl=60)  # 60 second cache for live updates

# Conflict-focused search queries - GLOBAL coverage
CONFLICT_QUERIES = [
    # Middle East (primary focus)
    "Iran attack missile drone strike",
    "Israel military strike airstrike",
    "Houthi Red Sea attack shipping",
    "Syria airstrike bombing military",
    "Gaza military operation strike",
    "Lebanon Hezbollah rocket missile",
    "Iraq militia attack base",
    "Yemen Saudi coalition strike",
    # Eastern Europe
    "Ukraine Russia war missile drone attack",
    "Ukraine frontline military strike today",
    # Africa
    "Sudan war conflict military airstrike",
    "Somalia al-Shabaab military attack",
    "Libya conflict military forces",
    # Asia-Pacific
    "Taiwan China military tensions",
    "North Korea missile launch test",
    "Myanmar conflict military operation",
    # Global military/security
    "NATO military deployment forces",
    "global conflict breaking military news",
]

# Location keyword to coordinates mapping
LOCATION_COORDS: dict[str, tuple[float, float]] = {
    # Cities & Regions
    "tehran": (35.69, 51.39), "isfahan": (32.65, 51.68), "tabriz": (38.08, 46.29),
    "shiraz": (29.59, 52.58), "natanz": (33.51, 51.92), "bushehr": (28.97, 50.84),
    "bandar abbas": (27.19, 56.27), "semnan": (35.57, 53.39), "kharg island": (29.24, 50.32),
    "tel aviv": (32.09, 34.78), "jerusalem": (31.77, 35.23), "haifa": (32.79, 34.99),
    "beersheba": (31.25, 34.79), "ashkelon": (31.67, 34.57), "sderot": (31.52, 34.60),
    "gaza": (31.42, 34.36), "gaza strip": (31.42, 34.36), "khan younis": (31.35, 34.30),
    "rafah": (31.30, 34.24), "jabalia": (31.53, 34.48), "deir al-balah": (31.42, 34.35),
    "nuseirat": (31.45, 34.39),
    "beirut": (33.89, 35.50), "tyre": (33.27, 35.20), "nabatieh": (33.38, 35.48),
    "bekaa": (33.85, 36.00), "bekaa valley": (33.85, 36.00), "baalbek": (34.01, 36.21),
    "damascus": (33.51, 36.28), "aleppo": (36.20, 37.16), "idlib": (35.93, 36.63),
    "deir ez-zor": (35.33, 40.14), "homs": (34.73, 36.72), "latakia": (35.52, 35.79),
    "tartus": (34.90, 35.89), "raqqa": (35.95, 39.01), "al-bukamal": (34.47, 40.34),
    "baghdad": (33.31, 44.37), "erbil": (36.19, 44.01), "basra": (30.51, 47.78),
    "mosul": (36.34, 43.14), "kirkuk": (35.47, 44.39), "al-tanf": (33.50, 38.67),
    "ain al-asad": (33.79, 42.44), "sulaymaniyah": (35.56, 45.44),
    "sanaa": (15.37, 44.19), "aden": (12.78, 45.02), "hodeidah": (14.80, 42.95),
    "marib": (15.46, 45.33), "taiz": (13.58, 44.02),
    "riyadh": (24.71, 46.68), "jeddah": (21.54, 39.17), "jizan": (16.89, 42.55),
    "najran": (17.49, 44.13), "dhahran": (26.27, 50.21),
    "abu dhabi": (24.45, 54.38), "dubai": (25.20, 55.27), "al dhafra": (24.25, 54.55),
    "doha": (25.29, 51.53), "al udeid": (25.12, 51.32),
    "manama": (26.23, 50.59), "kuwait city": (29.38, 47.98),
    "amman": (31.95, 35.93), "muscat": (23.59, 58.38),
    "ankara": (39.93, 32.86), "incirlik": (37.00, 35.43),
    "cairo": (30.04, 31.24), "sinai": (29.50, 33.80),
    "kabul": (34.56, 69.21), "islamabad": (33.69, 73.04),
    # Water bodies & Straits
    "red sea": (20.00, 38.50), "bab el-mandeb": (12.60, 43.30),
    "strait of hormuz": (26.56, 56.25), "persian gulf": (27.00, 51.00),
    "gulf of aden": (12.50, 47.00), "gulf of oman": (24.50, 58.50),
    "mediterranean": (34.00, 30.00), "suez canal": (30.58, 32.27),
    # Countries (fallback coordinates - capital/center)
    "iran": (32.43, 53.69), "israel": (31.05, 34.85),
    "palestine": (31.90, 35.20), "lebanon": (33.85, 35.86),
    "syria": (34.80, 38.00), "iraq": (33.22, 43.68),
    "yemen": (15.55, 48.52), "saudi arabia": (23.89, 45.08),
    "uae": (24.47, 54.37), "united arab emirates": (24.47, 54.37),
    "qatar": (25.35, 51.18), "bahrain": (26.07, 50.55),
    "kuwait": (29.31, 47.48), "oman": (21.47, 55.98),
    "jordan": (31.24, 36.51), "egypt": (26.82, 30.80),
    "turkey": (38.96, 35.24), "pakistan": (30.38, 69.35),
    "afghanistan": (33.94, 67.71), "libya": (26.34, 17.23),
    "sudan": (12.86, 30.22), "ukraine": (48.38, 31.17),
    "crimea": (45.30, 34.10), "russia": (61.52, 105.32),
    # Additional global locations
    "kyiv": (50.45, 30.52), "kharkiv": (49.99, 36.23), "odesa": (46.48, 30.73),
    "donetsk": (48.00, 37.80), "zaporizhzhia": (47.84, 35.14), "kherson": (46.64, 32.62),
    "moscow": (55.76, 37.62), "kursk": (51.73, 36.19), "belgorod": (50.60, 36.59),
    "khartoum": (15.59, 32.53), "darfur": (13.50, 25.00), "port sudan": (19.62, 37.22),
    "mogadishu": (2.05, 45.32), "somalia": (5.15, 46.20),
    "tripoli libya": (32.90, 13.19), "benghazi": (32.12, 20.09),
    "taipei": (25.03, 121.57), "taiwan": (23.70, 120.96),
    "pyongyang": (39.02, 125.75), "north korea": (40.34, 127.51),
    "south korea": (35.91, 127.77), "seoul": (37.57, 126.98),
    "myanmar": (19.76, 96.08), "naypyidaw": (19.76, 96.07), "mandalay": (21.97, 96.08),
    "china": (35.86, 104.20), "beijing": (39.90, 116.40), "south china sea": (12.00, 114.00),
    "niger": (17.61, 8.08), "mali": (17.57, -4.00), "burkina faso": (12.37, -1.52),
    "ethiopia": (9.15, 40.49), "congo": (-4.44, 15.27), "mozambique": (-15.59, 35.24),
    "nato": (50.88, 4.32), "brussels": (50.85, 4.35), "london": (51.51, -0.13),
    "washington": (38.91, -77.04), "pentagon": (38.87, -77.06),
    "japan": (36.20, 138.25), "india": (20.59, 78.96), "new delhi": (28.61, 77.21),
    "philippines": (12.88, 121.77),
}

# Event type classification keywords
EVENT_TYPES = {
    "missile": ["missile", "ballistic", "cruise missile", "icbm", "scud", "shahab",
                 "fateh", "emad", "patriot", "s-300", "s-400", "thaad", "arrow"],
    "drone": ["drone", "uav", "ucav", "shahed", "qasef", "unmanned", "one-way attack"],
    "airstrike": ["airstrike", "air strike", "bombing", "bombard", "sortie", "f-35",
                   "f-16", "b-52", "b-2", "fighter jet", "warplane"],
    "rocket": ["rocket", "grad", "katyusha", "qassam", "iron dome"],
    "naval": ["ship", "vessel", "navy", "destroyer", "carrier", "frigate", "submarine",
              "maritime", "anti-ship", "torpedo"],
    "artillery": ["artillery", "shelling", "mortar", "howitzer", "tank fire"],
    "interception": ["intercept", "shot down", "neutralize", "destroy", "iron dome",
                      "patriot", "defend", "air defense"],
}


def _generate_id(text: str) -> str:
    return hashlib.md5(text.encode("utf-8", errors="replace")).hexdigest()[:12]


# ============================================================================
# Importance Scoring - Filter noise, keep only significant intel
# ============================================================================

# High-value news sources (trusted, fast, authoritative)
TIER1_SOURCES = {
    "reuters", "ap news", "associated press", "bbc", "cnn", "al jazeera",
    "the new york times", "the washington post", "the guardian", "france 24",
    "dw", "sky news", "bloomberg", "financial times",
}

# Critical action keywords (highest priority)
CRITICAL_KEYWORDS = [
    "breaking", "just in", "confirmed", "casualties", "killed", "dead",
    "intercepted", "launched", "struck", "explosion", "attacked",
    "declared war", "invaded", "shot down", "emergency", "evacuate",
    "nuclear", "chemical", "biological", "wmd",
]

# High importance keywords
HIGH_KEYWORDS = [
    "missile", "drone strike", "airstrike", "bombing", "rocket",
    "ballistic", "cruise missile", "iron dome", "patriot",
    "ceasefire", "peace deal", "surrender", "offensive",
    "troops deployed", "invasion", "escalation", "retaliation",
    "carrier strike group", "no-fly zone", "blockade",
]

# Medium importance keywords
MEDIUM_KEYWORDS = [
    "military", "conflict", "tensions", "sanctions", "diplomacy",
    "deployment", "exercise", "navy", "air force", "army",
    "intelligence", "surveillance", "reconnaissance",
]

# Noise/low-value patterns to filter out
NOISE_PATTERNS = [
    "opinion:", "editorial:", "analysis:", "podcast:", "review:",
    "what you need to know", "explained:", "how to", "subscribe",
    "sign up", "newsletter", "comment", "live blog",
]


def score_importance(article: dict) -> int:
    """
    Score article importance (0-100). Higher = more important.
    Factors: keywords, source quality, recency, event type.
    """
    score = 0
    title = article.get("title", "").lower()
    source = article.get("source", "").lower()

    # Noise filter - immediately disqualify
    for pattern in NOISE_PATTERNS:
        if pattern in title:
            return 0

    # Source quality (0-25)
    if any(s in source for s in TIER1_SOURCES):
        score += 25
    elif source:
        score += 10

    # Critical keywords (0-35)
    critical_matches = sum(1 for kw in CRITICAL_KEYWORDS if kw in title)
    score += min(critical_matches * 12, 35)

    # High keywords (0-20)
    high_matches = sum(1 for kw in HIGH_KEYWORDS if kw in title)
    score += min(high_matches * 7, 20)

    # Medium keywords (0-10)
    medium_matches = sum(1 for kw in MEDIUM_KEYWORDS if kw in title)
    score += min(medium_matches * 4, 10)

    # Has location (geolocatable = more actionable intel)
    if article.get("lat") is not None:
        score += 5

    # Event type bonus
    event_type = article.get("event_type", "")
    if event_type in ("missile", "airstrike", "interception"):
        score += 5
    elif event_type in ("drone", "rocket"):
        score += 3

    return min(score, 100)


def _infer_location(text: str) -> Optional[tuple[float, float, str]]:
    """Extract the most specific location from text. Returns (lat, lon, location_name)."""
    text_lower = text.lower()
    # Try most specific (cities) first, then regions, then countries
    # Sort by name length descending so "khan younis" matches before "khan"
    sorted_locations = sorted(LOCATION_COORDS.keys(), key=len, reverse=True)
    for loc in sorted_locations:
        if loc in text_lower:
            lat, lon = LOCATION_COORDS[loc]
            return lat, lon, loc.title()
    return None


def _classify_event(text: str) -> str:
    """Classify event type from headline text."""
    text_lower = text.lower()
    for event_type, keywords in EVENT_TYPES.items():
        for kw in keywords:
            if kw in text_lower:
                return event_type
    return "military"


def _extract_status(text: str) -> str:
    """Extract event status from text."""
    text_lower = text.lower()
    if any(w in text_lower for w in ["intercept", "shot down", "destroy", "neutraliz", "defended", "iron dome block"]):
        return "intercepted"
    if any(w in text_lower for w in ["confirmed", "killed", "dead", "casualties", "struck", "hit target"]):
        return "confirmed"
    return "reported"


def _parse_rss_date(date_str: str) -> datetime:
    """Parse RSS date string."""
    try:
        return parsedate_to_datetime(date_str)
    except Exception:
        return datetime.now(timezone.utc)


async def fetch_conflict_news(max_articles: int = 200) -> list[dict]:
    """
    Fetch real conflict/military news from Google News RSS.
    Returns parsed articles with extracted locations and event types.
    """
    cache_key = "conflict_news"
    if cache_key in _news_cache:
        return _news_cache[cache_key]

    all_articles: list[dict] = []
    seen_titles: set[str] = set()

    async with httpx.AsyncClient(timeout=15.0, follow_redirects=True) as client:
        for query in CONFLICT_QUERIES:
            try:
                response = await client.get(
                    "https://news.google.com/rss/search",
                    params={"q": query, "hl": "en-US", "gl": "US", "ceid": "US:en"},
                )
                if response.status_code != 200:
                    continue

                rss_text = response.text

                # Parse RSS items
                items = re.findall(
                    r"<item>(.*?)</item>", rss_text, re.DOTALL
                )

                for item_xml in items:
                    # Extract title
                    title_match = re.search(
                        r"<title><!\[CDATA\[(.*?)\]\]></title>|<title>(.*?)</title>",
                        item_xml,
                    )
                    if not title_match:
                        continue
                    title = html.unescape(title_match.group(1) or title_match.group(2) or "")

                    # Skip Google News meta titles
                    if title == "Google News" or not title:
                        continue

                    # Deduplicate by title
                    title_key = title.lower().strip()[:80]
                    if title_key in seen_titles:
                        continue
                    seen_titles.add(title_key)

                    # Extract link
                    link_match = re.search(r"<link/>\s*(https?://\S+)", item_xml)
                    link = link_match.group(1).strip() if link_match else ""

                    # Extract date
                    date_match = re.search(r"<pubDate>(.*?)</pubDate>", item_xml)
                    pub_date = _parse_rss_date(date_match.group(1)) if date_match else datetime.now(timezone.utc)

                    # Extract source
                    source_match = re.search(r"<source[^>]*>(.*?)</source>", item_xml)
                    source = html.unescape(source_match.group(1)) if source_match else ""

                    # Extract location from title
                    location = _infer_location(title)

                    # Classify event
                    event_type = _classify_event(title)
                    status = _extract_status(title)

                    article = {
                        "id": _generate_id(f"gnews-{title[:50]}-{pub_date.isoformat()}"),
                        "title": title,
                        "url": link,
                        "source": source,
                        "published_at": pub_date.isoformat(),
                        "event_type": event_type,
                        "status": status,
                        "query": query,
                    }

                    if location:
                        article["lat"] = location[0]
                        article["lon"] = location[1]
                        article["location_name"] = location[2]

                    # Score importance
                    article["importance"] = score_importance(article)

                    all_articles.append(article)

            except Exception as e:
                logger.warning("Google News query '%s' failed: %s", query, str(e))

    # Filter out noise (importance score 0)
    all_articles = [a for a in all_articles if a.get("importance", 0) > 0]

    # Sort by date (newest first) - importance is used as filter, not sort
    all_articles.sort(key=lambda a: a.get("published_at", ""), reverse=True)

    # Limit
    all_articles = all_articles[:max_articles]

    _news_cache[cache_key] = all_articles
    logger.info("Fetched %d quality-filtered conflict articles from Google News", len(all_articles))
    return all_articles


async def fetch_breaking_news(max_articles: int = 50) -> list[dict]:
    """Fetch general breaking Middle East news."""
    cache_key = "breaking_news"
    if cache_key in _news_cache:
        return _news_cache[cache_key]

    articles: list[dict] = []
    seen: set[str] = set()

    queries = [
        "Middle East breaking news today",
        "Iran war latest",
        "Israel Gaza Lebanon latest",
        "Ukraine Russia war latest news",
        "global military conflict breaking news",
        "Africa conflict war latest",
        "Asia Pacific military tensions",
    ]

    async with httpx.AsyncClient(timeout=15.0, follow_redirects=True) as client:
        for query in queries:
            try:
                response = await client.get(
                    "https://news.google.com/rss/search",
                    params={"q": query, "hl": "en-US", "gl": "US", "ceid": "US:en"},
                )
                if response.status_code != 200:
                    continue

                items = re.findall(r"<item>(.*?)</item>", response.text, re.DOTALL)

                for item_xml in items:
                    title_match = re.search(
                        r"<title><!\[CDATA\[(.*?)\]\]></title>|<title>(.*?)</title>",
                        item_xml,
                    )
                    if not title_match:
                        continue
                    title = html.unescape(title_match.group(1) or title_match.group(2) or "")
                    if title == "Google News" or not title:
                        continue
                    key = title.lower()[:80]
                    if key in seen:
                        continue
                    seen.add(key)

                    link_match = re.search(r"<link/>\s*(https?://\S+)", item_xml)
                    link = link_match.group(1).strip() if link_match else ""
                    date_match = re.search(r"<pubDate>(.*?)</pubDate>", item_xml)
                    pub_date = _parse_rss_date(date_match.group(1)) if date_match else datetime.now(timezone.utc)
                    source_match = re.search(r"<source[^>]*>(.*?)</source>", item_xml)
                    source = html.unescape(source_match.group(1)) if source_match else ""

                    location = _infer_location(title)

                    art = {
                        "id": _generate_id(f"gnews-break-{title[:50]}"),
                        "title": title,
                        "url": link,
                        "source": source,
                        "published_at": pub_date.isoformat(),
                        "country": location[2] if location else "",
                        "image_url": "",
                        "keywords": [],
                        "sentiment": "negative" if any(
                            w in title.lower()
                            for w in ["attack", "kill", "dead", "strike", "bomb", "war"]
                        ) else "neutral",
                    }
                    art["importance"] = score_importance(art)
                    if art["importance"] > 0:
                        articles.append(art)

            except Exception as e:
                logger.warning("Breaking news query '%s' failed: %s", query, str(e))

    articles.sort(key=lambda a: a.get("published_at", ""), reverse=True)
    articles = articles[:max_articles]

    _news_cache[cache_key] = articles
    logger.info("Fetched %d quality-filtered breaking news articles", len(articles))
    return articles
