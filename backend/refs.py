"""
参考文献存储（BibTeX 式）

数据来源有两份，**只读一份、可写一份**：

  * `backend/data/papers.json`  —— 从上游导出的已有文献（97 条），只读；
  * `abstract-shape/references.ndjson` —— 本仓库新增 / 修改的文献，一行一条。

读取时先放只读的，再用可写的按 `id` 覆盖，所以改动都落在后者，
上游数据不动，git diff 干净。

字段（对齐 BibTeX）::

    id           引用键，如 C001
    type         article / book / incollection / thesis / misc ...
    author       作者列表（数组），每个元素一个人名
    editor       编者列表（数组）
    year         年
    date         完整日期，如 2007-05-01
    article_title  文章名（article 用）
    book_title     期刊名 / 书名（article 用期刊，inbook 用书名）
    journal        期刊名（显式字段，优先于 book_title）
    publisher    出版社
    location     出版地
    volume       卷
    number       期（BibTeX 的 `number`）
    pages        页码，如 243—272
    url
    doi
    note
"""

from __future__ import annotations

import json
import re
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent / "data"
REPO = DATA_DIR.parent.parent
STORE_DIR = REPO / "abstract-shape"
STORE_FILE = STORE_DIR / "references.ndjson"

#: 内置只读文献
BUILTIN_FILE = DATA_DIR / "papers.json"
#: 广韵专用文献（只读）
BUILTIN_GY_FILE = DATA_DIR / "papers_gy.json"

#: 字段定义：(key, 中文名, 类型, BibTeX 名)
#: 类型 text | list | multiline
FIELDS: list[tuple[str, str, str, str]] = [
    ("id", "引用键", "text", "key"),
    ("type", "类型", "type", "entrytype"),
    ("author", "作者", "list", "author"),
    ("editor", "编者", "list", "editor"),
    ("article_title", "篇名", "text", "title"),
    ("journal", "期刊", "text", "journal"),
    ("book_title", "书名 / 集名", "text", "booktitle"),
    ("publisher", "出版社", "text", "publisher"),
    ("location", "出版地", "text", "address"),
    ("year", "年", "text", "year"),
    ("date", "日期", "text", "date"),
    ("volume", "卷", "text", "volume"),
    ("number", "期", "text", "number"),
    ("pages", "页码", "text", "pages"),
    ("edition", "版次", "text", "edition"),
    ("url", "网址", "text", "url"),
    ("doi", "DOI", "text", "doi"),
    ("note", "备注", "multiline", "note"),
]

FIELD_KEYS = [f[0] for f in FIELDS]

ENTRY_TYPES = [
    ("article", "期刊论文"),
    ("book", "专著"),
    ("incollection", "文集析出"),
    ("inproceedings", "会议论文"),
    ("thesis", "学位论文"),
    ("report", "报告"),
    ("misc", "其他"),
]

# ─── 缓存 ──────────────────────────────────────────────────

_BUILTIN: dict[str, dict] = {}
_CUSTOM: dict[str, dict] = {}
_LOADED = False
_MTIME: float = -1.0


def _norm_authors(value) -> list[str]:
    """作者：接受数组 / 字符串（用 and、;、；、,、，分隔）。"""
    if isinstance(value, (list, tuple)):
        return [str(a).strip() for a in value if str(a).strip()]
    if not value:
        return []
    parts = re.split(r"\s+and\s+|[;;、]|,(?![^(]*\))", str(value))
    return [p.strip() for p in parts if p.strip()]


def _normalize(rec: dict) -> dict:
    out: dict = {}
    for key, _name, kind, _bib in FIELDS:
        v = rec.get(key, "")
        if kind == "list":
            out[key] = _norm_authors(v)
        else:
            out[key] = ("" if v is None else str(v)).strip()
    # 兼容上游 papers.json 的 book_title/raw_title
    if not out["journal"] and rec.get("type") == "article":
        out["journal"] = (rec.get("book_title") or "").strip()
    if not out["article_title"] and rec.get("raw_title"):
        out["article_title"] = ""
    out["_builtin"] = bool(rec.get("_builtin"))
    out["_citation"] = rec.get("citation", "")
    return out


def _load() -> None:
    global _LOADED, _MTIME
    try:
        mtime = STORE_FILE.stat().st_mtime
    except OSError:
        mtime = -1.0
    if _LOADED and mtime == _MTIME:
        return

    _BUILTIN.clear()
    if BUILTIN_FILE.exists():
        data = json.loads(BUILTIN_FILE.read_text(encoding="utf-8"))
        for r in data.get("papers", []):
            rid = r.get("id")
            if rid:
                r = dict(r)
                r["_builtin"] = True
                _BUILTIN[rid] = _normalize(r)

    _CUSTOM.clear()
    if mtime >= 0:
        with open(STORE_FILE, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    rec = json.loads(line)
                except json.JSONDecodeError:
                    continue
                rid = rec.get("id")
                if rid:
                    _CUSTOM[rid] = _normalize(rec)
    _LOADED = True
    _MTIME = mtime


def _flush() -> None:
    global _MTIME
    STORE_DIR.mkdir(parents=True, exist_ok=True)
    tmp = STORE_FILE.with_name(STORE_FILE.name + ".tmp")
    with open(tmp, "w", encoding="utf-8", newline="\n") as f:
        for rid in sorted(_CUSTOM):
            rec = {k: v for k, v in _CUSTOM[rid].items() if not k.startswith("_")}
            rec = {k: rec[k] for k in FIELD_KEYS if k in rec and rec[k] not in ("", [])}
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    tmp.replace(STORE_FILE)
    try:
        _MTIME = STORE_FILE.stat().st_mtime
    except OSError:
        _MTIME = -1.0


# ─── 对外 ──────────────────────────────────────────────────


def get(rid: str) -> dict | None:
    _load()
    return _CUSTOM.get(rid) or _BUILTIN.get(rid)


def next_id(prefix: str = "R") -> str:
    """生成一个没被占用的引用键。"""
    _load()
    used = set(_CUSTOM) | set(_BUILTIN)
    i = 1
    while f"{prefix}{i:03d}" in used:
        i += 1
    return f"{prefix}{i:03d}"


def list_all(q: str = "") -> list[dict]:
    """全部文献（自建覆盖内置），按引用键排序。"""
    _load()
    merged = dict(_BUILTIN)
    merged.update(_CUSTOM)
    out = list(merged.values())
    q = (q or "").lower()
    if q:
        def hit(r):
            return q in " ".join([
                r.get("id", ""),
                " ".join(r.get("author") or []),
                r.get("article_title", ""),
                r.get("journal", ""),
                r.get("book_title", ""),
                r.get("year", ""),
                r.get("_citation", ""),
            ]).lower()
        out = [r for r in out if hit(r)]
    out.sort(key=lambda r: (r.get("id", "")))
    return out


def save(rec: dict) -> dict:
    """新增 / 覆盖一条文献。"""
    _load()
    rid = (rec.get("id") or "").strip()
    if not rid:
        rid = next_id()
    rec = dict(rec)
    rec["id"] = rid
    rec["_builtin"] = False
    _CUSTOM[rid] = _normalize(rec)
    _flush()
    return _CUSTOM[rid]


def delete(rid: str) -> bool:
    """删除。内置文献不能真删，只能标记为隐藏（写一条同 id 的空覆盖？不）。

    这里只允许删自建的；内置的返回 False。
    """
    _load()
    if rid in _CUSTOM:
        del _CUSTOM[rid]
        _flush()
        return True
    return False


def is_builtin(rid: str) -> bool:
    _load()
    return rid in _BUILTIN and rid not in _CUSTOM


def gy_references() -> list[dict]:
    """广韵专用文献（只读）。"""
    if not BUILTIN_GY_FILE.exists():
        return []
    return json.loads(BUILTIN_GY_FILE.read_text(encoding="utf-8"))


def stats() -> dict:
    _load()
    return {
        "total": len(set(_BUILTIN) | set(_CUSTOM)),
        "builtin": len(_BUILTIN),
        "custom": len(_CUSTOM),
        "file": STORE_FILE.name,
    }


# ─── 引用格式化 ────────────────────────────────────────────


def citation(rec: dict) -> str:
    """生成一行引用文本（用于展示和 `[[文献: id]]`）。"""
    if rec.get("_citation"):
        return rec["_citation"]
    authors = rec.get("author") or []
    author = "、".join(authors)
    title = rec.get("article_title") or rec.get("book_title") or ""
    venue = rec.get("journal") or (rec.get("book_title") if rec.get("article_title") else "")
    bits = []
    if author:
        bits.append(author)
    if title:
        bits.append(f"《{title}》")
    if venue:
        bits.append(f"《{venue}》")
    if rec.get("publisher"):
        bits.append(rec["publisher"])
    if rec.get("year"):
        bits.append(f"{rec['year']}年")
    if rec.get("pages"):
        bits.append(f"第{rec['pages']}页")
    return "，".join(bits)


def to_bibtex(rec: dict) -> str:
    """导出成 BibTeX 文本。"""
    t = rec.get("type") or "misc"
    lines = [f"@{t}{{{rec.get('id','')},"]
    for key, _name, kind, bib in FIELDS:
        if key in ("id", "type"):
            continue
        v = rec.get(key)
        if kind == "list":
            if not v:
                continue
            v = " and ".join(v)
        if not v:
            continue
        lines.append(f"  {bib:<16}= {{{v}}},")
    lines.append("}")
    return "\n".join(lines)
