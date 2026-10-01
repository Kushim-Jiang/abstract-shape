"""
抽构条（entry）存储

**一条札记 = 一行 ndjson**，键是 `(字, 条号)`：

    {"char": "丂", "seq": 1, "con": "⿱一丂", "ref_con": "*考",
     "notes": "……", "refs": [{"id": "L005", "pages": "12—15"}]}

  * `con`      抽构（IDS 表达式，`backend/shape.py` 校验，可空）
  * `ref_con`  参考抽构（同上，通常是 `=字` / `*字` 这种非 IDS 写法，不做校验）
  * `notes`    札记正文（自由 Markdown）
  * `refs`     引用列表。每条是一个 dict：
                 `id`    文献编号（`backend/refs.py` 里文献的 id）
                 `pages` **这一条引用所指的页码范围**，可空
               `pages` 与文献自身的总页码（`refs.pages`）不同：
               比如整本书 100—300 页，这里只引其中的 120—135 页。
               旧数据里 `refs` 是纯字符串列表，载入时自动升格成 dict。

一个字可以有多条，条号从 1 开始，引用写作 `字-n`（如 `丂-1`）。

文件：`abstract-shape/abstract-shape.ndjson`。
内存缓存 + 按 mtime 自动失效，外部改文件后 API 立刻能看到。
"""

from __future__ import annotations

import json
import re
from pathlib import Path

from . import shape

# ─── 常量 ──────────────────────────────────────────────────

DATA_DIR = Path(__file__).resolve().parent.parent / "abstract-shape"
DATA_FILE = DATA_DIR / "abstract-shape.ndjson"

#: 条号上限，防止写出离谱的记录
MAX_SEQ = 999


# ─── 内存缓存 ──────────────────────────────────────────────

#: {(字, 条号): {char, seq, con, ref_con, notes, refs}}
_ENTRIES: dict[tuple[str, int], dict] = {}
_LOADED = False
_MTIME: float = -1.0


def _clean_refs(value) -> list[dict]:
    """规整引用列表。

    每条引用是一个 dict：`{"id": "L005", "pages": "12—15"}`。
    兼容旧写法（纯字符串 / 字符串列表 / "L005:12-15"），统一升格成 dict。
    `pages` 是**这一条引用所指的页码**，与文献本身的总页码范围（`refs.pages`）
    是两回事 —— 比如整本书 100—300 页，这里只引其中的 120—135 页。
    """
    if value is None:
        value = []
    if isinstance(value, (str, dict)):
        value = [value]

    out: list[dict] = []
    for v in value:
        if isinstance(v, dict):
            rid = str(v.get("id") or v.get("ref") or "").strip()
            pages = str(v.get("pages") or v.get("page") or "").strip()
        else:
            s = str(v).strip()
            if not s:
                continue
            # `L005:12-15` / `L005 12-15` / `L005` 都能认
            m = re.match(r"^(?P<id>[^\s:：]+)\s*(?:[:：]\s*(?P<pages>.+))?$", s)
            if not m:
                continue
            rid = m.group("id").strip()
            pages = (m.group("pages") or "").strip()
        if not rid:
            continue
        rec = {"id": rid}
        if pages:
            rec["pages"] = pages
        out.append(rec)
    return out


def _norm_entry(rec: dict) -> dict | None:
    """把一行 json 规整成一条 entry；字为空则丢弃。"""
    ch = (rec.get("char") or "").strip()
    if not ch:
        return None
    try:
        seq = int(rec.get("seq") or 0)
    except (TypeError, ValueError):
        seq = 0
    if seq < 1:
        seq = 1
    return {
        "char": ch,
        "seq": seq,
        "con": (rec.get("con") or "").strip(),
        "ref_con": (rec.get("ref_con") or "").strip(),
        "notes": rec.get("notes") or "",
        "refs": _clean_refs(rec.get("refs")),
    }


def merge_legacy_refs(old, new) -> list[dict]:
    """保存时：旧引用里没填页码的，保留旧页码（前端只传 id 时别把页码抹掉）。"""
    olds = {r["id"]: r for r in _clean_refs(old)}
    out: list[dict] = []
    for r in _clean_refs(new):
        if not r.get("pages") and r["id"] in olds and olds[r["id"]].get("pages"):
            r["pages"] = olds[r["id"]]["pages"]
        out.append(r)
    return out


def _load() -> None:
    """载入 ndjson；文件被外部改动（mtime 变化）时自动重载。"""
    global _LOADED, _MTIME
    try:
        mtime = DATA_FILE.stat().st_mtime
    except OSError:
        mtime = -1.0

    if _LOADED and mtime == _MTIME:
        return

    _ENTRIES.clear()
    if mtime >= 0:
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    rec = json.loads(line)
                except json.JSONDecodeError:
                    continue
                e = _norm_entry(rec)
                if e is None:
                    continue
                key = (e["char"], e["seq"])
                # 同一 (字, 条号) 重复时后者覆盖
                _ENTRIES[key] = e
    _LOADED = True
    _MTIME = mtime


def reload() -> int:
    """强制重新读盘，返回条数。"""
    global _LOADED
    _LOADED = False
    _load()
    return len(_ENTRIES)


def _flush() -> None:
    """写回 ndjson：按 (字, 条号) 排序，diff 稳定。

    全空的条也照写（`{"char":"一","seq":1}`）—— 它表示「这个字已收录」，
    是左侧列表计数的依据，不能当垃圾丢掉。
    """
    global _MTIME
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    tmp = DATA_FILE.with_name(DATA_FILE.name + ".tmp")
    with open(tmp, "w", encoding="utf-8", newline="\n") as f:
        for key in sorted(_ENTRIES):
            e = _ENTRIES[key]
            out = {"char": e["char"], "seq": e["seq"]}
            if e["con"]:
                out["con"] = e["con"]
            if e["ref_con"]:
                out["ref_con"] = e["ref_con"]
            if e["notes"]:
                out["notes"] = e["notes"]
            if e["refs"]:
                out["refs"] = e["refs"]
            f.write(json.dumps(out, ensure_ascii=False) + "\n")
    tmp.replace(DATA_FILE)
    try:
        _MTIME = DATA_FILE.stat().st_mtime
    except OSError:
        _MTIME = -1.0


def flush() -> None:
    _load()
    _flush()


# ─── 读 ────────────────────────────────────────────────────


def entries_of(char: str) -> list[dict]:
    """一个字的全部条，按条号排序。"""
    _load()
    return [dict(e) for k, e in sorted(_ENTRIES.items()) if k[0] == char]


def get_entry(char: str, seq: int) -> dict | None:
    _load()
    e = _ENTRIES.get((char, seq))
    return dict(e) if e else None


def count_entries(char: str) -> int:
    _load()
    return sum(1 for k in _ENTRIES if k[0] == char)


def counts() -> dict[str, int]:
    """{字: 条数}，只含有条的字。"""
    _load()
    out: dict[str, int] = {}
    for ch, _seq in _ENTRIES:
        out[ch] = out.get(ch, 0) + 1
    return out


def characters_with_entries() -> list[str]:
    _load()
    return sorted({ch for ch, _ in _ENTRIES})


def stats() -> dict:
    _load()
    return {
        "entries": len(_ENTRIES),
        "characters": len({ch for ch, _ in _ENTRIES}),
        "file": DATA_FILE.name,
    }


def entry_key(char: str, seq: int) -> str:
    """`丂-1` 这种引用写法。"""
    return f"{char}-{seq}"


def parse_key(key: str) -> tuple[str, int] | None:
    """把 `丂-1` 解析成 (字, 条号)；解析不出返回 None。"""
    m = re.match(r"^(?P<char>.+?)-(?P<seq>\d+)$", (key or "").strip())
    if not m:
        return None
    seq = int(m.group("seq"))
    if seq < 1:
        return None
    return m.group("char"), seq


# ─── 写 ────────────────────────────────────────────────────


def write_entry(char: str, seq: int, con: str = "", ref_con: str = "",
                notes: str = "", refs=None) -> dict:
    """写入 / 覆盖一条。seq<=0 时自动分配下一个可用条号。"""
    _load()
    char = char.strip()
    seq = int(seq or 0)
    if seq < 1:
        seq = next_seq(char)
    rec = {
        "char": char,
        "seq": seq,
        "con": (con or "").strip(),
        "ref_con": (ref_con or "").strip(),
        "notes": notes or "",
        "refs": _clean_refs(refs),
    }
    _ENTRIES[(char, seq)] = rec
    _flush()
    return dict(rec)


def next_seq(char: str) -> int:
    """这个字的下一个可用条号（1 起）。"""
    _load()
    used = {s for c, s in _ENTRIES if c == char}
    s = 1
    while s in used and s < MAX_SEQ:
        s += 1
    return s


def delete_entry(char: str, seq: int) -> bool:
    _load()
    if (char, seq) in _ENTRIES:
        del _ENTRIES[(char, seq)]
        _flush()
        return True
    return False


def delete_character(char: str) -> int:
    """删掉一个字的所有条，返回删了几条。"""
    _load()
    keys = [k for k in _ENTRIES if k[0] == char]
    for k in keys:
        del _ENTRIES[k]
    if keys:
        _flush()
    return len(keys)


# ─── 引用格式化 ────────────────────────────────────────────


def ref_label(r: dict) -> str:
    """`L005` 或 `L005:12—15`（带本条的页码范围）。"""
    rid = r.get("id") or ""
    pages = (r.get("pages") or "").strip()
    return f"{rid}:{pages}" if pages else rid


def refs_text(refs) -> str:
    return "、".join(ref_label(r) for r in _clean_refs(refs))


# ─── 预览：把一个字的全部条合成 Markdown ──────────────────


def render_character(char: str) -> str:
    """该字所有条的合并 Markdown（预览用）。"""
    es = entries_of(char)
    lines = [f"# {char}", ""]
    if not es:
        lines.append("（还没有条）")
        return "\n".join(lines) + "\n"

    for e in es:
        lines.append(f"## {entry_key(char, e['seq'])}")
        lines.append("")
        if e["con"]:
            lines.append(f"- 抽构：`{e['con']}`")
        if e["ref_con"]:
            lines.append(f"- 参考抽构：`{e['ref_con']}`")
        if e["con"] or e["ref_con"]:
            lines.append("")
        if e["notes"].strip():
            lines.append(e["notes"].strip())
            lines.append("")
        if e["refs"]:
            lines.append("文献：" + refs_text(e["refs"]))
            lines.append("")
    return "\n".join(lines).replace("\n\n\n", "\n\n").rstrip() + "\n"


def validate_entry(con: str, ref_con: str = "") -> dict:
    """校验抽构；参考抽构只在非空且看起来像 IDS 时才校验。"""
    out = {"con": shape.validate(con)}
    rc = (ref_con or "").strip()
    if rc:
        # `=字` / `*字` 这类是标注约定，不是 IDS，不校验
        looks_ids = not rc.startswith(("=", "*", "~", "?"))
        out["ref_con"] = shape.validate(rc) if looks_ids else {"ok": True, "skipped": True}
    else:
        out["ref_con"] = {"ok": True, "skipped": True}
    out["ok"] = bool(out["con"].get("ok") and out["ref_con"].get("ok"))
    return out
