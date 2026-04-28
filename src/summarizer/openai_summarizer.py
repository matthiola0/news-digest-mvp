"""OpenAI-compatible summarizer using chat completion API."""
from __future__ import annotations

import logging

import requests

from src import config
from src.collectors.base import NewsItem

logger = logging.getLogger(__name__)


def _system_prompt() -> str:
    return f"""\
You are a concise tech news curator. You receive raw news items grouped by category
and produce a tight, readable daily digest in Markdown.

Language requirement:
- Write the entire digest in {config.SUMMARY_LANGUAGE}.
- If source titles are in English, you may keep the title itself, but the summary/context must be in {config.SUMMARY_LANGUAGE}.

Rules:
- Use ## for each top-level section heading.
- Under each section, write 2-5 bullet points with the most interesting items.
- Each bullet: bold title as a Markdown link, then one clear sentence of context.
- Skip duplicates or low-signal items.
- End with a "關鍵重點" section of 3 bullet points summarising the day.
- Do NOT add any preamble; start directly with the first ## heading.
"""


def _items_to_text(label: str, items: list[NewsItem]) -> str:
    if not items:
        return ""
    lines = [f"### {label}"]
    for it in items:
        desc = it.description[:400] if it.description else ""
        lines.append(f"- [{it.title}]({it.url}): {desc}")
    return "\n".join(lines)


def _describe_exception(exc: Exception) -> str:
    parts = [f"{type(exc).__name__}: {exc!s}"]
    if exc.__cause__:
        parts.append(f"cause={type(exc.__cause__).__name__}: {exc.__cause__!r}")
    if exc.__context__ and exc.__context__ is not exc.__cause__:
        parts.append(f"context={type(exc.__context__).__name__}: {exc.__context__!r}")
    return " | ".join(parts)


def _preflight_openai(api_key: str) -> None:
    url = (config.OPENAI_BASE_URL.rstrip("/") + "/models") if config.OPENAI_BASE_URL else "https://api.openai.com/v1/models"
    try:
        response = requests.get(
            url,
            headers={"Authorization": f"Bearer {api_key}"},
            timeout=15,
        )
        logger.info(
            "OpenAI preflight GET %s -> status=%s content-type=%s",
            url,
            response.status_code,
            response.headers.get("content-type", ""),
        )
    except Exception as exc:
        logger.warning("OpenAI preflight failed: %s", _describe_exception(exc))


def summarize(
    twitter_items: list[NewsItem],
    github_items: list[NewsItem],
    ai_items: list[NewsItem],
) -> dict[str, str]:
    """
    Returns a single dict with key "digest" containing the full LLM-written
    Markdown digest, or falls back to the simple summarizer on failure.
    """
    try:
        from openai import OpenAI  # import here so missing package is not fatal
    except ImportError:
        logger.warning("openai package not installed; falling back to simple summarizer.")
        from src.summarizer import simple_summarizer
        return simple_summarizer.summarize(twitter_items, github_items, ai_items)

    parts: list[str] = []
    if twitter_items:
        parts.append(_items_to_text("Twitter / Social", twitter_items))
    if github_items:
        parts.append(_items_to_text("GitHub Trending", github_items))
    if ai_items:
        parts.append(_items_to_text("AI News", ai_items))

    if not parts:
        return {"digest": "_No items collected today._"}

    user_message = "\n\n".join(parts)

    kwargs: dict = {}
    if config.OPENAI_BASE_URL:
        kwargs["base_url"] = config.OPENAI_BASE_URL

    client = OpenAI(api_key=config.OPENAI_API_KEY, **kwargs)

    logger.info("Calling OpenAI-compatible API (model=%s)…", config.OPENAI_MODEL)
    _preflight_openai(config.OPENAI_API_KEY)
    try:
        response = client.chat.completions.create(
            model=config.OPENAI_MODEL,
            messages=[
                {"role": "system", "content": _system_prompt()},
                {"role": "user", "content": user_message},
            ],
            temperature=0.3,
            max_tokens=2048,
        )
        digest_text = response.choices[0].message.content or ""
        return {"digest": digest_text}
    except Exception as exc:
        logger.warning("OpenAI API call failed: %s; falling back to simple summarizer.", _describe_exception(exc))
        from src.summarizer import simple_summarizer
        return simple_summarizer.summarize(twitter_items, github_items, ai_items)
