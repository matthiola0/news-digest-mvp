"""RSS feed collector – handles Twitter/Nitter/RSSHub and AI news feeds."""
from __future__ import annotations

import logging
import time
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from typing import Optional

import feedparser
import requests

from src import config
from src.collectors.base import NewsItem

logger = logging.getLogger(__name__)


def _parse_published(entry) -> Optional[datetime]:
    """Extract a timezone-aware datetime from a feedparser entry, best-effort."""
    for attr in ("published_parsed", "updated_parsed", "created_parsed"):
        val = getattr(entry, attr, None)
        if val:
            try:
                return datetime(*val[:6], tzinfo=timezone.utc)
            except Exception:
                pass
    for attr in ("published", "updated"):
        raw = getattr(entry, attr, None)
        if raw:
            try:
                return parsedate_to_datetime(raw)
            except Exception:
                pass
    return None


def _clean_description(text: str, max_chars: int) -> str:
    import html
    import re

    text = html.unescape(text)
    text = re.sub(r"<[^>]+>", " ", text)        # strip HTML tags
    text = re.sub(r"\s+", " ", text).strip()
    return text[:max_chars] + "…" if len(text) > max_chars else text


def fetch_rss_feed(
    url: str,
    source_label: str,
    max_items: int = 10,
    max_desc_chars: int = 300,
) -> list[NewsItem]:
    """Fetch and parse a single RSS/Atom feed URL."""
    logger.info("Fetching RSS feed: %s", url)
    try:
        # feedparser can handle the URL directly, but we pre-fetch so we can set
        # a proper User-Agent and timeout.
        resp = requests.get(
            url,
            headers=config.REQUEST_HEADERS,
            timeout=config.REQUEST_TIMEOUT,
        )
        resp.raise_for_status()
        feed = feedparser.parse(resp.content)
    except Exception as exc:
        logger.warning("Failed to fetch %s: %s", url, exc)
        return []

    items: list[NewsItem] = []
    for entry in feed.entries[:max_items]:
        title = getattr(entry, "title", "").strip() or "(no title)"
        link = getattr(entry, "link", "").strip() or url
        summary = (
            getattr(entry, "summary", "")
            or getattr(entry, "description", "")
            or getattr(entry, "content", [{}])[0].get("value", "")
        )
        items.append(
            NewsItem(
                title=title,
                url=link,
                source=source_label,
                description=_clean_description(summary, max_desc_chars),
                published=_parse_published(entry),
            )
        )
    logger.info("  → %d items from %s", len(items), source_label)
    return items


def collect_twitter_feeds() -> list[NewsItem]:
    """Collect items from configured Twitter/Nitter/RSSHub RSS feeds."""
    feeds = config.TWITTER_RSS_FEEDS
    if not feeds:
        logger.info("No TWITTER_RSS_FEEDS configured; skipping Twitter section.")
        return []

    all_items: list[NewsItem] = []
    for url in feeds:
        label = _label_from_url(url, prefix="Twitter")
        items = fetch_rss_feed(
            url,
            label,
            max_items=config.MAX_ITEMS_PER_SOURCE,
            max_desc_chars=config.MAX_DESCRIPTION_CHARS,
        )
        all_items.extend(items)
        time.sleep(0.5)  # be polite
    return all_items


def collect_ai_news_feeds() -> list[NewsItem]:
    """Collect items from AI news RSS feeds."""
    all_items: list[NewsItem] = []
    for url in config.AI_NEWS_RSS_FEEDS:
        label = _label_from_url(url, prefix="AI News")
        items = fetch_rss_feed(
            url,
            label,
            max_items=config.MAX_ITEMS_PER_SOURCE,
            max_desc_chars=config.MAX_DESCRIPTION_CHARS,
        )
        all_items.extend(items)
        time.sleep(0.5)
    return all_items


def _label_from_url(url: str, prefix: str = "") -> str:
    """Derive a human-readable source label from a feed URL."""
    from urllib.parse import urlparse
    host = urlparse(url).netloc.lstrip("www.").lstrip("rss.")
    return f"{prefix} / {host}" if prefix else host
