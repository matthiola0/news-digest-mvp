"""Deterministic fallback summarizer – no external API required."""
from __future__ import annotations

from collections import defaultdict
from itertools import islice
import html
import re

from src import config
from src.collectors.base import NewsItem

_MAX_TWITTER_ITEMS = 5
_MAX_GITHUB_ITEMS = 5
_MAX_AI_ITEMS_TOTAL = 10
_MAX_AI_ITEMS_PER_SOURCE = 5


_TOPIC_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"gpt-?5\.5|openai", re.I), "OpenAI / GPT"),
    (re.compile(r"anthropic|claude", re.I), "Anthropic / Claude"),
    (re.compile(r"codex", re.I), "Codex"),
    (re.compile(r"copilot", re.I), "GitHub Copilot"),
    (re.compile(r"quantconnect|quant|trading|databento|alpha", re.I), "量化交易"),
    (re.compile(r"health|clinician|medical|healthbench", re.I), "醫療 AI"),
    (re.compile(r"security|hacking|漏洞|資安|breach", re.I), "資安"),
    (re.compile(r"voice|audio", re.I), "語音 AI"),
    (re.compile(r"agent", re.I), "AI Agent"),
    (re.compile(r"robot|機器人", re.I), "機器人"),
]


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
        twitter_items = twitter_items[:_MAX_TWITTER_ITEMS]
        sections["社群 / Twitter" if is_zh else "Twitter / Social"] = (
            _render_section_zh(twitter_items, kind="twitter")
            if is_zh
            else _render_section(twitter_items)
        )

    if github_items:
        github_items = github_items[:_MAX_GITHUB_ITEMS]
        sections["GitHub 熱門趨勢" if is_zh else "GitHub Trending"] = (
            _render_section_zh(github_items, kind="github")
            if is_zh
            else _render_section(github_items)
        )

    if ai_items:
        by_source: dict[str, list[NewsItem]] = defaultdict(list)
        for item in ai_items:
            by_source[item.source].append(item)

        parts: list[str] = []
        total_used = 0
        for source, items in by_source.items():
            if total_used >= _MAX_AI_ITEMS_TOTAL:
                break
            limited_items = list(islice(items, 0, min(_MAX_AI_ITEMS_PER_SOURCE, _MAX_AI_ITEMS_TOTAL - total_used)))
            if not limited_items:
                continue
            body = _render_section_zh(limited_items, kind="ai") if is_zh else _render_section(limited_items)
            parts.append(f"**{_clean_text(source)}**\n\n{body}")
            total_used += len(limited_items)
        sections["AI 新聞" if is_zh else "AI News"] = "\n\n".join(parts)

    return sections


def _render_section(items: list[NewsItem]) -> str:
    lines: list[str] = []
    for item in items:
        line = f"- **[{item.title}]({item.url})**"
        if item.description:
            line += f"\n  {item.description}"
        lines.append(line)
    return "\n".join(lines)


def _render_section_zh(items: list[NewsItem], kind: str) -> str:
    lines: list[str] = []
    seen_titles: set[str] = set()
    for item in items:
        if kind == "twitter":
            title, description = _twitter_item_to_zh(item)
        elif kind == "github":
            title, description = _github_item_to_zh(item)
        else:
            title, description = _ai_item_to_zh(item)

        if title in seen_titles:
            continue
        seen_titles.add(title)

        line = f"- **[{title}]({item.url})**"
        if description:
            line += f"\n  {description}"
        lines.append(line)
    return "\n".join(lines)


def _twitter_item_to_zh(item: NewsItem) -> tuple[str, str]:
    text = _combined_text(item)
    lower = text.lower()

    if "gpt-5.5" in lower:
        return (
            "OpenAI：GPT-5.5 / GPT-5.5 Pro 更新",
            "重點：OpenAI 宣布新模型已開放於 API 與 ChatGPT，主打更高能力與更佳 token 效率。",
        )
    if "our principles" in lower or ("principles" in lower and "openai" in lower):
        return (
            "OpenAI 公布 AI 發展原則",
            "重點：內容聚焦民主化、賦能、普惠、韌性與適應性等長期方向。",
        )
    if "clinician" in lower or "healthbench" in lower or "health at openai" in lower:
        return (
            "OpenAI 推出臨床版 ChatGPT 與醫療評測",
            "重點：包含面向臨床工作的 ChatGPT for Clinicians，以及醫療任務基準 HealthBench Professional。",
        )
    if "flipbook" in lower:
        return (
            "Karpathy 團隊展示 Flipbook 原型",
            "重點：嘗試直接由模型串流畫面像素，探索不同於 HTML 介面的互動方式。",
        )
    if "market" in lower and ("anthropic" in lower or "claude" in lower):
        return (
            "Anthropic 討論 AI agent 市場機制",
            "重點：指出高品質模型有優勢，但使用者不一定察覺，法規與制度也需要跟進。",
        )
    if "databento" in lower:
        return (
            "QuantConnect 整合 Databento 市場資料",
            "重點：把即時與歷史市場資料接進 LEAN，可直接用於研究、回測與實盤流程。",
        )
    if "quant finance" in lower:
        return (
            "QuantConnect 分享 AI 量化金融議題",
            "重點：聚焦 Applied AI for Quant Finance 與 AI 生成 alpha 的實作討論。",
        )
    if "lppls" in lower or "bubble" in lower:
        return (
            "量化研究：LPPLS 泡沫預測",
            "重點：討論如何用 LPPLS 模型偵測投機市場泡沫與轉折。",
        )

    topics = _extract_topics(text)
    title = f"{topics[0]} 近況" if topics else _shorten_title(item.title)
    topic_text = "、".join(topics) if topics else "技術動態"
    return title, f"重點：此則內容涉及 {topic_text}，原始貼文為英文，已保留連結供查看。"


def _github_item_to_zh(item: NewsItem) -> tuple[str, str]:
    title = _clean_text(item.title)
    repo_name = re.sub(r"\s*\[[^\]]+\]\s*$", "", title)
    language_match = re.search(r"\[([^\]]+)\]\s*$", title)
    language = language_match.group(1) if language_match else "未知"

    desc = _clean_text(item.description)
    stars_today_match = re.search(r"([\d,]+)\s+stars today", desc, re.I)
    total_stars_match = re.search(r"★\s*([\d,]+)", desc)
    core_desc = re.split(r"\s+·\s+[\d,]+\s+stars today", desc, maxsplit=1, flags=re.I)[0].strip(" ·")

    topics = _extract_topics(f"{repo_name} {core_desc}")
    if topics:
        brief = f"重點：與 {'、'.join(topics)} 相關的熱門專案"
    elif core_desc:
        brief = f"重點：{_shorten_text(core_desc, 28)}"
    else:
        brief = "重點：值得留意的開發工具 / 專案趨勢"

    parts = [brief, f"語言：{language}"]
    if stars_today_match:
        parts.append(f"今日星數：{stars_today_match.group(1)}")
    if total_stars_match:
        parts.append(f"累積星數：{total_stars_match.group(1)}")

    return repo_name, "；".join(parts) + "。"


def _ai_item_to_zh(item: NewsItem) -> tuple[str, str]:
    title = _normalize_news_title(item.title)
    description = _clean_text(item.description)
    description = re.sub(r"\s*&nbsp;\s*", " ", description)
    description = _simplify_ai_description(title, description)
    return title, description


def _topic_based_brief(title: str) -> str:
    title_lower = title.lower()
    if "copilot" in title_lower:
        return "重點：與 GitHub Copilot 產品或商業模式調整有關。"
    if "馬斯克" in title or "elon" in title_lower or "x money" in title_lower or "tesla" in title_lower:
        return "重點：與馬斯克、X 或 Tesla 的最新動向有關。"
    if any(word in title_lower for word in ["bitcoin", "ethereum", "加密", "幣", "crypto"]):
        return "重點：與加密貨幣市場、交易或政策變化有關。"
    if any(word in title for word in ["白宮", "烏克蘭", "俄羅斯", "歐盟", "中國", "美國"]):
        return "重點：與國際政治、政策或地緣局勢有關。"
    if any(word in title_lower for word in ["llm", "gemini", "openai", "ai", "人工智慧"]):
        return "重點：與 AI 模型、產品或產業進展有關。"
    if any(word in title for word in ["資安", "駭", "漏洞"]):
        return "重點：與資安事件或漏洞修補進展有關。"
    return "重點：與今日重要科技或市場動態有關。"


def _simplify_ai_description(title: str, description: str) -> str:
    if not description:
        return _topic_based_brief(title)

    normalized_title = _clean_text(title)
    normalized_description = _clean_text(description)

    if normalized_description.startswith(normalized_title):
        remainder = normalized_description[len(normalized_title):].strip(" -|｜:：")
        if remainder and len(remainder) <= 24 and re.search(r"[A-Za-z\u4e00-\u9fff]", remainder):
            return f"重點：此消息來自 {remainder}，可點連結看全文。"
        normalized_description = remainder or normalized_description

    normalized_description = re.sub(r"^(Comprehensive up-to-date news coverage, aggregated from sources all over the world by Google News\.?)+", "", normalized_description, flags=re.I).strip(" -|｜:：")
    if not normalized_description:
        return _topic_based_brief(title)
    if len(normalized_description) <= 28:
        return f"重點：{normalized_description}"
    return f"重點：{_shorten_text(normalized_description, 72)}"


def _combined_text(item: NewsItem) -> str:
    return _clean_text(f"{item.title} {item.description} {item.source}")


def _clean_text(text: str) -> str:
    text = html.unescape(text or "")
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"https?://\S+", "", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def _shorten_text(text: str, max_chars: int) -> str:
    text = _clean_text(text)
    if len(text) <= max_chars:
        return text
    return text[: max_chars - 1].rstrip() + "…"


def _shorten_title(title: str, max_chars: int = 36) -> str:
    title = _normalize_news_title(title)
    title = re.sub(r"^(RT by @[^:]+:|R to @[^:]+:|Pinned:)\s*", "", title, flags=re.I)
    if len(title) <= max_chars:
        return title
    title = re.split(r"[.。!！?？:]", title, maxsplit=1)[0].strip()
    return _shorten_text(title, max_chars)


def _normalize_news_title(title: str) -> str:
    title = _clean_text(title)
    title = re.sub(r"\s+-\s+[^-]+$", "", title)
    return title


def _extract_topics(text: str) -> list[str]:
    topics: list[str] = []
    for pattern, label in _TOPIC_PATTERNS:
        if pattern.search(text) and label not in topics:
            topics.append(label)
    return topics
