"""Copy the latest output/digest_YYYY-MM-DD.md into archives/YYYY/MM/digest_DD.md.

Idempotent: re-running on the same day overwrites the archive copy with the
current output. Safe to invoke from CI on every run.
"""
from __future__ import annotations

import shutil
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
OUTPUT_DIR = REPO_ROOT / "output"
ARCHIVE_DIR = REPO_ROOT / "archives"


def archive_one(src: Path) -> Path:
    # Filenames are digest_YYYY-MM-DD.md
    stem = src.stem  # digest_YYYY-MM-DD
    date_part = stem.removeprefix("digest_")
    year, month, day = date_part.split("-")
    dest_dir = ARCHIVE_DIR / year / month
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / f"digest_{day}.md"
    shutil.copy2(src, dest)
    return dest


def main() -> int:
    digests = sorted(OUTPUT_DIR.glob("digest_*.md"))
    if not digests:
        print("No digests in output/ — nothing to archive.")
        return 0
    for src in digests:
        dest = archive_one(src)
        print(f"archived {src.name} -> {dest.relative_to(REPO_ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
