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
        twitter_body = (
            _render_section_zh(twitter_items, kind="twitter")
            if is_zh
            else _render_section(twitter_items)
        )
        if twitter_body:
            sections["社群 / Twitter" if is_zh else "Twitter / Social"] = twitter_body

    if github_items:
        github_items = github_items[:_MAX_GITHUB_ITEMS]
        github_body = (
            _render_section_zh(github_items, kind="github")
            if is_zh
            else _render_section(github_items)
        )
        if github_body:
            sections["GitHub 熱門趨勢" if is_zh else "GitHub Trending"] = github_body

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
            if _should_skip_twitter_item(item):
                continue
            title, description = _twitter_item_to_zh(item)
        elif kind == "github":
            title, description = _github_item_to_zh(item)
        else:
            title, description = _ai_item_to_zh(item)

        if not title or title in seen_titles:
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

    return "", ""


def _github_item_to_zh(item: NewsItem) -> tuple[str, str]:
    title = _clean_text(item.title)
    repo_name = re.sub(r"\s*\[[^\]]+\]\s*$", "", title)
    language_match = re.search(r"\[([^\]]+)\]\s*$", title)
    language = language_match.group(1) if language_match else "未知"

    desc = _clean_text(item.description)
    stars_today_match = re.search(r"([\d,]+)\s+stars today", desc, re.I)
    total_stars_match = re.search(r"★\s*([\d,]+)", desc)
    core_desc = re.split(r"\s+·\s+[\d,]+\s+stars today", desc, maxsplit=1, flags=re.I)[0].strip(" ·")

    brief_text = _humanize_github_description(repo_name, core_desc)
    brief = f"重點：{brief_text}" if brief_text else "重點：值得留意的開發工具 / 專案趨勢"

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
    title_brief = _summarize_news_title(title)
    if not description:
        return f"重點：{title_brief}" if title_brief else _topic_based_brief(title)

    normalized_title = _clean_text(title)
    normalized_description = _clean_text(description)

    if normalized_description.startswith(normalized_title):
        remainder = normalized_description[len(normalized_title):].strip(" -|｜:：")
        if not remainder or len(remainder) <= 24:
            return f"重點：{title_brief}" if title_brief else _topic_based_brief(title)
        normalized_description = remainder

    normalized_description = re.sub(r"^(Comprehensive up-to-date news coverage, aggregated from sources all over the world by Google News\.?)+", "", normalized_description, flags=re.I).strip(" -|｜:：")
    if not normalized_description:
        return f"重點：{title_brief}" if title_brief else _topic_based_brief(title)

    if len(normalized_description) <= 28:
        return f"重點：{normalized_description}"

    simplified = _humanize_english_snippet(normalized_description)
    if simplified:
        return f"重點：{simplified}"

    compact = _compact_chinese_brief(normalized_description)
    if compact and not _is_generic_brief(compact):
        return f"重點：{compact}"
    if title_brief:
        return f"重點：{title_brief}"
    return f"重點：{_shorten_text(normalized_description, 72)}"


def _humanize_github_description(repo_name: str, description: str) -> str:
    description = _clean_text(description).strip(" .")
    if not description:
        topics = _extract_topics(repo_name)
        return f"與 {'、'.join(topics)} 相關的熱門專案" if topics else "值得留意的開發工具 / 專案趨勢"

    lowered = description.lower()
    if "curated list of practical codex skills" in lowered:
        return "整理 Codex CLI 與 API 的實用技能與自動化工作流範例"
    if "vibevoice" in repo_name.lower():
        return "開源語音 AI 專案，主打可重現的情緒化語音生成"
    if "speech ai project" in lowered and "emotional voice generation" in lowered:
        return "開源語音 AI 專案，主打可重現的情緒化語音生成"
    if "voice ai" in lowered and "emotional voice generation" in lowered:
        return "開源語音 AI 專案，主打可重現的情緒化語音生成"
    if "track locati" in lowered or "track location" in lowered:
        return "位置追蹤工具，可用於蒐集與整理公開定位資訊"
    if "public apis" in repo_name.lower() or "free apis" in lowered:
        return "整理免費 API 資源，方便快速尋找可串接的服務"
    if "claude-code-templates" in repo_name.lower() or ("claude" in lowered and "template" in lowered):
        return "整理 Claude Code 的常用模板與工作流範例"

    simplified = _humanize_english_snippet(description)
    if simplified:
        return simplified

    topics = _extract_topics(f"{repo_name} {description}")
    if topics:
        return f"與 {'、'.join(topics)} 相關的熱門專案"
    return _shorten_text(description, 40)


def _humanize_english_snippet(text: str) -> str:
    text = _clean_text(text).strip(" .")
    if not text or not re.search(r"[A-Za-z]", text):
        return ""

    latin_chars = len(re.findall(r"[A-Za-z]", text))
    cjk_chars = len(re.findall(r"[\u4e00-\u9fff]", text))
    if cjk_chars and latin_chars < cjk_chars:
        return ""

    replacements = [
        (r"^an open-source ", "開源"),
        (r"^a curated list of ", "整理"),
        (r"^a collective list of ", "整理"),
        (r"\bpractical\b", "實用"),
        (r"\bcurated\b", "精選"),
        (r"\bopen-source\b", "開源"),
        (r"\bfrontier\b", "前沿"),
        (r"\bspeech ai\b", "語音 AI"),
        (r"\bvoice ai\b", "語音 AI"),
        (r"\bemotional voice generation\b", "情緒化語音生成"),
        (r"\breproducible\b", "可重現的"),
        (r"\bautomating workflows\b", "自動化工作流"),
        (r"\bworkflow(s)?\b", "工作流"),
        (r"\bpractical codex skills\b", "Codex 實用技能"),
        (r"\bcodex cli and api\b", "Codex CLI 與 API"),
        (r"\btool to\b", "工具，可"),
        (r"\btrack location(s)?\b", "追蹤位置"),
        (r"\bfree apis\b", "免費 API"),
        (r"\btemplates\b", "模板"),
    ]

    result = text
    for pattern, repl in replacements:
        result = re.sub(pattern, repl, result, flags=re.I)

    result = result.strip(" .")
    result = re.sub(r"\s+", " ", result)
    if re.search(r"[A-Za-z]{4,}", result):
        return _shorten_text(text, 36)
    return result


def _compact_chinese_brief(text: str) -> str:
    text = _clean_text(text).strip("。")
    if not text:
        return ""
    first_sentence = re.split(r"[。！？]", text, maxsplit=1)[0].strip()
    first_clause = re.split(r"[，；]", first_sentence, maxsplit=1)[0].strip()
    candidate = first_clause or first_sentence or text
    return _shorten_text(candidate, 42)


def _is_generic_brief(text: str) -> bool:
    text = _clean_text(text)
    generic_prefixes = (
        "AI浪潮加持下",
        "去年",
        "在政府推動",
        "為了因應",
        "Google近日",
        "近期研究成果",
        "法國報紙摘要",
    )
    if len(text) < 12:
        return True
    return any(text.startswith(prefix) for prefix in generic_prefixes)


def _summarize_news_title(title: str) -> str:
    normalized = _normalize_news_title(title)
    lowered = normalized.lower()

    if "蒸餾" in normalized and ("美國ai技術" in normalized.replace(" ", "").lower() or "美國ai" in normalized.replace(" ", "").lower()):
        return "中國公司透過模型蒸餾大規模竊取美國 AI 技術。"
    if "copilot" in lowered and any(word in normalized for word in ["按量計費", "ai credits", "生效"]):
        return "GitHub Copilot 將改採 AI Credits 與按量計費模式。"
    if "量化交易" in normalized and "ai" in lowered:
        return "量化交易公司正成為 AI 新創與人才的重要孵化來源。"
    if any(word in normalized for word in ["白宮", "烏克蘭", "俄羅斯", "歐盟", "中國", "美國"]):
        return _shorten_text(normalized, 38)
    if any(word in lowered for word in ["gemini", "openai", "ai", "人工智慧"]):
        return _shorten_text(normalized, 38)
    return _shorten_text(normalized, 38)


def _should_skip_twitter_item(item: NewsItem) -> bool:
    title = _clean_text(item.title)
    description = _clean_text(item.description)
    combined = f"{title} {description}".strip()
    if not combined:
        return True
    if not re.search(r"[A-Za-z0-9\u4e00-\u9fff]", title):
        return True
    if len(title) <= 3 and not re.search(r"[A-Za-z\u4e00-\u9fff]{2,}", title):
        return True
    if title.endswith("…"):
        return True
    return False


def _summarize_twitter_text(item: NewsItem) -> str:
    text = _combined_text(item)
    lowered = text.lower()
    if "openai" in lowered and "api" in lowered:
        return "OpenAI 公布新功能或模型更新，細節可由原貼文進一步查看。"
    if "anthropic" in lowered or "claude" in lowered:
        return "與 Anthropic / Claude 的產品、研究或市場觀點有關。"
    if "quantconnect" in lowered or "quant" in lowered:
        return "與量化交易、研究流程或市場資料整合有關。"
    if "elon" in lowered or "musk" in lowered or "x money" in lowered or "tesla" in lowered:
        return "與馬斯克、X 平台或 Tesla 的最新動向有關。"
    return ""


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
