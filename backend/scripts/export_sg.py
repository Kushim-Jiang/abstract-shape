#!/usr/bin/env python3
"""
将 sg-20260621.xlsx 完全解析为 JSON → shanggu.json
包含：字典表、小韻表（含音節矩陣索引）、音節表、计数表
"""

import json
import re
from pathlib import Path

import pandas as pd

REPO_DIR = Path(__file__).resolve().parent.parent.parent
XLSX_PATH = REPO_DIR / "data" / "sg-20260621.xlsx"
OUT_PATH = REPO_DIR / "backend" / "data" / "shanggu.json"


def _clean(val) -> str:
    if pd.isna(val):
        return ""
    s = str(val).strip()
    return s


def _int_or_none(val):
    if pd.isna(val):
        return None
    try:
        return int(float(val))
    except (ValueError, TypeError):
        return None


def _float_or_none(val):
    if pd.isna(val):
        return None
    try:
        return round(float(val), 4)
    except (ValueError, TypeError):
        return None


def parse_dictionary(df: pd.DataFrame) -> list[dict]:
    """解析字典表"""
    records = []
    for _, row in df.iterrows():
        char = _clean(row.iloc[0])
        if not char:
            continue
        rec: dict = {
            "char": char,
            "reading": _clean(row.iloc[1]),
            "pinyin": _clean(row.iloc[2]),
            "xiesheng": _clean(row.iloc[3]),
        }
        # 韵文证据
        shijing = _clean(row.iloc[4])
        zhanguo = _clean(row.iloc[5])
        if shijing:
            rec["rhyme_shijing"] = True
        if zhanguo:
            rec["rhyme_zhanguo"] = True

        # 频率
        total = _int_or_none(row.iloc[6])
        freq = _float_or_none(row.iloc[7])
        if total is not None:
            rec["occurrences"] = total
        if freq is not None:
            rec["freq_preqin"] = freq

        # 西周
        xizhou = _int_or_none(row.iloc[9])
        xizhou_freq = _float_or_none(row.iloc[10])
        if xizhou is not None:
            rec["occ_western_zhou"] = xizhou
        if xizhou_freq is not None:
            rec["freq_western_zhou"] = xizhou_freq

        # 出处、释义、注释
        source = _clean(row.iloc[8])
        meaning = _clean(row.iloc[11])
        note = _clean(row.iloc[12]) if len(row) > 12 else ""

        if source:
            rec["source"] = source
        if meaning:
            rec["meaning"] = meaning
        if note:
            rec["note"] = note

        records.append(rec)
    return records


def parse_syllable_table(df: pd.DataFrame) -> dict:
    """
    解析音節表（二维矩阵）
    列头：聲母 (P幫, P滂, P並, M明, ...)
    行头：介音/等(r/ˤ/ˤr) + 元音(a/e/i/o/u/ə) + 韻尾
    """
    # 前3行是列头
    data = []

    # 解析列头：Row 1 = 声母组名, Row 2 = 推荐音标
    col_initials = {}
    for ci in range(3, df.shape[1]):
        h1 = _clean(df.iloc[1, ci]) if df.shape[0] > 1 else ""
        h2 = _clean(df.iloc[2, ci]) if df.shape[0] > 2 else ""
        if h1:
            col_initials[ci] = {"group": h1, "ipa": h2}

    # 从 Row 3 开始是数据
    for ri in range(3, len(df)):
        medial = _clean(df.iloc[ri, 0])  # 介音 r/ˤ/ˤr
        vowel = _clean(df.iloc[ri, 1])  # 元音 a/e/i/o/u/ə
        coda = _clean(df.iloc[ri, 2])  # 韻尾 ŋ/k/j/s/m/n/...
        label = _clean(df.iloc[ri, 3])  # 推荐拟音标签

        row_data = {}
        for ci, init_info in col_initials.items():
            val = _clean(df.iloc[ri, ci])
            if val:
                row_data[init_info["group"]] = val

        entry = {
            "medial": medial,
            "vowel": vowel,
            "coda": coda,
            "label": label,
            "chars_by_initial": row_data,
        }
        if medial or vowel or coda:
            data.append(entry)

    return {
        "initial_headers": {str(k): v for k, v in col_initials.items()},
        "rows": data,
    }


def parse_small_rhyme_table(df: pd.DataFrame) -> list[dict]:
    """解析小韻表"""
    records = []
    for _, row in df.iterrows():
        ipa = _clean(row.iloc[0])
        pinyin = _clean(row.iloc[1])
        if not ipa and not pinyin:
            continue
        # 跳过 header 行
        if ipa == "IPA" or ipa == "ipa":
            continue
        rec: dict = {
            "ipa": ipa,
            "pinyin": pinyin,
            "initial": _clean(row.iloc[2]),
            "medial": _clean(row.iloc[3]),
            "vowel": _clean(row.iloc[4]),
        }
        tone = _clean(row.iloc[5]) if len(row) > 5 else ""
        if tone:
            rec["tone"] = tone
        chars = _clean(row.iloc[6]) if len(row) > 6 else ""
        if chars:
            # 解析字，可能包含 {注釋}
            raw_chars = chars
            char_list = re.findall(r"[^\s{}（）()]+", chars)
            rec["chars_raw"] = raw_chars
            rec["chars"] = char_list
        records.append(rec)
    return records


def parse_count_tables(xls) -> dict:
    """解析导出计数表"""
    counts = {}
    for sn in xls.sheet_names:
        s = str(sn).strip()
        if s.startswith("导出计数"):
            df = pd.read_excel(xls, sn, header=None)
            rows = []
            for _, row in df.iterrows():
                r = {}
                for ci in range(len(row)):
                    v = _clean(row.iloc[ci])
                    if v:
                        r[str(ci)] = v
                if r:
                    rows.append(r)
            key = s.replace("导出计数_", "")
            counts[key] = rows
    return counts


def main():
    print("=== 解析 sg-20260621.xlsx ===")
    xls = pd.ExcelFile(XLSX_PATH)

    result = {
        "meta": {"source": "sg-20260621.xlsx", "sheets": xls.sheet_names},
        "dictionary": [],
        "syllable_table": {},
        "small_rhyme_table": [],
        "statistics": {},
    }

    for sn in xls.sheet_names:
        s = str(sn).strip()
        print(f"  [{s}]")
        if s == "字典表":
            df = pd.read_excel(xls, sn, header=0)
            result["dictionary"] = parse_dictionary(df)
            print(f"    → dictionary: {len(result['dictionary'])} 字")
        elif s == "音節表":
            df = pd.read_excel(xls, sn, header=None)
            result["syllable_table"] = parse_syllable_table(df)
            rows = len(result["syllable_table"].get("rows", []))
            initials = len(result["syllable_table"].get("initial_headers", {}))
            print(f"    → syllable_table: {rows} 行 × {initials} 声母")
        elif s == "小韻表":
            df = pd.read_excel(xls, sn, header=None)
            result["small_rhyme_table"] = parse_small_rhyme_table(df)
            print(f"    → small_rhyme_table: {len(result['small_rhyme_table'])} 小韻")
        elif s.startswith("导出计数"):
            pass  # 后面统一处理

    # 统计表
    result["statistics"] = parse_count_tables(xls)
    for k, v in result["statistics"].items():
        print(f"    → 计数_{k}: {len(v)} 行")

    # 保存
    with open(OUT_PATH, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2, ensure_ascii=False)

    print(f"\n  ✓ 已保存到 {OUT_PATH}")
    size = OUT_PATH.stat().st_size / 1024 / 1024
    print(f"    大小: {size:.1f} MB")


if __name__ == "__main__":
    main()
