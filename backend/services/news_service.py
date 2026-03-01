"""
News Service - Fetches Middle East news from GDELT DOC API and provides
curated live news stream URLs for regional coverage.
"""

import hashlib
import logging
from datetime import datetime, timezone

import httpx
from cachetools import TTLCache

from config import settings
from models import LiveFeed, NewsItem

logger = logging.getLogger(__name__)

_news_cache: TTLCache = TTLCache(maxsize=10, ttl=settings.CACHE_TTL_NEWS)


# ============================================================================
# LIVE NEWS FEEDS - Curated YouTube live stream URLs for Middle East coverage
# ============================================================================

_LIVE_FEEDS: dict[str, list[dict]] = {
    "Iraq": [
        {
            "country": "Iraq",
            "channel_name": "Al Jazeera Arabic",
            "stream_url": "https://www.youtube.com/c/abordered/live",
            "language": "Arabic",
            "category": "news",
        },
        {
            "country": "Iraq",
            "channel_name": "Rudaw English",
            "stream_url": "https://www.youtube.com/@RudawEnglish/live",
            "language": "English",
            "category": "news",
        },
    ],
    "Syria": [
        {
            "country": "Syria",
            "channel_name": "Syria TV",
            "stream_url": "https://www.youtube.com/@sabordered/live",
            "language": "Arabic",
            "category": "news",
        },
        {
            "country": "Syria",
            "channel_name": "Al Jazeera English",
            "stream_url": "https://www.youtube.com/@AlJazeeraEnglish/live",
            "language": "English",
            "category": "news",
        },
    ],
    "Palestine": [
        {
            "country": "Palestine",
            "channel_name": "Al Jazeera English - Gaza Live",
            "stream_url": "https://www.youtube.com/@AlJazeeraEnglish/live",
            "language": "English",
            "category": "news",
        },
        {
            "country": "Palestine",
            "channel_name": "Palestine TV",
            "stream_url": "https://www.youtube.com/@PalestineTV/live",
            "language": "Arabic",
            "category": "news",
        },
    ],
    "Israel": [
        {
            "country": "Israel",
            "channel_name": "i24NEWS English",
            "stream_url": "https://www.youtube.com/@i24NEWSEnglish/live",
            "language": "English",
            "category": "news",
        },
        {
            "country": "Israel",
            "channel_name": "Kan 11",
            "stream_url": "https://www.youtube.com/@kan11/live",
            "language": "Hebrew",
            "category": "news",
        },
    ],
    "Iran": [
        {
            "country": "Iran",
            "channel_name": "Iran International",
            "stream_url": "https://www.youtube.com/@IranIntl/live",
            "language": "Persian",
            "category": "news",
        },
        {
            "country": "Iran",
            "channel_name": "BBC Persian",
            "stream_url": "https://www.youtube.com/@bbcpersian/live",
            "language": "Persian",
            "category": "news",
        },
    ],
    "Yemen": [
        {
            "country": "Yemen",
            "channel_name": "Al Arabiya",
            "stream_url": "https://www.youtube.com/@AlArabiya/live",
            "language": "Arabic",
            "category": "news",
        },
        {
            "country": "Yemen",
            "channel_name": "Yemen Shabab TV",
            "stream_url": "https://www.youtube.com/@YemenShabab/live",
            "language": "Arabic",
            "category": "news",
        },
    ],
    "Lebanon": [
        {
            "country": "Lebanon",
            "channel_name": "MTV Lebanon",
            "stream_url": "https://www.youtube.com/@mabordered/live",
            "language": "Arabic",
            "category": "news",
        },
        {
            "country": "Lebanon",
            "channel_name": "LBCI Lebanon",
            "stream_url": "https://www.youtube.com/@LBCI/live",
            "language": "Arabic",
            "category": "news",
        },
    ],
    "Saudi Arabia": [
        {
            "country": "Saudi Arabia",
            "channel_name": "Al Arabiya",
            "stream_url": "https://www.youtube.com/@AlArabiya/live",
            "language": "Arabic",
            "category": "news",
        },
        {
            "country": "Saudi Arabia",
            "channel_name": "Saudi TV",
            "stream_url": "https://www.youtube.com/@SaudiTVNews/live",
            "language": "Arabic",
            "category": "news",
        },
    ],
    "UAE": [
        {
            "country": "UAE",
            "channel_name": "Sky News Arabia",
            "stream_url": "https://www.youtube.com/@skabordered/live",
            "language": "Arabic",
            "category": "news",
        },
        {
            "country": "UAE",
            "channel_name": "Al Ain News",
            "stream_url": "https://www.youtube.com/@AlAinNews/live",
            "language": "Arabic",
            "category": "news",
        },
    ],
    "Turkey": [
        {
            "country": "Turkey",
            "channel_name": "TRT World",
            "stream_url": "https://www.youtube.com/@tabordered/live",
            "language": "English",
            "category": "news",
        },
        {
            "country": "Turkey",
            "channel_name": "Anadolu Agency",
            "stream_url": "https://www.youtube.com/@aabordered/live",
            "language": "Turkish",
            "category": "news",
        },
    ],
    "Egypt": [
        {
            "country": "Egypt",
            "channel_name": "Al Jazeera Mubasher",
            "stream_url": "https://www.youtube.com/@AJMubasher/live",
            "language": "Arabic",
            "category": "news",
        },
        {
            "country": "Egypt",
            "channel_name": "Extra News",
            "stream_url": "https://www.youtube.com/@eXtraNews/live",
            "language": "Arabic",
            "category": "news",
        },
    ],
    "Jordan": [
        {
            "country": "Jordan",
            "channel_name": "Roya News",
            "stream_url": "https://www.youtube.com/@RoyaNews/live",
            "language": "Arabic",
            "category": "news",
        },
    ],
    "Global": [
        {
            "country": "Global",
            "channel_name": "Al Jazeera English",
            "stream_url": "https://www.youtube.com/@AlJazeeraEnglish/live",
            "language": "English",
            "category": "news",
        },
        {
            "country": "Global",
            "channel_name": "France 24 English",
            "stream_url": "https://www.youtube.com/@FRANCE24English/live",
            "language": "English",
            "category": "news",
        },
        {
            "country": "Global",
            "channel_name": "DW News",
            "stream_url": "https://www.youtube.com/@DWNews/live",
            "language": "English",
            "category": "news",
        },
        {
            "country": "Global",
            "channel_name": "BBC News",
            "stream_url": "https://www.youtube.com/@BBCNews/live",
            "language": "English",
            "category": "news",
        },
    ],
}


def _generate_id(text: str) -> str:
    """Generate deterministic short ID."""
    return hashlib.md5(text.encode("utf-8", errors="replace")).hexdigest()[:12]


async def get_news(country: str | None = None) -> list[NewsItem]:
    """
    Fetch Middle East news from GDELT DOC API.

    Args:
        country: Optional country filter for news results.

    Returns:
        List of NewsItem models.
    """
    cache_key = f"news_{country or 'all'}"
    if cache_key in _news_cache:
        logger.debug("Returning cached news for %s", country or "all")
        return _news_cache[cache_key]

    news_items: list[NewsItem] = []

    # Build query based on country filter
    if country:
        query = f"{country} (conflict OR politics OR military OR security OR crisis)"
    else:
        query = "middleeast (conflict OR politics OR military OR security OR crisis OR war OR diplomacy)"

    params = {
        "query": query,
        "mode": "artlist",
        "maxrecords": "50",
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
                source_domain = article.get("domain", "")
                seendate = article.get("seendate", "")
                socialimage = article.get("socialimage", "")
                language = article.get("language", "")
                source_country = article.get("sourcecountry", "")

                if not title:
                    continue

                # Parse date
                try:
                    if seendate and len(seendate) >= 8:
                        published = datetime.strptime(
                            seendate[:14] if len(seendate) >= 14 else seendate[:8],
                            "%Y%m%d%H%M%S" if len(seendate) >= 14 else "%Y%m%d"
                        ).replace(tzinfo=timezone.utc)
                    else:
                        published = datetime.now(timezone.utc)
                except ValueError:
                    published = datetime.now(timezone.utc)

                # Extract keywords from title
                keywords = _extract_keywords(title)

                # Determine sentiment from tone
                tone = article.get("tone", None)
                sentiment = "neutral"
                if tone is not None:
                    try:
                        tone_val = float(tone.split(",")[0]) if isinstance(tone, str) and "," in tone else float(tone)
                        if tone_val < -3:
                            sentiment = "negative"
                        elif tone_val > 3:
                            sentiment = "positive"
                    except (ValueError, TypeError):
                        pass

                news_id = _generate_id(f"{url}{seendate}")

                news_items.append(NewsItem(
                    id=f"news-{news_id}",
                    title=title,
                    description=f"Source: {source_domain} | Language: {language}",
                    url=url,
                    image_url=socialimage or "",
                    source=source_domain,
                    country=source_country or (country or ""),
                    published_at=published,
                    keywords=keywords,
                    sentiment=sentiment,
                ))

    except httpx.HTTPStatusError as e:
        logger.error("GDELT News HTTP error: %s", e.response.status_code)
    except httpx.RequestError as e:
        logger.error("GDELT News request error: %s", str(e))
    except Exception as e:
        logger.error("GDELT News unexpected error: %s", str(e))

    _news_cache[cache_key] = news_items
    logger.info("Fetched %d news items for %s", len(news_items), country or "all")
    return news_items


def get_live_feeds(country: str | None = None) -> list[LiveFeed]:
    """
    Return curated live news stream URLs.

    Args:
        country: Optional country filter. If None, returns all feeds.

    Returns:
        List of LiveFeed models with stream URLs.
    """
    if country:
        # Try exact match first, then case-insensitive
        feeds_data = _LIVE_FEEDS.get(country)
        if not feeds_data:
            country_lower = country.lower()
            for key, val in _LIVE_FEEDS.items():
                if key.lower() == country_lower:
                    feeds_data = val
                    break

        if feeds_data:
            return [LiveFeed(**feed) for feed in feeds_data]
        return []

    # Return all feeds
    all_feeds: list[LiveFeed] = []
    for feeds_list in _LIVE_FEEDS.values():
        for feed in feeds_list:
            all_feeds.append(LiveFeed(**feed))
    return all_feeds


def _extract_keywords(title: str) -> list[str]:
    """Extract relevant keywords from article title."""
    keyword_set = {
        "missile", "rocket", "airstrike", "bombing", "attack", "military",
        "conflict", "war", "ceasefire", "peace", "nuclear", "sanctions",
        "diplomacy", "humanitarian", "refugees", "casualties", "drone",
        "strike", "explosion", "terrorism", "insurgency", "coup",
        "election", "protest", "demonstration", "crisis", "escalation",
        "iran", "israel", "gaza", "ukraine", "syria", "iraq", "yemen",
        "lebanon", "hezbollah", "hamas", "houthi", "isis", "taliban",
        "saudi", "turkey", "egypt", "russia", "nato", "pentagon",
        "oil", "energy", "pipeline", "sanctions", "iaea", "un",
    }
    title_words = set(title.lower().split())
    matched = [kw for kw in keyword_set if kw in title_words]
    return sorted(matched)[:10]
