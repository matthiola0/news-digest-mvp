"""Assembles and writes the final Markdown digest file."""
from __future__ import annotations

import logging
from datetime import datetime
from pathlib import Path

import pytz

from src import config

logger = logging.getLogger(__name__)


def _title_text() -> str:
    if config.SUMMARY_LANGUAGE.lower().startswith(("traditional chinese", "zh", "繁")):
        return "每日新聞摘要"
    return "Daily News Digest"

_HEADER_TEMPLATE = """\
# {title} — {date}

> Generated at **{time} {tz}**
> Sources: {source_list}

---

"""


def build_digest(
    sections: dict[str, str],
    source_summary: str,
    run_date: datetime | None = None,
) -> str:
    """Combine section dict into a full Markdown document string."""
    tz = pytz.timezone(config.DIGEST_TIMEZONE)
    now = run_date or datetime.now(tz)
    if now.tzinfo is None:
        now = tz.localize(now)
    else:
        now = now.astimezone(tz)

    header = _HEADER_TEMPLATE.format(
        title=_title_text(),
        date=now.strftime("%Y-%m-%d"),
        time=now.strftime("%H:%M"),
        tz=config.DIGEST_TIMEZONE,
        source_list=source_summary,
    )

    body_parts: list[str] = []

    # If summarizer returned a single "digest" key, use it directly
    if "digest" in sections:
        body_parts.append(sections["digest"])
    else:
        for section_name, content in sections.items():
            body_parts.append(f"## {section_name}\n\n{content}")

    return header + "\n\n---\n\n".join(body_parts) + "\n"


def write_digest(markdown: str, date_str: str | None = None) -> Path:
    """Write the digest Markdown to the output directory and return the path."""
    output_dir = config.OUTPUT_DIR
    output_dir.mkdir(parents=True, exist_ok=True)

    if date_str is None:
        tz = pytz.timezone(config.DIGEST_TIMEZONE)
        date_str = datetime.now(tz).strftime("%Y-%m-%d")

    filename = f"digest_{date_str}.md"
    path = output_dir / filename
    path.write_text(markdown, encoding="utf-8")
    logger.info("Digest written to %s", path)
    return path
