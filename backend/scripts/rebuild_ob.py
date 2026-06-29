"""从 abstract_shape.xlsx 重构 ob.jsonl

- 读取 xlsx 的 'ob' sheet
- 前向填充 num (A) 和 glyph (B) 列
- 保留 num 原始值（含 N001、1255A 等字母前缀）
- 仅清理 trailing 冒号（如 0014: → 0014）
- 纯数字 num 补 4 位（1 → 0001）
- 按 (num, glyph) 分组合并注解
- 排序：纯数字在前（数值序），字母前缀在后（字典序）
"""

import json
import re
from collections import OrderedDict

import pandas as pd

XLSX_PATH = "input/abstract_shape.xlsx"

# ── 1. 读取 xlsx ──
df = pd.read_excel(XLSX_PATH, "ob")
print(f"读取 xlsx: {len(df)} 行")


# ── 2. 清理 num ──
def clean_num(raw) -> str:
    """清理 num：去冒号、纯数字补4位、保留字母前缀"""
    if pd.isna(raw):
        return ""
    s = str(raw).strip()
    # 去掉 trailing 冒号
    s = s.rstrip(":")
    if not s:
        return ""
    # 如果是纯数字，zfill(4)
    if s.isdigit():
        return s.zfill(4)
    return s


# ── 3. 前向填充 + 清洗 ──
rows = []
last_num = ""
last_glyph = ""
for _, row in df.iterrows():
    raw_num = row.get("num", "")
    raw_glyph = row.get("glyph", "")
    # 前向填充 num
    cleaned = clean_num(raw_num)
    if cleaned:
        last_num = cleaned
    # 前向填充 glyph
    glyph = str(raw_glyph).strip() if pd.notna(raw_glyph) else ""
    if glyph:
        last_glyph = glyph
    rows.append(
        {
            "num": last_num,
            "glyph": last_glyph,
            "con": str(row.get("con", "")).strip() if pd.notna(row.get("con")) else "",
            "ref": str(row.get("recon", "")).strip() if pd.notna(row.get("recon")) else "",
            "comm": str(row.get("comm", "")).strip() if pd.notna(row.get("comm")) else "",
        }
    )

print(f"处理后: {len(rows)} 行")

# ── 4. 按 (num, glyph) 分组 ──
groups = OrderedDict()
for r in rows:
    key = (r["num"], r["glyph"])
    if key not in groups:
        groups[key] = {"num": r["num"], "glyph": r["glyph"], "annotations": []}
    if r["con"] or r["ref"] or r["comm"]:
        groups[key]["annotations"].append(
            {
                "con": r["con"],
                "ref": r["ref"],
                "comm": r["comm"],
            }
        )


# ── 5. 排序：纯数字在前（数值序），字母前缀在后（字典序） ──
def sort_key(item):
    n = item["num"]
    if n.isdigit():
        return (0, int(n), "")
    else:
        return (1, 0, n)


result = sorted(groups.values(), key=sort_key)

print(f"合并后条目: {len(result)}")
multi = sum(1 for r in result if len(r["annotations"]) > 1)
print(f"多注解: {multi}")
total_annos = sum(len(r["annotations"]) for r in result)
print(f"注解总数: {total_annos}")

# 验证特殊编号
n_entries = [r for r in result if r["num"].startswith("N")]
print(f"N 前缀条目: {len(n_entries)} (N001 ~ N{len(n_entries):03d})")
ab_entries = [r for r in result if re.search(r"[A-Z]$", r["num"])]
print(f"字母后缀条目: {len(ab_entries)}")

# ── 6. 保存 jsonl ──
with open("backend/data/ob.jsonl", "w", encoding="utf-8") as f:
    for entry in result:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")
print("已保存到 backend/data/ob.jsonl")
