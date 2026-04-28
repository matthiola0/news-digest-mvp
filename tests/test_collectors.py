"""Unit tests for collectors and digest builder (network-free where possible)."""
from __future__ import annotations

import sys
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# Make sure src is importable from the project root
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.collectors.base import NewsItem
from src.collectors import rss_collector
from src.collectors.rss_collector import _clean_description
from src.summarizer import openai_summarizer, simple_summarizer
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


def test_simple_summarize_zh_twitter_rewrites_to_concise_chinese(monkeypatch):
    monkeypatch.setattr(simple_summarizer.config, "SUMMARY_LANGUAGE", "zh-TW")
    item = NewsItem(
        title="Pinned: Update: GPT-5.5 and GPT-5.5 Pro are now available in the API.",
        url="https://example.com/openai-gpt55",
        source="Twitter / nitter.net",
        description=(
            "The model brings higher intelligence and stronger token efficiency "
            "to complex work, helping tasks get done with fewer retries."
        ),
    )

    sections = simple_summarize([item], [], [])
    text = sections["社群 / Twitter"]

    assert "OpenAI" in text
    assert "GPT-5.5" in text
    assert "重點：" in text
    assert "higher intelligence" not in text
    assert "token efficiency" not in text


def test_simple_summarize_zh_github_formats_metadata(monkeypatch):
    monkeypatch.setattr(simple_summarizer.config, "SUMMARY_LANGUAGE", "zh-TW")
    item = NewsItem(
        title="ComposioHQ/awesome-codex-skills [Python]",
        url="https://github.com/ComposioHQ/awesome-codex-skills",
        source="GitHub Trending",
        description=(
            "A curated list of practical Codex skills for automating workflows "
            "across the Codex CLI and API. · 638 stars today ★3,088"
        ),
    )

    sections = simple_summarize([], [item], [])
    text = sections["GitHub 熱門趨勢"]

    assert "重點：與 Codex 相關的熱門專案" in text
    assert "語言：Python" in text
    assert "今日星數：638" in text
    assert "累積星數：3,088" in text


def test_clean_description_decodes_html_entities():
    cleaned = _clean_description("AI新聞&nbsp;&nbsp;<br>重點更新", 100)
    assert cleaned == "AI新聞 重點更新"


def test_openai_client_uses_explicit_default_base_url_when_config_empty(monkeypatch):
    monkeypatch.setattr(openai_summarizer.config, "OPENAI_BASE_URL", "")
    assert openai_summarizer._client_kwargs() == {"base_url": "https://api.openai.com/v1"}


def test_openai_client_normalizes_custom_base_url(monkeypatch):
    monkeypatch.setattr(openai_summarizer.config, "OPENAI_BASE_URL", "https://example.com/v1/")
    assert openai_summarizer._client_kwargs() == {"base_url": "https://example.com/v1"}


def test_simple_summarize_dedupes_repeated_titles(monkeypatch):
    monkeypatch.setattr(simple_summarizer.config, "SUMMARY_LANGUAGE", "zh-TW")
    items = [
        NewsItem(
            title="Update: GPT-5.5 and GPT-5.5 Pro are now available in the API.",
            url="https://example.com/1",
            source="Twitter / nitter.net",
            description="OpenAI API update",
        ),
        NewsItem(
            title="Pinned: Update: GPT-5.5 and GPT-5.5 Pro are now available in the API.",
            url="https://example.com/2",
            source="Twitter / nitter.net",
            description="Another wording of the same update",
        ),
    ]

    text = simple_summarize(items, [], [])["社群 / Twitter"]
    assert text.count("OpenAI：GPT-5.5 / GPT-5.5 Pro 更新") == 1


def test_simple_summarize_github_uses_metadata_not_simple_description(monkeypatch):
    monkeypatch.setattr(simple_summarizer.config, "SUMMARY_LANGUAGE", "zh-TW")
    item = NewsItem(
        title="microsoft/VibeVoice [Python]",
        url="https://github.com/microsoft/VibeVoice",
        source="GitHub Trending",
        description="An open-source frontier speech AI project for reproducible emotional voice generation. · 757 stars today ★43,506",
    )

    text = simple_summarize([], [item], [])["GitHub 熱門趨勢"]
    assert "重點：與 語音 AI 相關的熱門專案" in text
    assert "語言：Python" in text
    assert "今日星數：757" in text
    assert "累積星數：43,506" in text


def test_filter_recent_items_keeps_only_last_24_hours():
    now = datetime(2026, 4, 28, 15, 0, tzinfo=timezone.utc)
    recent = NewsItem("recent", "https://example.com/r", "AI", published=now - timedelta(hours=3))
    old = NewsItem("old", "https://example.com/o", "AI", published=now - timedelta(hours=30))
    undated = NewsItem("undated", "https://example.com/u", "AI")

    result = rss_collector._filter_recent_items([recent, old, undated], now=now, hours=24)
    assert [item.title for item in result] == ["recent"]


def test_filter_recent_items_skips_google_news_noise():
    now = datetime(2026, 4, 28, 15, 0, tzinfo=timezone.utc)
    noise = NewsItem("Google News", "https://example.com/g", "AI", description="Comprehensive up-to-date news coverage", published=now)
    real = NewsItem("真新聞", "https://example.com/n", "AI", description="重要更新", published=now)

    result = rss_collector._filter_recent_items([noise, real], now=now, hours=24)
    assert [item.title for item in result] == ["真新聞"]


def test_simple_summarize_ai_description_is_brief(monkeypatch):
    monkeypatch.setattr(simple_summarizer.config, "SUMMARY_LANGUAGE", "zh-TW")
    item = NewsItem(
        title="人工智慧：白宮備忘錄指中國公司通過「蒸餾」活動大規模竊取美國AI技術",
        url="https://example.com/ai-news",
        source="AI News / news.google.com",
        description="人工智慧：白宮備忘錄指中國公司通過「蒸餾」活動大規模竊取美國AI技術 BBC",
    )

    text = simple_summarize([], [], [item])["AI 新聞"]
    assert "重點：" in text
    assert "可點連結看全文" in text
    assert text.count("人工智慧：白宮備忘錄") == 1


def test_simple_summarize_ai_limits_total_items(monkeypatch):
    monkeypatch.setattr(simple_summarizer.config, "SUMMARY_LANGUAGE", "zh-TW")
    ai_items = [
        NewsItem(
            title=f"新聞 {i}",
            url=f"https://example.com/news-{i}",
            source="AI News / news.google.com" if i < 8 else "AI News / ithome.com.tw",
            description="摘要內容",
        )
        for i in range(12)
    ]

    text = simple_summarize([], [], ai_items)["AI 新聞"]
    assert text.count("- **[") == 9


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


def test_openai_summarizer_hybrid_adds_key_points(monkeypatch):
    monkeypatch.setattr(openai_summarizer.config, "SUMMARY_LANGUAGE", "zh-TW")
    monkeypatch.setattr(openai_summarizer.config, "OPENAI_MODEL", "gpt-4o-mini")
    monkeypatch.setattr(openai_summarizer.config, "OPENAI_API_KEY", "test-key")

    class _FakeCompletions:
        def create(self, **kwargs):
            return type("Resp", (), {
                "choices": [type("Choice", (), {"message": type("Msg", (), {"content": "- 重點一\n- 重點二\n- 重點三"})()})]
            })()

    class _FakeChat:
        completions = _FakeCompletions()

    class _FakeClient:
        def __init__(self, *args, **kwargs):
            self.chat = _FakeChat()

    monkeypatch.setattr(openai_summarizer, "_preflight_openai", lambda api_key: None)
    monkeypatch.setitem(sys.modules, "openai", type("OpenAIModule", (), {"OpenAI": _FakeClient}))

    item = NewsItem(
        title="repo [Python]",
        url="https://example.com/repo",
        source="GitHub Trending",
        description="Useful project · 10 stars today ★100",
    )
    sections = openai_summarizer.summarize([], [item], [])

    assert "GitHub 熱門趨勢" in sections
    assert "關鍵重點" in sections
    assert "今日星數：10" in sections["GitHub 熱門趨勢"]
    assert sections["關鍵重點"].startswith("- 重點一")


def test_discord_notifier_suppresses_embeds(monkeypatch):
    from src.notifiers import discord as discord_notifier

    monkeypatch.setattr(discord_notifier.config, "DISCORD_WEBHOOK_URL", "https://example.com/webhook")
    payloads = []

    class _Resp:
        def raise_for_status(self):
            return None

    def _fake_post(url, json, headers, timeout):
        payloads.append(json)
        return _Resp()

    monkeypatch.setattr(discord_notifier.requests, "post", _fake_post)
    ok = discord_notifier.send_digest("- **[title](https://example.com)**\n  重點：摘要")

    assert ok is True
    assert payloads[0]["flags"] == 4


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


def test_github_trending_caps_total_items_to_five(monkeypatch):
    repos = [
        NewsItem(title=f"repo{i} [Python]", url=f"https://example.com/{i}", source="GitHub Trending", description="desc")
        for i in range(7)
    ]
    monkeypatch.setattr("src.collectors.github_trending._scrape_trending", lambda url: [
        type("Repo", (), {
            "name": f"owner/repo{i}",
            "url": f"https://github.com/owner/repo{i}",
            "description": "desc",
            "language": "Python",
            "stars_today": str(i),
            "total_stars": str(i * 10),
        })()
        for i in range(7)
    ])
    monkeypatch.setattr("src.collectors.github_trending.config.GITHUB_TRENDING_LANGUAGES", ["python"])
    monkeypatch.setattr("src.collectors.github_trending.config.GITHUB_TRENDING_SINCE", "daily")
    monkeypatch.setattr("src.collectors.github_trending.config.MAX_ITEMS_PER_SOURCE", 10)

    from src.collectors.github_trending import collect_github_trending
    items = collect_github_trending()

    assert len(items) == 5
