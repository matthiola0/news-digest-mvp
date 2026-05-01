"""Regenerate index.md (GitHub Pages homepage) from archives/ contents.

Scans archives/YYYY/MM/digest_DD.md, groups by month, and writes a single
browseable index. The first H1 of each digest is used as a short label.
"""
from __future__ import annotations

import re
import sys
from collections import defaultdict
from datetime import date
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
ARCHIVE_DIR = REPO_ROOT / "archives"
INDEX_PATH = REPO_ROOT / "index.md"

H1_RE = re.compile(r"^#\s+(.*?)\s*$", re.MULTILINE)


def first_h1(path: Path) -> str:
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return ""
    m = H1_RE.search(text)
    return m.group(1).strip() if m else ""


def collect() -> list[tuple[date, Path, str]]:
    rows: list[tuple[date, Path, str]] = []
    for md in ARCHIVE_DIR.glob("*/*/digest_*.md"):
        try:
            year = int(md.parent.parent.name)
            month = int(md.parent.name)
            day = int(md.stem.removeprefix("digest_"))
            d = date(year, month, day)
        except (ValueError, IndexError):
            continue
        rows.append((d, md.relative_to(REPO_ROOT), first_h1(md)))
    rows.sort(key=lambda r: r[0], reverse=True)
    return rows


MONTH_NAMES_ZH = {
    1: "一月", 2: "二月", 3: "三月", 4: "四月", 5: "五月", 6: "六月",
    7: "七月", 8: "八月", 9: "九月", 10: "十月", 11: "十一月", 12: "十二月",
}


def render(rows: list[tuple[date, Path, str]]) -> str:
    lines: list[str] = []
    lines.append("---")
    lines.append("layout: default")
    lines.append("title: Daily News Digest")
    lines.append("---")
    lines.append("")
    lines.append("# Daily News Digest")
    lines.append("")
    lines.append(
        "每日自動產出的繁體中文 AI / 開發 / 量化 / 加密 / 國際新聞摘要。"
        "資料來源：RSS、GitHub Trending、OpenAI 摘要。"
    )
    lines.append("")
    lines.append(
        "Source repo: "
        "[matthiola0/daily-news-digest](https://github.com/matthiola0/daily-news-digest)"
    )
    lines.append("")
    if not rows:
        lines.append("_尚無歸檔內容。_")
        lines.append("")
        return "\n".join(lines)

    grouped: dict[tuple[int, int], list[tuple[date, Path, str]]] = defaultdict(list)
    for d, path, title in rows:
        grouped[(d.year, d.month)].append((d, path, title))

    for (year, month) in sorted(grouped.keys(), reverse=True):
        lines.append(f"## {year} 年 {MONTH_NAMES_ZH[month]}")
        lines.append("")
        for d, path, title in grouped[(year, month)]:
            label = title or f"{d.isoformat()} digest"
            url = "/" + path.as_posix()
            lines.append(f"- [{d.isoformat()}]({url}) — {label}")
        lines.append("")
    return "\n".join(lines)


def main() -> int:
    rows = collect()
    INDEX_PATH.write_text(render(rows), encoding="utf-8")
    print(f"wrote {INDEX_PATH.relative_to(REPO_ROOT)} ({len(rows)} entries)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
