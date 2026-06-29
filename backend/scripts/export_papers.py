#!/usr/bin/env python3
"""
将 paper.txt 和 gy 参考文献解析为 BibTeX 风格的 JSON。
每个条目包含结构化字段和一个预格式化的引用字符串。
"""

import json
import re
from pathlib import Path

REPO_DIR = Path(__file__).resolve().parent.parent.parent
DATA_DIR = REPO_DIR / "backend" / "data"
INPUT_DIR = REPO_DIR / "input"
GY_PATH = REPO_DIR / "data" / "gy-20250226.xlsx"

OUT_PATH = DATA_DIR / "papers.json"

# ─── 解析 paper.txt 引用 (C001, L005 等) ─────────────────


def parse_paper_txt(path: Path) -> list[dict]:
    """解析 paper.txt，每行格式：编号\t标题\turl"""
    records = []
    if not path.exists():
        return records
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            parts = line.split("\t")
            pid = parts[0].strip()
            title = parts[1].strip() if len(parts) >= 2 else ""
            url = parts[2].strip() if len(parts) >= 3 else ""
            if pid:
                rec = parse_title_to_fields(pid, title, url)
                records.append(rec)
    return records


def parse_title_to_fields(pid: str, title: str, url: str) -> dict:
    """
    将中文参考文献标题解析为结构化字段。

    常见格式：
      作者《文章名》（《期刊名》X辑，年份年，第X—X页）
      作者《书名》（地点：出版社，年份年）
      作者《文章名》（期刊名，年份年）
    """
    rec = {
        "id": pid,
        "type": "article",  # article, book, thesis, etc.
        "author": "",
        "year": "",
        "article_title": "",  # 文章/章节标题
        "book_title": "",  # 书名/期刊名
        "publisher": "",
        "location": "",
        "volume": "",
        "issue": "",
        "pages": "",
        "note": "",
        "url": url,
        "raw_title": title,
        "citation": title,  # formatted citation, will be refined
    }

    if not title:
        return rec

    # 提取括号外的作者名
    m = re.match(r"^([^《（(]+)", title)
    if m:
        rec["author"] = m.group(1).strip()

    # 提取《文章名》
    m = re.findall(r"《([^》]+)》", title)
    if m:
        rec["article_title"] = m[0]
    if len(m) >= 2:
        rec["book_title"] = m[1]

    # 提取年份
    m = re.search(r"(\d{4})年", title)
    if m:
        rec["year"] = m.group(1)

    # 提取页码
    m = re.search(r"第(\d+)[—\-](\d+)頁", title)
    if m:
        rec["pages"] = f"{m.group(1)}—{m.group(2)}"

    # 提取出版社
    m = re.search(r"[：:]([^，,）)]+出版社)", title)
    if m:
        rec["publisher"] = m.group(1)
    # 也提取 "出版社" 前的完整名称
    m = re.search(r"([^，,）)]+出版社)", title)
    if m and not rec["publisher"]:
        rec["publisher"] = m.group(1)

    # 提取地点（出版社前的城市名）
    m = re.search(r"[（(]([^：:）)]+)[：:]", title)
    if m:
        rec["location"] = m.group(1)

    # 判断类型
    if "碩士學位論文" in title or "博士學位論文" in title:
        rec["type"] = "thesis"
    elif "出版社" in title:
        rec["type"] = "book"

    # 构建格式化引用
    rec["citation"] = build_citation(rec)

    return rec


def build_citation(rec: dict) -> str:
    """生成格式化的参考文献引用字符串"""
    parts = []
    if rec["author"]:
        parts.append(rec["author"])

    if rec["article_title"]:
        t = f"《{rec['article_title']}》"
        parts.append(t)

    if rec["book_title"]:
        if rec["type"] == "book":
            parts.append(f"《{rec['book_title']}》")
        else:
            parts.append(f"《{rec['book_title']}》")

    if rec["volume"]:
        parts.append(rec["volume"])

    if rec["issue"]:
        parts.append(rec["issue"])

    if rec["year"]:
        year_clean = rec["year"].rstrip("年")
        parts.append(f"{year_clean}年")

    if rec["pages"]:
        parts.append(f"第{rec['pages']}頁")

    if rec["publisher"] and rec["type"] == "book":
        loc = f"{rec['location']}：" if rec["location"] else ""
        parts.append(f"{loc}{rec['publisher']}")

    if rec["note"]:
        parts.append(rec["note"])

    return "，".join(parts) if parts else rec["raw_title"]


# ─── 解析 gy 参考文献 ────────────────────────────────────


def parse_gy_refs() -> list[dict]:
    """从 gy-20250226.xlsx 读参考文献"""
    import pandas as pd

    xls = pd.ExcelFile(GY_PATH)
    refs = []
    # 尝试多个可能的 sheet 名称
    for sn in xls.sheet_names:
        s = str(sn).strip()
        if "文獻" in s or "参考" in s:
            df = pd.read_excel(xls, sn)
            for _, row in df.iterrows():
                author = str(row.iloc[1]).strip() if pd.notna(row.iloc[1]) else ""
                title = str(row.iloc[3]).strip() if len(row) > 3 and pd.notna(row.iloc[3]) else ""
                if not author or not title or author == "作者":
                    continue
                rec = {
                    "id": "",
                    "type": "book" if "專著" in str(row.iloc[0]) else "article",
                    "author": author,
                    "year": str(row.iloc[2]).strip() if pd.notna(row.iloc[2]) else "",
                    "article_title": "",
                    "book_title": title,
                    "publisher": str(row.iloc[4]).strip() if len(row) > 4 and pd.notna(row.iloc[4]) else "",
                    "location": "",
                    "volume": "",
                    "issue": "",
                    "pages": "",
                    "note": str(row.iloc[5]).strip() if len(row) > 5 and pd.notna(row.iloc[5]) else "",
                    "url": "",
                    "raw_title": f"{author}（{str(row.iloc[2]) if pd.notna(row.iloc[2]) else ''}）{title}",
                    "citation": "",
                }
                rec["citation"] = build_citation(rec)
                refs.append(rec)
            break
    return refs


# ─── 合并去重 ────────────────────────────────────────────


def merge_refs(paper_refs: list[dict], gy_refs: list[dict]) -> list[dict]:
    """合并 paper.txt 和 gy 参考文献"""
    seen = {}
    id_counter = [0]

    # paper refs 有 id
    for r in paper_refs:
        seen[r["id"]] = r
        id_counter[0] = max(id_counter[0], int(r["id"][1:]) if r["id"][1:].isdigit() else 0)

    # gy refs 分配 GYxxx 编号
    for r in gy_refs:
        id_counter[0] += 1
        r["id"] = f"GY{id_counter[0]:03d}"
        # 生成更好的 citation
        r["citation"] = build_citation(r)
        seen[r["id"]] = r

    # 排序
    def sort_key(item):
        rid = item[0]
        m = re.match(r"([A-Za-z]+)(\d+)", rid)
        if m:
            return (0, m.group(1), int(m.group(2)))
        return (1, rid, 0)

    sorted_items = sorted(seen.items(), key=sort_key)
    return [item[1] for item in sorted_items]


# ─── 主程序 ──────────────────────────────────────────────


def main():
    print("=== 解析参考文献 ===")

    # 解析 paper.txt
    paper_path = INPUT_DIR / "paper.txt"
    paper_refs = parse_paper_txt(paper_path)
    print(f"  paper.txt: {len(paper_refs)} 条")

    # 解析 gy 参考文献
    gy_refs = parse_gy_refs()
    print(f"  gy 参考文献: {len(gy_refs)} 条")

    # 合并
    all_refs = merge_refs(paper_refs, gy_refs)
    print(f"  合并后: {len(all_refs)} 条")

    # 保存
    with open(OUT_PATH, "w", encoding="utf-8") as f:
        json.dump({"papers": all_refs}, f, indent=2, ensure_ascii=False)

    # 打印前几条验证
    print()
    print("=== 示例 ===")
    for r in all_refs[:5]:
        print(f"  {r['id']:6s} | {r['citation'][:70]}")
    print("  ...")
    for r in all_refs[-3:]:
        print(f"  {r['id']:6s} | {r['citation'][:70]}")


if __name__ == "__main__":
    main()
