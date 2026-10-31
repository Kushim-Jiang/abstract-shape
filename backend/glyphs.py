"""
甲骨文 / 小篆 字形表

两种字形都是「表外字」：字体文件把每个字形放在私用区，码位 = `0xF0000 + 序号 - 1`。

  * **小篆**：`backend/data/tab_unicode.tsv` 给出 `unicode_cid`（如 `C-01998`），
    字形在 `frontend/sw-ccz-1963-rev1.ttf` 里，码位 `0xF0000 + cid 数字 - 1`
    （11108 个形）。查某个字的小篆，按表里的 `zi_strict` → `zi` 两列找。
    注意：表里的 `sid`（`S01996`）是另一套编号，跟字体里的顺序对不上，
    只有 `unicode_cid` 才是字体的字形序号。
  * **甲骨文**：`backend/data/ob.jsonl`，每条就是 `{num, glyph, annotations}`，
    `glyph` 本身就是私用区字符（和 `ZihuiSongJGW.ttf` 对应）；按标注里的
    `con`（如 `匕(妣)`）找到跟某个今字对应的卜辞字形。

对外只提供「候选列表」：给一个字，返回两种字形的可选项，前端负责多选。
"""

from __future__ import annotations

import csv
import json
import re
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent / "data"
REPO = DATA_DIR.parent.parent

SEAL_TSV = DATA_DIR / "tab_unicode.tsv"
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


def _sid_number(sid: str) -> int:
    m = re.search(r"(\d+)", sid or "")
    return int(m.group(1)) if m else 0

def codepoint(number: int) -> int:
    """序号 → 私用区码位（1 起）。"""
    return PUA_BASE + max(0, number - 1)


def _load_seal() -> None:
    mtime = _mtime(SEAL_TSV)
    if _SEAL["mtime"] == mtime:
        return
    by_char: dict[str, list[dict]] = {}
    rows: list[dict] = []
    if mtime >= 0:
        with open(SEAL_TSV, "r", encoding="utf-8", newline="") as f:
            for row in csv.DictReader(f, delimiter="\t"):
                cid = (row.get("unicode_cid") or "").strip()
                num = _sid_number(cid)
                if not num:
                    # 没有 unicode_cid 的行在这套字体里没有字形
                    continue
                item = {
                    "cid": cid,
                    "num": num,
                    "id": (row.get("id") or "").strip(),
                    "zi": (row.get("zi") or "").strip(),
                    "zi_strict": (row.get("zi_strict") or "").strip(),
                    "type": (row.get("type") or "").strip(),
                    "unicode": (row.get("unicode") or "").strip(),
                    "cp": codepoint(num),
                }
                rows.append(item)
                for key in {item["zi"], item["zi_strict"]}:
                    if key:
                        by_char.setdefault(key, []).append(item)
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
    """小篆候选：`zi_strict` 命中的排前面，其次 `zi` 命中，最后是搜索词命中。"""
    _load_seal()
    char = (char or "").strip()
    q = (q or "").strip()
    out: list[dict] = []
    seen: set[str] = set()

    def push(items):
        for it in items:
            if it["cid"] in seen:
                continue
            seen.add(it["cid"])
            out.append(it)

    if char:
        push([i for i in _SEAL["by_char"].get(char, []) if i["zi_strict"] == char])
        push(_SEAL["by_char"].get(char, []))
    if q:
        low = q.lower()
        push([i for i in _SEAL["all"]
              if low in i["cid"].lower() or low in i["zi"] or low in i["zi_strict"]
              or low in i["id"] or low in i["unicode"]])
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


def known_seal(cids) -> list[str]:
    """过滤出确实存在的小篆 cid。"""
    _load_seal()
    valid = {i["cid"] for i in _SEAL["all"]}
    return [str(s) for s in (cids or []) if str(s) in valid]


def stats() -> dict:
    _load_seal()
    _load_ob()
    return {"seal": len(_SEAL["all"]), "ob": len(_OB["all"])}
