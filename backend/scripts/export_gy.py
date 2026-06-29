#!/usr/bin/env python3
"""
将 gy-20250226.xlsx 完全解析为 JSON。
输出结构包含全部 5 个 sheet 的综合数据，
可同时替代 guangyun.json 和 shengsheng.json。
"""

import json
import re
from pathlib import Path

import pandas as pd

REPO_DIR = Path(__file__).resolve().parent.parent.parent
XLSX_PATH = REPO_DIR / "data" / "gy-20250226.xlsx"
OUT_PATH = REPO_DIR / "backend" / "data" / "guangyun.json"


def parse_main_rhyme_table(df: pd.DataFrame) -> list[dict]:
    """解析《廣韻》小韻諧聲劃分"""
    records = []
    header_skipped = False
    for _, row in df.iterrows():
        seq = row.iloc[0]
        if pd.isna(seq) or seq == "本表序":
            if not header_skipped:
                header_skipped = True
                continue
            continue
        try:
            seq = int(float(seq))
        except (ValueError, TypeError):
            continue

        raw_chars = _clean(row.iloc[11])
        chars_parsed = _parse_chars_with_corrections(raw_chars)
        init = _clean(row.iloc[4])
        kh = _clean(row.iloc[5])
        deng = _clean(row.iloc[6])
        yun = _clean(row.iloc[7])
        ton = _clean(row.iloc[8])
        rec = {
            "seq": seq,
            "type": _clean(row.iloc[1]),
            "shoushou": _clean(row.iloc[2]),
            "secondary": _clean(row.iloc[3]),
            "status": f"{init}-{kh}-{deng}-{yun}-{ton}",
            "qieyu": _clean(row.iloc[9]),
            "qiepin": _clean(row.iloc[10]),
            "chars_raw": raw_chars,
            "chars": [c["char"] for c in chars_parsed],
            "corrections": {c["char"]: c["corrected_to"] for c in chars_parsed if c["corrected_to"]},
        }
        if rec["shoushou"] or rec["status"] or rec["chars"]:
            records.append(rec)
    return records


def parse_full_table(df: pd.DataFrame) -> list[dict]:
    """解析《廣韻》全聲系表（含前向填充合并单元格）"""
    df = df.copy()
    # 找到 header 行之后的数据起始位置
    data_start = 0
    for row_idx in range(len(df)):
        row = df.iloc[row_idx]
        seq = row.iloc[0]
        if pd.notna(seq) and seq != "本表序":
            try:
                int(float(seq))
                data_start = row_idx
                break
            except (ValueError, TypeError):
                continue

    # 先 hard-reset index 以便 loc 操作
    data_df = df.iloc[data_start:].copy().reset_index(drop=True)

    # col 2 (shoushou): 跨整个声首组填充
    data_df.iloc[:, 2] = data_df.iloc[:, 2].ffill()

    # col 3 (xiesheng_domain), col 4 (syllable_type): 跨声首组填充
    for ci in [3, 4]:
        data_df.iloc[:, ci] = data_df.iloc[:, ci].ffill()

    # F/G/H/I (col 5~8: 二級聲符/聲/韻/上推古音) 逐行独立，不作填充

    # 写回原始 df
    for idx_in_data, orig_idx in enumerate(range(data_start, len(df))):
        for ci in range(df.shape[1]):
            df.iloc[orig_idx, ci] = data_df.iloc[idx_in_data, ci]

    records = []
    header_skipped = False
    for _, row in df.iterrows():
        seq = row.iloc[0]
        if pd.isna(seq) or seq == "本表序":
            if not header_skipped:
                header_skipped = True
                continue
            continue
        try:
            seq = int(float(seq))
        except (ValueError, TypeError):
            continue

        raw_chars = _clean(row.iloc[16])
        chars_parsed = _parse_chars_with_corrections(raw_chars)
        raw_note = _clean(row.iloc[17])
        notes_parsed = _parse_notes_with_chars(raw_note, chars_parsed)

        init = _clean(row.iloc[9])
        kh = _clean(row.iloc[10])
        deng = _clean(row.iloc[11])
        yun = _clean(row.iloc[12])
        ton = _clean(row.iloc[13])
        rec = {
            "seq": seq,
            "xieyun_seq": _int_or_none(row.iloc[1]),
            "shoushou": _clean(row.iloc[2]),
            "xiesheng_domain": _clean(row.iloc[3]),
            "syllable_type": _clean(row.iloc[4]),
            "secondary": _clean(row.iloc[5]),
            "sheng": _clean(row.iloc[6]),
            "yun": _clean(row.iloc[7]),
            "old_phonetic_ref": _clean(row.iloc[8]),
            "status": f"{init}-{kh}-{deng}-{yun}-{ton}",
            "qieyu": _clean(row.iloc[14]),
            "qiepin": _clean(row.iloc[15]),
            "chars_raw": raw_chars,
            "chars": [c["char"] for c in chars_parsed],
            "corrections": {c["char"]: c["corrected_to"] for c in chars_parsed if c["corrected_to"]},
            "notes_raw": raw_note,
            "notes": notes_parsed,
            "previous_views": _clean(row.iloc[18]),
        }
        if rec["shoushou"] or rec["status"] or rec["chars"]:
            records.append(rec)
    return records


def parse_special_table(df: pd.DataFrame) -> list[dict]:
    """解析《廣韻》特殊字表"""
    records = []
    header_skipped = False
    for _, row in df.iterrows():
        seq = row.iloc[0]
        if pd.isna(seq) or seq == "本表序":
            if not header_skipped:
                header_skipped = True
                continue
            continue
        try:
            seq = int(float(seq))
        except (ValueError, TypeError):
            continue

        raw_oc = _clean(row.iloc[3])
        oc_parsed = _parse_chars_with_corrections(raw_oc)
        raw_note = _clean(row.iloc[11]) if len(row) > 11 else ""
        notes_parsed = _parse_notes_with_chars(raw_note, oc_parsed)

        rec = {
            "seq": seq,
            "xieyun_seq": _int_or_none(row.iloc[1]),
            "type": _clean(row.iloc[2]),
            "original_char_raw": raw_oc,
            "original_chars": [c["char"] for c in oc_parsed],
            "corrections": {c["char"]: c["corrected_to"] for c in oc_parsed if c["corrected_to"]},
            "status": f"{_clean(row.iloc[4])}-{_clean(row.iloc[5])}-{_clean(row.iloc[6])}-{_clean(row.iloc[7])}-{_clean(row.iloc[8])}",
            "qieyu": _clean(row.iloc[9]),
            "qiepin": _clean(row.iloc[10]),
            "notes_raw": raw_note,
            "notes": notes_parsed,
        }
        records.append(rec)
    return records


def parse_refs(df: pd.DataFrame) -> list[dict]:
    """解析參考文獻"""
    records = []
    for _, row in df.iterrows():
        author = _clean(row.iloc[1])
        title = _clean(row.iloc[3])
        if not author or not title or author == "作者":
            continue
        rec = {
            "type": _clean(row.iloc[0]),
            "author": author,
            "year": _clean(row.iloc[2]),
            "title": title,
            "publisher": _clean(row.iloc[4]),
            "note": _clean(row.iloc[5]),
            "status": _clean(row.iloc[6]),
        }
        records.append(rec)
    return records


def parse_initial_distribution(df: pd.DataFrame) -> dict:
    """
    解析上古聲首分布表（舊）
    返回结构包含 header 行和 data 行
    """
    # 第0行是主 header (I, E, Ə, A, U, O)
    # 第1行是子 header (I, IŊ~IN, IK~IT, ...)

    headers = []
    data_rows = []

    for i, (_, row) in enumerate(df.iterrows()):
        if i == 0:
            # 主元音行
            main_vowels = {}
            for ci, val in enumerate(row):
                v = _clean(val)
                if v:
                    main_vowels[ci] = v
            headers.append({"row": 0, "type": "main_vowel", "data": main_vowels})
        elif i == 1:
            # 韵尾行
            coda = {}
            for ci, val in enumerate(row):
                v = _clean(val)
                if v:
                    coda[ci] = v
            headers.append({"row": 1, "type": "coda", "data": coda})
        else:
            # 数据行
            dull = _clean(row.iloc[0]) or ""  # 鈍/銳
            series = _clean(row.iloc[1]) or ""  # P, M, W, K 等
            group = _clean(row.iloc[2]) or ""  # 幫, 明, 云, 見 等

            cells = {}
            for ci in range(3, len(row)):
                v = _clean(row.iloc[ci])
                if v:
                    cells[ci] = v

            if series or group:
                data_rows.append(
                    {
                        "dull_sharp": dull,
                        "series": series,
                        "group": group,
                        "cells": cells,
                    }
                )

    # 将头两行解析为结构化元音-韵尾矩阵标签
    vowel_coda_labels = {}
    if len(headers) >= 2:
        main_v = headers[0]["data"]
        coda = headers[1]["data"]
        # 合并
        for ci in sorted(set(list(main_v.keys()) + list(coda.keys()))):
            mv = main_v.get(ci, "")
            cd = coda.get(ci, "")
            vowel_coda_labels[ci] = (mv, cd)

    return {
        "headers": headers,
        "vowel_coda_labels": vowel_coda_labels,
        "rows": data_rows,
    }


def _clean(val) -> str:
    if pd.isna(val):
        return ""
    s = str(val).strip().replace("\u3000", "").replace("\xa0", "")
    return s


def _int_or_none(val):
    if pd.isna(val):
        return None
    try:
        return int(float(val))
    except (ValueError, TypeError):
        return None


# ─── 字符解析增强 ─────────────────────────────────────────

# IDS 运算符集合（用于识别 IDS 序列）
IDS_OPS = {"⿰", "⿱", "⿲", "⿳", "⿴", "⿵", "⿶", "⿷", "⿸", "⿹", "⿺", "⿻", "⿼", "⿽", "〾", "⿾", "⿿"}


def _parse_chars_with_corrections(chars_str: str) -> list[dict]:
    """
    解析字列，处理 A<B> 讹字标记和 IDS 序列。

    输入: "𨲂<䦊>䘀阜" 或 "⿱冂父<𠬛>" 或 "䅵𫌉<禚>"
    输出: [
        {"char": "𨲂", "corrected_to": "䦊"},
        {"char": "䘀"},
        {"char": "阜"},
    ]
    """
    if not chars_str:
        return []

    result = []
    # 用正则匹配：要么是 IDS 序列（以 IDS 运算符开头），要么是普通字符
    # IDS 序列可能包含 <...> 讹字标记
    i = 0
    while i < len(chars_str):
        ch = chars_str[i]

        # 检测 IDS 序列开头
        if ch in IDS_OPS or (i + 1 < len(chars_str) and chars_str[i : i + 1] in IDS_OPS):
            # 扫描到下一个空白或独立字符为止
            j = i
            depth = 0
            while j < len(chars_str):
                c = chars_str[j]
                if c == "<":
                    depth += 1
                elif c == ">":
                    depth -= 1
                    if depth < 0:
                        break
                elif depth == 0 and (c == " " or c == "\t" or c == "\u3000"):
                    break
                elif depth == 0 and j > i and c not in IDS_OPS and ord(c) > 0x2FFF and ord(c) < 0x3400:
                    # 遇到普通字符（不是IDS运算符也不是IDS的一部分）
                    # 检查是否可能是单独的字
                    break
                j += 1

            token = chars_str[i:j]
            # 检查是否有 <B> 标记
            correction = None
            m = re.match(r"^(.*?)<(.*?)>(.*)$", token)
            if m:
                token = (m.group(1) + m.group(3)).strip()
                correction = m.group(2).strip()
            if token:
                result.append({"char": token, "corrected_to": correction})
            i = j
            continue

        # 检测 < 开始的讹字标记（前一个字的后半部分已经处理了）
        if ch == "<":
            # 找到对应的 >
            j = chars_str.index(">", i) if ">" in chars_str[i:] else len(chars_str)
            # 这应该已经在前一个字的处理中被捕获了
            i = j + 1
            continue

        # 普通字符（包括 CJK 统一汉字）
        correction = None
        # 检查后面是否有 <B>
        if i + 1 < len(chars_str) and chars_str[i + 1] == "<":
            end = chars_str.index(">", i + 2) if ">" in chars_str[i + 2 :] else len(chars_str)
            correction = chars_str[i + 2 : end]
            result.append({"char": ch, "corrected_to": correction})
            i = end + 1
        elif ch.strip():
            result.append({"char": ch, "corrected_to": None})
            i += 1
        else:
            i += 1

    return result


def _parse_notes_with_chars(notes_str: str, chars_list: list[dict]) -> list[dict]:
    """
    解析 · 分隔的多条备注，尽量关联到具体的字。

    · 作为章节分隔符的特征：
      - 位于段首（前面是句号、引号结尾或字符串开头）
      - 后面紧跟字符名/IDS + 逗号
    而《廣韻·肴韻》这类内部的 · 不分割。

    输入 notes: "·𦮹，xxx。·䆁，yyy。"
    输入 chars: [{"char": "A"}, {"char": "B"}]
    输出: [{"char_ref": "A", "text": "..."}]
    """
    if not notes_str:
        return []

    # 保护《···」「···」（···）内部的 ·，以免被误分割
    protected = {}
    counter = [0]

    def _protect(m):
        counter[0] += 1
        key = f"\x00P{counter[0]}\x00"
        protected[key] = m.group(0)
        return key

    text = notes_str
    text = re.sub(r"《[^》]*》", _protect, text)
    text = re.sub(r"「[^」]*」", _protect, text)
    text = re.sub(r"（[^）]*）", _protect, text)

    # 现在按 · 分割（内部的 · 已被保护）
    raw_segments = re.split(r"·", text)
    raw_segments = [s.strip() for s in raw_segments if s.strip()]

    # 还原
    segments = []
    for seg in raw_segments:
        for key, val in protected.items():
            seg = seg.replace(key, val)
        segments.append(seg)

    result = []
    for seg in segments:
        stripped = seg.strip()
        if not stripped:
            continue

        # 取 segment 开头的字符/IDS 用于匹配 char_ref
        first_token = ""
        fc = stripped[0]
        if fc in IDS_OPS:
            m = re.match(r"^([⿰⿱⿲⿳⿴⿵⿶⿷⿸⿹⿺⿻][^，。；\s<>]{0,10})", stripped)
            if m:
                first_token = m.group(1)
        else:
            m = re.match(r"^([^，。；<>\s]{1,4})", stripped)
            if m:
                first_token = m.group(1)

        matched_char = ""
        if first_token:
            for c in chars_list:
                base = c["char"].replace(" ", "")
                if first_token in base or base in first_token:
                    matched_char = c["char"]
                    break

        result.append({"char_ref": matched_char, "text": seg})

    return result


def main():
    print("=== 解析 gy-20250226.xlsx ===")
    print(f"  文件: {XLSX_PATH}")
    print()

    xls = pd.ExcelFile(XLSX_PATH)

    result = {
        "meta": {
            "source": "gy-20250226.xlsx",
            "sheets": xls.sheet_names,
        },
        "rhyme_table": [],  # 小韻諧聲劃分
        "full_table": [],  # 全聲系表
        "special_table": [],  # 特殊字表
        "references": [],  # 參考文獻
        "initial_distribution": {},  # 上古聲首分布表
    }

    for sheet_name in xls.sheet_names:
        df = pd.read_excel(xls, sheet_name)
        sn = str(sheet_name).strip()
        print(f"  [{sn}] ({len(df)} rows)")

        if sn == "《廣韻》小韻諧聲劃分":
            result["rhyme_table"] = parse_main_rhyme_table(df)
            print(f"    → rhyme_table: {len(result['rhyme_table'])} 条")

        elif sn == "《廣韻》全聲系表":
            result["full_table"] = parse_full_table(df)
            print(f"    → full_table: {len(result['full_table'])} 条")

        elif sn == "《廣韻》特殊字表":
            result["special_table"] = parse_special_table(df)
            print(f"    → special_table: {len(result['special_table'])} 条")

        elif sn == "參考文獻":
            result["references"] = parse_refs(df)
            print(f"    → references: {len(result['references'])} 条")

        elif sn == "上古聲首分布表（舊）":
            result["initial_distribution"] = parse_initial_distribution(df)
            rows = len(result["initial_distribution"].get("rows", []))
            print(f"    → initial_distribution: {rows} 个声母组")

    # 保存
    with open(OUT_PATH, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2, ensure_ascii=False)

    print()
    print(f"  ✓ 已保存到 {OUT_PATH}")
    size_mb = OUT_PATH.stat().st_size / 1024 / 1024
    print(f"    大小: {size_mb:.1f} MB")


if __name__ == "__main__":
    main()
