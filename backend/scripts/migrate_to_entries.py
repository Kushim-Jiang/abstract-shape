"""
迁移：把旧的 ndjson 形态转成新的「条」模型。

旧形态（2026-10 中间态）：
    {"char": "丂"}                                  ← 只有收录标记
    {"char": "丂", "con": "…", "analysis": "…"}      ← 更早的形态

新形态：
    {"char": "丂", "seq": 1, "con": "…", "ref_con": "…",
     "notes": "…", "refs": ["L005"]}

规则：
  * `char` 一条 -> 条号 1
  * `analysis` -> `notes`
  * `refs` / `references` -> `refs`
  * `con` -> `con`
  * 只有 char、其余全空的 -> 仍然生成一条空札记（保留「已收录」这个事实）

用法：
    python -m backend.scripts.migrate_to_entries [--dry-run]
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from collections import Counter
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent.parent
NDJSON = REPO / "abstract-shape" / "abstract-shape.ndjson"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    if not NDJSON.exists():
        print(f"找不到 {NDJSON}")
        return 1

    lines = [l for l in NDJSON.read_text(encoding="utf-8").splitlines() if l.strip()]
    recs = []
    for l in lines:
        try:
            recs.append(json.loads(l))
        except json.JSONDecodeError:
            continue

    # 已经是新形态？
    already = sum(1 for r in recs if "seq" in r)
    if already and already == len(recs):
        print("已经是「条」模型，无需迁移。")
        return 0

    keys = Counter()
    for r in recs:
        for k in r:
            keys[k] += 1
    print("旧字段分布:", dict(keys))

    out: list[dict] = []
    seen: set[tuple[str, int]] = set()
    for r in recs:
        ch = (r.get("char") or "").strip()
        if not ch:
            continue
        seq = int(r.get("seq") or 0)
        if seq < 1:
            # 每个字的条号从 1 开始递增
            seq = 1
            while (ch, seq) in seen:
                seq += 1
        seen.add((ch, seq))

        notes = r.get("notes") or r.get("analysis") or ""
        refs = r.get("refs") or r.get("references") or []
        rec = {"char": ch, "seq": seq}
        if r.get("con"):
            rec["con"] = str(r["con"]).strip()
        if r.get("ref_con"):
            rec["ref_con"] = str(r["ref_con"]).strip()
        if notes:
            rec["notes"] = notes
        if refs:
            rec["refs"] = list(refs)
        out.append(rec)

    out.sort(key=lambda r: (r["char"], r["seq"]))
    chars = len({r["char"] for r in out})
    print(f"\n记录: {len(recs)} -> {len(out)} 条，覆盖 {chars} 个字")

    if args.dry_run:
        print("[dry-run] 没写文件")
        return 0

    shutil.copy(NDJSON, NDJSON.with_suffix(".ndjson.bak3"))
    with NDJSON.open("w", encoding="utf-8", newline="\n") as f:
        for r in out:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")

    print("已写入（.bak3 备份）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
