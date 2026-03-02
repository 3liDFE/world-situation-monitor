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

# Live feeds using direct YouTube video embeds (known 24/7 live streams)
# These use direct YouTube video IDs for channels with confirmed 24/7 streams
_LIVE_FEEDS: dict[str, list[dict]] = {
    "Global": [
        {
            "country": "Global",
            "channel_name": "Al Jazeera English - LIVE",
            "stream_url": "https://www.youtube.com/watch?v=gCNeDWCI0vo",
            "embed_id": "gCNeDWCI0vo",
            "language": "English",
            "category": "news",
        },
        {
            "country": "Global",
            "channel_name": "France 24 English - LIVE",
            "stream_url": "https://www.youtube.com/watch?v=h3MuIUNCCzI",
            "embed_id": "h3MuIUNCCzI",
            "language": "English",
            "category": "news",
        },
        {
            "country": "Global",
            "channel_name": "DW News - LIVE",
            "stream_url": "https://www.youtube.com/watch?v=GE_SfNVNyqo",
            "embed_id": "GE_SfNVNyqo",
            "language": "English",
            "category": "news",
        },
        {
            "country": "Global",
            "channel_name": "TRT World - LIVE",
            "stream_url": "https://www.youtube.com/watch?v=CV5Fooi8YJE",
            "embed_id": "CV5Fooi8YJE",
            "language": "English",
            "category": "news",
        },
        {
            "country": "Global",
            "channel_name": "WION - LIVE",
            "stream_url": "https://www.youtube.com/watch?v=iuxPTliuqQg",
            "embed_id": "iuxPTliuqQg",
            "language": "English",
            "category": "news",
        },
    ],
    "Palestine": [
        {
            "country": "Palestine",
            "channel_name": "Al Jazeera English - LIVE",
            "stream_url": "https://www.youtube.com/watch?v=gCNeDWCI0vo",
            "embed_id": "gCNeDWCI0vo",
            "language": "English",
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
    ],
    "Iran": [
        {
            "country": "Iran",
            "channel_name": "Iran International",
            "stream_url": "https://www.youtube.com/@IranIntl/live",
            "language": "Persian",
            "category": "news",
        },
    ],
    "Iraq": [
        {
            "country": "Iraq",
            "channel_name": "Al Jazeera Arabic - LIVE",
            "stream_url": "https://www.youtube.com/watch?v=bNyUyrR0PHo",
            "embed_id": "bNyUyrR0PHo",
            "language": "Arabic",
            "category": "news",
        },
    ],
    "Syria": [
        {
            "country": "Syria",
            "channel_name": "Al Jazeera English - LIVE",
            "stream_url": "https://www.youtube.com/watch?v=gCNeDWCI0vo",
            "embed_id": "gCNeDWCI0vo",
            "language": "English",
            "category": "news",
        },
    ],
    "Yemen": [
        {
            "country": "Yemen",
            "channel_name": "Al Arabiya - LIVE",
            "stream_url": "https://www.youtube.com/watch?v=1Ql7yKDQrSs",
            "embed_id": "1Ql7yKDQrSs",
            "language": "Arabic",
            "category": "news",
        },
    ],
    "Lebanon": [
        {
            "country": "Lebanon",
            "channel_name": "Al Jazeera English - LIVE",
            "stream_url": "https://www.youtube.com/watch?v=gCNeDWCI0vo",
            "embed_id": "gCNeDWCI0vo",
            "language": "English",
            "category": "news",
        },
    ],
    "Saudi Arabia": [
        {
            "country": "Saudi Arabia",
            "channel_name": "Sky News Arabia - LIVE",
            "stream_url": "https://www.youtube.com/watch?v=XHD4ncYHzFk",
            "embed_id": "XHD4ncYHzFk",
            "language": "Arabic",
            "category": "news",
        },
    ],
    "UAE": [
        {
            "country": "UAE",
            "channel_name": "Sky News Arabia - LIVE",
            "stream_url": "https://www.youtube.com/watch?v=XHD4ncYHzFk",
            "embed_id": "XHD4ncYHzFk",
            "language": "Arabic",
            "category": "news",
        },
    ],
    "Turkey": [
        {
            "country": "Turkey",
            "channel_name": "TRT World - LIVE",
            "stream_url": "https://www.youtube.com/watch?v=CV5Fooi8YJE",
            "embed_id": "CV5Fooi8YJE",
            "language": "English",
            "category": "news",
        },
    ],
    "Egypt": [
        {
            "country": "Egypt",
            "channel_name": "France 24 English - LIVE",
            "stream_url": "https://www.youtube.com/watch?v=h3MuIUNCCzI",
            "embed_id": "h3MuIUNCCzI",
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
    Fetch real Middle East news from Google News RSS + GDELT.

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
    seen_titles: set[str] = set()

    # PRIMARY: Google News RSS (always available)
    try:
        from services.google_news_service import fetch_breaking_news
        articles = await fetch_breaking_news(max_articles=80)

        for article in articles:
            title = article.get("title", "")
            if not title:
                continue

            title_key = title.lower()[:60]
            if title_key in seen_titles:
                continue
            seen_titles.add(title_key)

            # Country filter
            article_country = article.get("country", "")
            if country and article_country:
                if country.lower() not in article_country.lower() and article_country.lower() not in country.lower():
                    # Check if country is in the title
                    if country.lower() not in title.lower():
                        continue

            pub_date_str = article.get("published_at", "")
            try:
                published = datetime.fromisoformat(pub_date_str.replace("Z", "+00:00")) if pub_date_str else datetime.now(timezone.utc)
            except (ValueError, AttributeError):
                published = datetime.now(timezone.utc)

            keywords = _extract_keywords(title)

            news_items.append(NewsItem(
                id=article.get("id", _generate_id(title)),
                title=title,
                description=f"Source: {article.get('source', '')}",
                url=article.get("url", ""),
                image_url=article.get("image_url", ""),
                source=article.get("source", ""),
                country=article_country or (country or ""),
                published_at=published,
                keywords=keywords,
                sentiment=article.get("sentiment", "neutral"),
            ))
    except Exception as e:
        logger.error("Google News fetch failed: %s", e)

    # SECONDARY: GDELT DOC API (may be unavailable)
    try:
        gdelt_news = await _fetch_gdelt_news(country)
        for item in gdelt_news:
            tk = item.title.lower()[:60]
            if tk not in seen_titles:
                seen_titles.add(tk)
                news_items.append(item)
    except Exception as e:
        logger.debug("GDELT news unavailable: %s", e)

    # Sort by date
    news_items.sort(key=lambda n: n.published_at, reverse=True)
    news_items = news_items[:60]

    _news_cache[cache_key] = news_items
    logger.info("Fetched %d real news items for %s", len(news_items), country or "all")
    return news_items


async def _fetch_gdelt_news(country: str | None = None) -> list[NewsItem]:
    """Try GDELT DOC API for news (may fail on some hosts)."""
    if country:
        query = f"{country} (conflict OR politics OR military OR security)"
    else:
        query = "middleeast (conflict OR war OR military OR crisis)"

    params = {
        "query": query,
        "mode": "artlist",
        "maxrecords": "30",
        "format": "json",
        "sort": "datedesc",
    }

    items: list[NewsItem] = []
    async with httpx.AsyncClient(timeout=10.0) as client:
        response = await client.get(settings.GDELT_DOC_API, params=params)
        response.raise_for_status()
        data = response.json()

        for article in data.get("articles", []):
            title = article.get("title", "")
            if not title:
                continue
            url = article.get("url", "")
            seendate = article.get("seendate", "")
            source_domain = article.get("domain", "")
            socialimage = article.get("socialimage", "")

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

            items.append(NewsItem(
                id=f"gdelt-{_generate_id(f'{url}{seendate}')}",
                title=title,
                description=f"Source: {source_domain}",
                url=url,
                image_url=socialimage or "",
                source=source_domain,
                country=country or "",
                published_at=published,
                keywords=_extract_keywords(title),
                sentiment="neutral",
            ))

    return items


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
