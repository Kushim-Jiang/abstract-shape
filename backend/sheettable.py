"""
抽构数据 / 字表数据 的加载

从 `input/` 与 `backend/data/` 里读原始数据，供上层使用：

  * `input/abstract_*.txt`  —— 抽构表（char / src_one / src_two / comment）
  * `input/xiangxing.txt`   —— 象形部件（构件 → 十进制自然分类码）
  * `backend/data/characters.jsonl` —— 全字表（97712 字，带标注）
  * `backend/data/ob.jsonl`         —— 甲骨文
  * `backend/data/geta.json`        —— 谚文（口诀字）

与 `src/build_json.py` 的区别：这里只做**读**，不改动上游数据，
并且把 `ids.py` 的解析换成 `backend/shape.py`（无第三方依赖）。
"""

from __future__ import annotations

import json
import re
from pathlib import Path

from . import shape

REPO = Path(__file__).resolve().parent.parent
INPUT_DIR = REPO / "input"
DATA_DIR = Path(__file__).resolve().parent / "data"

#: 抽构表的分卷（与 src/build_json.py 的 FILE_NAMES 对应）
SHEET_NAMES = ("main", "a", "b", "ci", "gh")

#: 参考文献短码 → 链接（src/build_json.py 里的 PAPER 映射，缺则原样显示）
_PAPERS: dict[str, str] = {}


def _load_papers() -> dict[str, str]:
    global _PAPERS
    if _PAPERS:
        return _PAPERS
    path = DATA_DIR / "papers.json"
    if path.exists():
        data = json.loads(path.read_text(encoding="utf-8"))
        for p in data.get("papers", []):
            pid = p.get("id")
            if pid:
                _PAPERS[pid] = p.get("citation") or p.get("raw_title") or pid
    return _PAPERS


def _split_tsv(line: str, n: int) -> list[str]:
    parts = line.rstrip("\n").split("\t")
    parts += [""] * n
    return [p.strip() for p in parts[:n]]


# ─── 抽构表 ────────────────────────────────────────────────


def load_sheet() -> dict[str, dict]:
    """读取 input/abstract_*.txt，返回 {char: {src_one, src_two, comment, sheet}}。"""
    out: dict[str, dict] = {}
    for name in SHEET_NAMES:
        path = INPUT_DIR / f"abstract_{name}.txt"
        if not path.exists():
            continue
        with path.open("r", encoding="utf-8") as f:
            for line in f:
                if not line.strip():
                    continue
                char, src_one, src_two, comment = _split_tsv(line, 4)
                if not char:
                    continue
                # 后面的分卷不覆盖 main 里已有的内容
                if char in out and name != "main":
                    continue
                out[char] = {
                    "char": char,
                    "src_one": src_one,
                    "src_two": src_two,
                    "comment": comment,
                    "sheet": name,
                }
    return out


def load_xiangxing() -> dict[str, str]:
    """读取 input/xiangxing.txt，返回 {构件: 自然分类码}。"""
    out: dict[str, str] = {}
    path = INPUT_DIR / "xiangxing.txt"
    if not path.exists():
        return out
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            parts = _split_tsv(line, 2)
            if parts[0]:
                out[parts[0]] = parts[1]
    return out


def load_geta() -> dict[str, str]:
    """谚文口诀字：构件 → 说明。"""
    path = DATA_DIR / "geta.json"
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8")).get("geta", {})
    return {}


# ─── 由抽构表推导：变体 / 父级 ─────────────────────────────


def build_index() -> dict:
    """把抽构表整理成前端要用的索引。

    返回::

        {
          "shapes":  {抽构: "主形@变体..."},
          "parents": {抽构: [直接上级抽构, ...]},
          "entries": {字: {sheet, src_one, src_two, comment}},
        }
    """
    sheet = load_sheet()

    # 抽构 → 主形与变体
    shapes: dict[str, list[list[str]]] = {}
    for char, e in sheet.items():
        src = e["src_one"]
        if not src or src == "X":
            continue
        if src.startswith("="):
            # `=字`：异体关系，不是抽构
            continue
        norm = shape.normalize(src)
        if not norm:
            continue
        bucket = shapes.setdefault(norm, [[], []])
        if char not in bucket[0] and char not in norm:
            bucket[0].append(char)

    # 抽构 → 直接上级（谁把它当作部件）
    parents: dict[str, set[str]] = {}
    keys = list(shapes)
    for norm in keys:
        for other in keys:
            if other == norm:
                continue
            if norm in other:
                parents.setdefault(norm, set()).add(other)

    return {
        "shapes": {
            k: "".join(v[0]) + ("@" + "".join(sorted(v[1])) if v[1] else "")
            for k, v in shapes.items()
        },
        "parents": {k: sorted(v) for k, v in parents.items()},
        "entries": {
            char: {
                "sheet": e["sheet"],
                "src_one": e["src_one"],
                "src_two": e["src_two"],
                "comment": e["comment"],
            }
            for char, e in sheet.items()
        },
    }


def lookup(char: str, index: dict | None = None) -> dict:
    """查一个字的抽构来源（抽构表里的原始记录）。

    返回 `{found, src_one, src_two, comment, shape, variants, parents}`。
    """
    idx = index if index is not None else build_index()
    e = idx["entries"].get(char)
    if not e:
        return {"found": False}

    src_one = e["src_one"]
    norm = ""
    if src_one and src_one != "X" and not src_one.startswith("="):
        norm = shape.normalize(src_one)
    # 自指（`丂 -> [丂]`）不是抽构：一个字不能是自己的部件
    if norm and norm == "[" + char + "]":
        norm = ""

    variants = ""
    parents: list[str] = []
    if norm:
        variants = idx["shapes"].get(norm, "")
        parents = idx["parents"].get(norm, [])

    return {
        "found": True,
        "src_one": src_one,
        "src_two": e["src_two"],
        "comment": e["comment"],
        "sheet": e["sheet"],
        "shape": norm,
        "variants": variants,
        "parents": parents,
    }
