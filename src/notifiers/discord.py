"""Optional Discord webhook notifier."""
from __future__ import annotations

import logging

import requests

from src import config

logger = logging.getLogger(__name__)

# Discord has a 2000-char message limit; we chunk the digest
_CHUNK_SIZE = 1900


def send_digest(markdown: str) -> bool:
    """
    Post the digest to Discord via webhook.
    Returns True on success, False if webhook is not configured or request fails.
    """
    webhook_url = config.DISCORD_WEBHOOK_URL
    if not webhook_url:
        logger.debug("DISCORD_WEBHOOK_URL not set; skipping Discord notification.")
        return False

    chunks = _chunk_message(markdown)
    success = True
    for i, chunk in enumerate(chunks):
        payload = {
            "content": chunk if i > 0 else f"📰 **Daily News Digest**\n\n{chunk}",
            "flags": 4,
        }
        try:
            resp = requests.post(
                webhook_url,
                json=payload,
                headers=config.REQUEST_HEADERS,
                timeout=config.REQUEST_TIMEOUT,
            )
            resp.raise_for_status()
            logger.info("Discord chunk %d/%d sent.", i + 1, len(chunks))
        except Exception as exc:
            logger.warning("Discord webhook failed for chunk %d: %s", i + 1, exc)
            success = False

    return success


def _chunk_message(text: str) -> list[str]:
    lines = text.splitlines(keepends=True)
    chunks: list[str] = []
    current: list[str] = []
    current_len = 0

    for line in lines:
        if current_len + len(line) > _CHUNK_SIZE and current:
            chunks.append("".join(current))
            current = []
            current_len = 0
        current.append(line)
        current_len += len(line)

    if current:
        chunks.append("".join(current))
    return chunks
