"""
给三张字形表的编号去重。

`ob.jsonl`（甲骨文）与 `bi.jsonl`（金文）的编号是拓片号，一个号下往往有好几个
字形；`seal.ndjson`（小篆）本来就是 1–11108 不重号。这里把重号的第二、三……
个依次加 A、B、C 后缀（`0001` → `0001A`、`0001B`），让三个文件里的 `num`
都能当唯一标识用。

用法：

    python backend/scripts/renumber_glyphs.py [--dry-run]
"""

from __future__ import annotations

import json
import string
import sys
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
TARGETS = ["ob.jsonl", "bi.jsonl", "seal.ndjson"]


def suffix(k: int) -> str:
    """第 k 个重号（k=1 是第一个重号）→ A, B, … Z, AA, AB, …"""
    out = ""
    while k > 0:
        k, r = divmod(k - 1, 26)
        out = string.ascii_uppercase[r] + out
    return out


def renumber(path: Path, dry: bool) -> int:
    rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    seen: dict[str, int] = {}
    changed = 0
    for rec in rows:
        num = str(rec.get("num") or "").strip()
        if not num:
            continue
        seen[num] = seen.get(num, 0) + 1
        if seen[num] == 1:
            continue
        new = num + suffix(seen[num] - 1)
        if new != num:
            rec["num"] = new
            changed += 1
    print(f"{path.name}: {len(rows)} records, {changed} renamed")
    if not dry and changed:
        with open(path, "w", encoding="utf-8", newline="\n") as f:
            for rec in rows:
                f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    return changed


def main() -> None:
    dry = "--dry-run" in sys.argv
    for name in TARGETS:
        renumber(DATA_DIR / name, dry)


if __name__ == "__main__":
    main()
