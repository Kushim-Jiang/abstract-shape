"""探索 guangyun.json 的声母组和韵部结构"""

import json
from collections import defaultdict

with open("backend/data/guangyun.json", "r", encoding="utf-8") as f:
    d = json.load(f)

# ── 声母组 ──────────────────────────────
idist = d["initial_distribution"]
rows = idist["rows"]
# 去重 (group, series)
seen = set()
unique_groups = []
for r in rows:
    key = (r["group"], r["series"])
    if key not in seen:
        seen.add(key)
        unique_groups.append(r)

print("=== 声母组 (去重) ===")
print(f"{'组名':4s}  系列  鈍鋭")
print("-" * 30)
for r in unique_groups:
    g = r["group"] or "(空)"
    s = r["series"]
    ds = r["dull_sharp"] or ""
    print(f"  {g:4s}  {s:4s}  {ds}")

# ── 韵部 ──────────────────────────────
rt = d["rhyme_table"]
by_yunmu = defaultdict(set)
for r in rt:
    parts = r["status"].split("-")
    if len(parts) >= 4:
        by_yunmu[parts[3]].add(parts[4] if len(parts) >= 5 else "")

print("\n=== 韵部 (yunmu) 及声调分布 ===")
print(f"{'韵部':4s}  声调")
print("-" * 30)
for yunmu in sorted(by_yunmu.keys()):
    tones = sorted(by_yunmu[yunmu])
    print(f"  {yunmu:4s}  {', '.join(tones)}")
print(f"\n总共 {len(by_yunmu)} 个韵部")
