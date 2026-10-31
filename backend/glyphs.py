"""
甲骨文 / 小篆 字形表

两种字形都是「表外字」：字体文件把每个字形放在私用区，码位 = `0xF0000 + 序号 - 1`。

  * **小篆**：`backend/data/seal.ndjson`，每条就是 `{num, glyph, char}`：
    `num` 是字体里的字形序号（`00001`–`11108`），`glyph` 是私用区字符
    （和 `frontend/sw-ccz-1963-rev1.ttf` 对应），`char` 是它对应的今字
    （原表的 `zi_strict`，没有就用 `zi`）。
  * **甲骨文**：`backend/data/ob.jsonl`，每条就是 `{num, glyph, annotations}`，
    `glyph` 本身就是私用区字符（和 `ZihuiSongJGW.ttf` 对应）；按标注里的
    `con`（如 `匕(妣)`）找到跟某个今字对应的卜辞字形。

对外只提供「候选列表」：给一个字，返回两种字形的可选项，前端负责多选。
"""

from __future__ import annotations

import json
import re
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent / "data"
REPO = DATA_DIR.parent.parent

SEAL_FILE = DATA_DIR / "seal.ndjson"
OB_FILE = DATA_DIR / "ob.jsonl"

#: 字形码位起点（两种字体都用这一区段）
PUA_BASE = 0xF0000

#: `con` 里的前缀（`=字` / `*字` / `~字` / `?字`）和括注（`匕(妣)`）
_CON_STRIP_RE = re.compile(r"^[=~*?\s]+")
_CON_SPLIT_RE = re.compile(r"[\[\(（]")


# ─── 缓存 ──────────────────────────────────────────────────

_SEAL: dict = {"mtime": None, "by_char": {}, "all": []}
_OB: dict = {"mtime": None, "by_char": {}, "all": []}


def _mtime(path: Path) -> float:
    try:
        return path.stat().st_mtime
    except OSError:
        return -1.0


def codepoint(number: int) -> int:
    """序号 → 私用区码位（1 起）。"""
    return PUA_BASE + max(0, number - 1)


def _load_seal() -> None:
    mtime = _mtime(SEAL_FILE)
    if _SEAL["mtime"] == mtime:
        return
    by_char: dict[str, list[dict]] = {}
    rows: list[dict] = []
    if mtime >= 0:
        with open(SEAL_FILE, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                rec = json.loads(line)
                num = str(rec.get("num") or "").strip()
                glyph = rec.get("glyph") or ""
                if not num or not glyph:
                    continue
                item = {"num": num, "glyph": glyph, "char": rec.get("char") or ""}
                rows.append(item)
                if item["char"]:
                    by_char.setdefault(item["char"], []).append(item)
    _SEAL.update(mtime=mtime, by_char=by_char, all=rows)


def _con_char(con: str) -> str:
    """`匕(妣)` → `匕`；`=[與]` → `與`。"""
    s = _CON_STRIP_RE.sub("", (con or "").strip())
    s = _CON_SPLIT_RE.split(s)[0].strip("[] ")
    return s


def _load_ob() -> None:
    mtime = _mtime(OB_FILE)
    if _OB["mtime"] == mtime:
        return
    by_char: dict[str, list[dict]] = {}
    rows: list[dict] = []
    if mtime >= 0:
        with open(OB_FILE, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    rec = json.loads(line)
                except json.JSONDecodeError:
                    continue
                num = str(rec.get("num") or "").strip()
                glyph = rec.get("glyph") or ""
                if not num or not glyph:
                    continue
                anns = rec.get("annotations") or []
                item = {
                    "num": num,
                    "glyph": glyph,
                    "con": [a.get("con", "") for a in anns if a.get("con")],
                    "comm": " ".join(a.get("comm", "") for a in anns if a.get("comm")),
                }
                rows.append(item)
                for con in item["con"]:
                    zi = _con_char(con)
                    if zi:
                        by_char.setdefault(zi, []).append(item)
    _OB.update(mtime=mtime, by_char=by_char, all=rows)


# ─── 对外 ──────────────────────────────────────────────────


def seal_candidates(char: str = "", q: str = "", limit: int = 240) -> dict:
    """小篆候选：先给 `char` 对应的字形，再按搜索词（编号 / 今字）在整表里搜。"""
    _load_seal()
    char = (char or "").strip()
    q = (q or "").strip()
    out: list[dict] = []
    seen: set[str] = set()

    def push(items):
        for it in items:
            if it["num"] in seen:
                continue
            seen.add(it["num"])
            out.append(it)

    if char:
        push(_SEAL["by_char"].get(char, []))
    if q:
        low = q.strip().lower()
        low_num = low.lstrip("0") or low
        push([i for i in _SEAL["all"]
              if low_num == i["num"].lstrip("0") or (low and low in i["char"])])
    total = len(out)
    return {"results": out[:limit], "total": total}


def ob_candidates(char: str = "", q: str = "", limit: int = 240) -> dict:
    """甲骨文候选：先给标注里就是这个字的，再按编号 / 字 / 释文搜索。"""
    _load_ob()
    char = (char or "").strip()
    q = (q or "").strip()
    out: list[dict] = []
    seen: set[str] = set()

    def push(items):
        for it in items:
            if it["num"] in seen:
                continue
            seen.add(it["num"])
            out.append(it)

    if char:
        push(_OB["by_char"].get(char, []))
    if q:
        low = q.lower()
        push([i for i in _OB["all"]
              if low in i["num"] or low in i["comm"]
              or any(low in c.lower() for c in i["con"])])
    total = len(out)
    return {"results": out[:limit], "total": total}


def known_ob(nums) -> list[str]:
    """过滤出确实存在的甲骨文编号（保存时用）。"""
    _load_ob()
    valid = {i["num"] for i in _OB["all"]}
    return [str(n) for n in (nums or []) if str(n) in valid]


def known_seal(nums) -> list[str]:
    """过滤出字体里确实存在的小篆序号。"""
    _load_seal()
    valid = {i["num"] for i in _SEAL["all"]}
    return [str(s) for s in (nums or []) if str(s) in valid]


def stats() -> dict:
    _load_seal()
    _load_ob()
    return {"seal": len(_SEAL["all"]), "ob": len(_OB["all"])}
