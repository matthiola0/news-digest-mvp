"""Deterministic fallback summarizer – no external API required."""
from __future__ import annotations

from collections import defaultdict

from src import config
from src.collectors.base import NewsItem


def summarize(
    twitter_items: list[NewsItem],
    github_items: list[NewsItem],
    ai_items: list[NewsItem],
) -> dict[str, str]:
    """
    Returns a dict mapping section name → markdown text block.
    Each block is a bulleted list of items with title, link and short description.
    """
    sections: dict[str, str] = {}
    is_zh = config.SUMMARY_LANGUAGE.lower().startswith(("traditional chinese", "zh", "繁"))

    if twitter_items:
        sections["社群 / Twitter"] = _render_section(twitter_items) if is_zh else _render_section(twitter_items)

    if github_items:
        sections["GitHub 熱門趨勢"] = _render_section(github_items) if is_zh else _render_section(github_items)

    if ai_items:
        # Group AI items by source feed
        by_source: dict[str, list[NewsItem]] = defaultdict(list)
        for item in ai_items:
            by_source[item.source].append(item)

        parts: list[str] = []
        for source, items in by_source.items():
            parts.append(f"**{source}**\n\n{_render_section(items)}")
        sections["AI 新聞"] = "\n\n".join(parts) if is_zh else "\n\n".join(parts)

    return sections


def _render_section(items: list[NewsItem]) -> str:
    lines: list[str] = []
    for item in items:
        line = f"- **[{item.title}]({item.url})**"
        if item.description:
            line += f"\n  {item.description}"
        lines.append(line)
    return "\n".join(lines)
