"""Central configuration loaded from environment variables / .env file."""
import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()


def _csv(key: str, default: str = "") -> list[str]:
    raw = os.getenv(key, default).strip()
    return [u.strip() for u in raw.split(",") if u.strip()] if raw else []


def _int(key: str, default: int) -> int:
    try:
        return int(os.getenv(key, str(default)))
    except ValueError:
        return default


# ── Summarization ─────────────────────────────────────────────────────────────
OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")
OPENAI_MODEL: str = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
OPENAI_BASE_URL: str = os.getenv("OPENAI_BASE_URL", "")
SUMMARY_LANGUAGE: str = os.getenv("SUMMARY_LANGUAGE", "Traditional Chinese")

# ── Sources ───────────────────────────────────────────────────────────────────
TWITTER_RSS_FEEDS: list[str] = _csv("TWITTER_RSS_FEEDS")

_DEFAULT_AI_FEEDS = [
    "https://rss.arxiv.org/rss/cs.AI",
    "https://openai.com/news/rss.xml",
    "https://huggingface.co/blog/feed.xml",
    "https://www.technologyreview.com/feed/",
    "https://hnrss.org/frontpage?q=AI+OR+LLM+OR+GPT+OR+machine+learning",
]
_user_ai_feeds = _csv("AI_NEWS_RSS_FEEDS")
AI_NEWS_RSS_FEEDS: list[str] = _user_ai_feeds if _user_ai_feeds else _DEFAULT_AI_FEEDS

GITHUB_TRENDING_LANGUAGES: list[str] = _csv("GITHUB_TRENDING_LANGUAGES")
GITHUB_TRENDING_SINCE: str = os.getenv("GITHUB_TRENDING_SINCE", "daily")

# ── Output ────────────────────────────────────────────────────────────────────
OUTPUT_DIR: Path = Path(os.getenv("OUTPUT_DIR", "output"))
DIGEST_TIMEZONE: str = os.getenv("DIGEST_TIMEZONE", "Asia/Taipei")

# ── Discord ───────────────────────────────────────────────────────────────────
DISCORD_WEBHOOK_URL: str = os.getenv("DISCORD_WEBHOOK_URL", "")

# ── Tuning ────────────────────────────────────────────────────────────────────
MAX_ITEMS_PER_SOURCE: int = _int("MAX_ITEMS_PER_SOURCE", 10)
MAX_DESCRIPTION_CHARS: int = _int("MAX_DESCRIPTION_CHARS", 300)

# Request headers – some sites reject empty user-agents
REQUEST_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (compatible; NewsDigestBot/1.0; "
        "+https://github.com/user/news-digest-mvp)"
    )
}
REQUEST_TIMEOUT = 20  # seconds
