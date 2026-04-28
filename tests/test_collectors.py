"""Unit tests for collectors and digest builder (network-free where possible)."""
from __future__ import annotations

import sys
import os
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# Make sure src is importable from the project root
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.collectors.base import NewsItem
from src.summarizer.simple_summarizer import summarize as simple_summarize
from src.digest.builder import build_digest


# ── NewsItem ─────────────────────────────────────────────────────────────────

def test_news_item_as_dict():
    item = NewsItem(
        title="Test Title",
        url="https://example.com",
        source="Test Source",
        description="A test description.",
        published=datetime(2024, 1, 1, tzinfo=timezone.utc),
    )
    d = item.as_dict()
    assert d["title"] == "Test Title"
    assert d["url"] == "https://example.com"
    assert d["published"] == "2024-01-01T00:00:00+00:00"


def test_news_item_no_published():
    item = NewsItem(title="T", url="u", source="s")
    assert item.as_dict()["published"] is None


# ── Simple summarizer ─────────────────────────────────────────────────────────

def _make_items(n: int, source: str = "Test") -> list[NewsItem]:
    return [
        NewsItem(
            title=f"Item {i}",
            url=f"https://example.com/{i}",
            source=source,
            description=f"Description {i}",
        )
        for i in range(n)
    ]


def test_simple_summarize_all_empty():
    sections = simple_summarize([], [], [])
    assert sections == {}


def test_simple_summarize_github_only():
    gh = _make_items(3, "GitHub Trending")
    sections = simple_summarize([], gh, [])
    assert "GitHub Trending" in sections or "GitHub 熱門趨勢" in sections
    assert "Twitter" not in "\n".join(sections.keys())
    key = "GitHub Trending" if "GitHub Trending" in sections else "GitHub 熱門趨勢"
    assert "Item 0" in sections[key]


def test_simple_summarize_twitter():
    tw = _make_items(2, "Twitter / nitter.net")
    sections = simple_summarize(tw, [], [])
    assert "Twitter / Social" in sections or "社群 / Twitter" in sections


def test_simple_summarize_ai_groups_by_source():
    ai1 = _make_items(2, "AI News / arxiv.org")
    ai2 = _make_items(2, "AI News / openai.com")
    sections = simple_summarize([], [], ai1 + ai2)
    assert "AI News" in sections or "AI 新聞" in sections
    key = "AI News" if "AI News" in sections else "AI 新聞"
    text = sections[key]
    assert "arxiv.org" in text
    assert "openai.com" in text


# ── Digest builder ────────────────────────────────────────────────────────────

def test_build_digest_with_sections():
    sections = {
        "GitHub Trending": "- [repo](url)\n  stars",
        "AI News": "- [post](url)\n  blurb",
    }
    md = build_digest(sections, "GitHub Trending (3), AI News (5)")
    assert "# Daily News Digest" in md or "# 每日新聞摘要" in md
    assert "## GitHub Trending" in md
    assert "## AI News" in md


def test_build_digest_with_llm_key():
    """When 'digest' key is present, body comes through verbatim."""
    sections = {"digest": "## Some LLM section\n\n- bullet"}
    md = build_digest(sections, "test")
    assert "## Some LLM section" in md
    assert "## digest" not in md  # should not double-wrap


# ── RSS collector (mocked network) ───────────────────────────────────────────

def test_rss_collector_handles_network_error():
    """A failing feed URL should return [] without raising."""
    from src.collectors.rss_collector import fetch_rss_feed

    with patch("requests.get", side_effect=ConnectionError("unreachable")):
        result = fetch_rss_feed("https://bad.example/feed.xml", "Test")
    assert result == []


def test_rss_collector_parses_feed(tmp_path):
    """Minimal valid Atom feed is parsed correctly."""
    atom = """<?xml version="1.0"?>
    <feed xmlns="http://www.w3.org/2005/Atom">
      <title>Test Feed</title>
      <entry>
        <title>Hello World</title>
        <link href="https://example.com/1"/>
        <summary>A short summary.</summary>
        <updated>2024-01-15T10:00:00Z</updated>
      </entry>
    </feed>"""

    mock_resp = MagicMock()
    mock_resp.content = atom.encode()
    mock_resp.raise_for_status = MagicMock()

    with patch("requests.get", return_value=mock_resp):
        from src.collectors.rss_collector import fetch_rss_feed
        items = fetch_rss_feed("https://example.com/feed", "Test Feed")

    assert len(items) == 1
    assert items[0].title == "Hello World"
    assert items[0].url == "https://example.com/1"
    assert "short summary" in items[0].description


# ── GitHub Trending (mocked network) ─────────────────────────────────────────

_TRENDING_HTML = """
<html><body>
<article class="Box-row">
  <h2><a href="/owner/repo1">owner / repo1</a></h2>
  <p>A cool repository description.</p>
  <span itemprop="programmingLanguage">Python</span>
  <a href="/owner/repo1/stargazers">1,234</a>
  <span class="d-inline-block float-sm-right">56 stars today</span>
</article>
</body></html>
"""


def test_github_trending_parses_html():
    mock_resp = MagicMock()
    mock_resp.text = _TRENDING_HTML
    mock_resp.raise_for_status = MagicMock()

    with patch("requests.get", return_value=mock_resp):
        from src.collectors.github_trending import collect_github_trending
        items = collect_github_trending()

    assert len(items) >= 1
    assert "owner/repo1" in items[0].title


def test_github_trending_handles_error():
    with patch("requests.get", side_effect=ConnectionError("down")):
        from src.collectors.github_trending import collect_github_trending
        items = collect_github_trending()
    assert items == []
