"""
按「卷 × 1000 + 卷内三位序号」重编 `bi.jsonl` 的编号（金文原书的编法）。

原书每一卷都从 `001` 重新编号，所以完整编号是 `0` + 卷号 + 三位卷内号：

    卷一 01001-01193、卷二 02001-02452、卷三 03001-…（卷内最多 999 条）

`bi.jsonl` 现在的编号是后来重排的连续流水号（1–4419），卷界已经丢了，所以
每卷有多少条得写在 `backend/data/bi_volumes.json` 里，按卷序：

    [193, 452, 311, ...]

卷内的每个「号」（一处）带上原样的 A/B/C 后缀，例如 `01001`、`01001A`。

用法：

    python backend/scripts/number_bi_volumes.py [--dry-run]
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
BI_FILE = DATA_DIR / "bi.jsonl"
VOL_FILE = DATA_DIR / "bi_volumes.json"


def base_of(num: str) -> str:
    m = re.match(r"(\d+)([A-Z]*)$", num)
    return m.group(1) if m else num


def suffix_of(num: str) -> str:
    m = re.match(r"(\d+)([A-Z]*)$", num)
    return m.group(2) if m else ""


def main() -> None:
    dry = "--dry-run" in sys.argv
    if not VOL_FILE.exists():
        raise SystemExit(
            f"缺少 {VOL_FILE.name}：请写成每卷条目数的数组，如 [193, 452, 311]"
        )
    sizes = json.loads(VOL_FILE.read_text(encoding="utf-8"))
    if not isinstance(sizes, list) or not all(isinstance(x, int) and x > 0 for x in sizes):
        raise SystemExit("bi_volumes.json 应该是正整数数组")
    if any(x > 999 for x in sizes):
        raise SystemExit("每卷最多 999 个号（三位序号）")

    rows = [json.loads(l) for l in BI_FILE.read_text(encoding="utf-8").splitlines() if l.strip()]

    # 记录顺序里「号」的先后（同一号的多个字形是相邻的）
    order: list[str] = []
    seen: set[str] = set()
    for r in rows:
        b = base_of(r["num"])
        if b not in seen:
            seen.add(b)
            order.append(b)

    total_vol = sum(sizes)
    if total_vol < len(order):
        raise SystemExit(
            f"各卷合计 {total_vol} 个号，但 bi.jsonl 里有 {len(order)} 个号，分不完"
        )
    if total_vol > len(order):
        print(
            f"注意：各卷合计 {total_vol} 个号，文件里只有 {len(order)} 个；"
            "多出来的按「原书有、这批没有字形」处理"
        )

    # 旧号 → 新号（0 + 卷号 + 三位卷内号，即 卷号 × 1000 + k 补零到 5 位）
    mapping: dict[str, str] = {}
    i = 0
    for vol, size in enumerate(sizes, start=1):
        for k in range(size):
            if i >= len(order):
                break
            mapping[order[i]] = f"{vol * 1000 + k + 1:05d}"
            i += 1

    for r in rows:
        b = base_of(r["num"])
        r["num"] = mapping[b] + suffix_of(r["num"])

    print(f"{BI_FILE.name}: {len(rows)} records, {len(order)} numbers, {len(sizes)} volumes")
    start = 0
    for vol, size in enumerate(sizes, start=1):
        take = min(size, len(order) - start)
        if take <= 0:
            print(f"  卷{vol}: 0 个号（表比文件长）")
            continue
        print(f"  卷{vol}: {take} 个号, {mapping[order[start]]}..{mapping[order[start + take - 1]]}")
        start += take
    if dry:
        print("(dry run, nothing written)")
        return
    with open(BI_FILE, "w", encoding="utf-8", newline="\n") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")


if __name__ == "__main__":
    main()
