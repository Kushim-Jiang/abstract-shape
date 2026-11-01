"""
按「卷 × 1000 + 卷内号」重编 `bi.jsonl` 的编号（金文原书的编法）。

原书每一卷都从 `001` 重新编号，所以完整编号是 `卷号 × 1000 + 卷内号`，写成五位：

    卷一 01001-01193、卷二 02001-02452、卷三 03001-…（卷内最多 999 条）

`bi.jsonl` 现在的编号是后来重排的连续流水号（1–4419），卷界已经丢了，所以
每卷有多少条、哪几个号原书就没有，都得写在 `backend/data/bi_volumes.json` 里：

    {"volumes": [193, 452, ...], "holes": ["07086"]}

`holes` 是原书里跳过的号（比如 07085 之后直接 07087），这些号不占文件里的记录。
卷内一个号下的多个字形带 A/B/C 后缀，例如 `01001`、`01001A`。

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


def load_volumes() -> tuple[list[int], set[str]]:
    if not VOL_FILE.exists():
        raise SystemExit(
            f"缺少 {VOL_FILE.name}：请写成 "
            '{"volumes": [193, 452, ...], "holes": ["07086"]}'
        )
    data = json.loads(VOL_FILE.read_text(encoding="utf-8"))
    if isinstance(data, list):
        sizes, holes = data, []
    else:
        sizes, holes = data.get("volumes") or [], data.get("holes") or []
    if not sizes or not all(isinstance(x, int) and x > 0 for x in sizes):
        raise SystemExit("volumes 应该是正整数数组")
    if any(x > 999 for x in sizes):
        raise SystemExit("每卷最多 999 个号（三位序号）")
    return sizes, {str(h).strip() for h in holes if str(h).strip()}


def main() -> None:
    dry = "--dry-run" in sys.argv
    sizes, holes = load_volumes()

    rows = [json.loads(l) for l in BI_FILE.read_text(encoding="utf-8").splitlines() if l.strip()]

    # 记录顺序里「号」的先后（同一号的多个字形是相邻的）
    order: list[str] = []
    seen: set[str] = set()
    for r in rows:
        b = base_of(r["num"])
        if b not in seen:
            seen.add(b)
            order.append(b)

    # 目标编号序列：卷 × 1000 + 卷内号，跳过原书就没有的号
    targets: list[str] = []
    per_vol: list[int] = []
    for vol, size in enumerate(sizes, start=1):
        n = 0
        for k in range(1, size + 1):
            num = f"{vol * 1000 + k:05d}"
            if num in holes:
                continue
            targets.append(num)
            n += 1
        per_vol.append(n)

    print(f"{BI_FILE.name}: {len(rows)} records, {len(order)} numbers, {len(sizes)} volumes")
    if len(targets) != len(order):
        print(
            f"注意：各卷合计 {sum(sizes)} 个号、跳过 {len(holes)} 个空号，应得 "
            f"{len(targets)} 个，文件里有 {len(order)} 个（差 {len(order) - len(targets):+d}）"
        )

    mapping = dict(zip(order, targets))
    for r in rows:
        b = base_of(r["num"])
        if b in mapping:
            r["num"] = mapping[b] + suffix_of(r["num"])

    start = 0
    for vol, n in enumerate(per_vol, start=1):
        used = [mapping[order[i]] for i in range(start, min(start + n, len(order)))]
        if used:
            print(f"  卷{vol}: {len(used)} 个号, {used[0]}..{used[-1]}")
        start += n

    if dry:
        print("(dry run, nothing written)")
        return
    with open(BI_FILE, "w", encoding="utf-8", newline="\n") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")


if __name__ == "__main__":
    main()
