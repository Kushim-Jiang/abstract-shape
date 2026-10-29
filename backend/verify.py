"""
核验：抽构 / 参考抽构 / 引用的自洽检查

检查项（`code`）：

  * `bad-char`      表达式里有非法字符（只允许 IDC、汉字、`[ ] ( )` 与 `= ~ * ?` 前缀）
  * `arity`         运算符的目数和部件数对不上
  * `bracket`       括号不配对 / 表达式没写完
  * `extra`         表达式后面还有多余内容
  * `missing-unit`  抽构里用到的部件，没有任何一条记录的抽构等于它（**警告**）
  * `dup-unit`      同一条抽构（`[下]`、`⿰[虫][下]` …）有两条以上记录把它当自己的抽构
                    （其余应写成 `=[下]` / `=⿰[虫][下]`）
  * `no-ref`        引用了不存在的文献编号
  * `page-range`    引用的页码超出文献登记的页码范围

`missing-unit` 只算警告：部件迟早要单独建条，可以以后补。
引用键（文献 id）重复是全局问题，见 `refs.duplicates()`，不进单字结果。
`by_block` 的键与 `backend/blocks.py` 的区段 key 一致（`uro` / `exta` …）。
"""

from __future__ import annotations

import re

from . import blocks, entrystore, refs, shape

#: 字段 → 中文名（前端展示用）
FIELD_NAMES = {"con": "抽构", "ref_con": "参考抽构", "notes": "札记"}

_PAGE_SPLIT_RE = re.compile(r"[+＋]")
_NUM_RE = re.compile(r"\d+")

#: `unit_index()` / `unit_defs()` 的缓存（按 entrystore 的数据版本失效）
_INDEX_CACHE: dict = {"token": None, "defs": None, "units": None}


def _issue(level: str, code: str, field: str, message: str, seq: int) -> dict:
    return {
        "level": level,
        "code": code,
        "field": field,
        "field_name": FIELD_NAMES.get(field, field),
        "message": message,
        "seq": seq,
    }


def _parse_expr(expr: str):
    """拆前缀后解析，返回 (prefix, body, node|None)。"""
    prefix, body = shape.split_prefix(expr)
    node = shape.try_parse(body) if body else None
    return prefix, body, node


def _build_indexes() -> tuple[dict[str, list[tuple[str, int]]], set[str]]:
    """一次扫完全部条，得到 (定义者表, 存在的部件集合)。

    `defs` 的键是**不带前缀的整条抽构**的规范写法（`[下]`、`⿰[虫][下]`）。
    带 `= ~ * ?` 前缀的是异体 / 参考写法，不算定义者，可以重复。
    """
    token = entrystore.data_token()
    if _INDEX_CACHE["token"] == token and _INDEX_CACHE["defs"] is not None:
        return _INDEX_CACHE["defs"], _INDEX_CACHE["units"]

    defs: dict[str, list[tuple[str, int]]] = {}
    units: set[str] = set()

    for e in entrystore.all_entries():
        prefix, _body, node = _parse_expr(e["con"] or "")
        if prefix or node is None:
            continue
        key = repr(node)
        defs.setdefault(key, []).append((e["char"], e["seq"]))
        if node.operator is None:
            chars = node.chars()
            if len(chars) == 1:
                units.add(repr(chars[0]))
                units.add("[" + chars[0].shape + "]")

    _INDEX_CACHE["token"] = token
    _INDEX_CACHE["defs"] = defs
    _INDEX_CACHE["units"] = units
    return defs, units


def unit_index() -> set[str]:
    """所有「单部件」条目给出的部件集合：`[下]`、`[乙(ᄅ)]`（同时收 `[乙]`）。"""
    return _build_indexes()[1]


def unit_defs() -> dict[str, list[tuple[str, int]]]:
    """谁定义了某条抽构：`{"[下]": [(下, 1)], "⿰[虫][下]": [(虾, 1)]}`。"""
    return _build_indexes()[0]


def check_unique_unit(entry: dict, defs: dict[str, list[tuple[str, int]]]) -> list[dict]:
    """同一条抽构只能有一个定义者（`[下]`、`⿰[虫][下]` 都一样），其余应写成 `=…`。"""
    prefix, _body, node = _parse_expr(entry["con"] or "")
    if prefix or node is None:
        return []
    key = repr(node)
    owners = defs.get(key) or []
    me = (entry["char"], entry["seq"])
    if len(owners) < 2:
        return []
    others = [f"{ch}-{seq}" for ch, seq in owners if (ch, seq) != me]
    return [_issue(
        "error", "dup-unit", "con",
        f"{key} 已经有 {', '.join(others)} 这条定义了，这里应写作 ={key}", entry["seq"])]


def check_expression(expr: str, field: str, existing: set[str], seq: int) -> list[dict]:
    """抽构 / 参考抽构：格式 + 部件是否单独有记录。"""
    out: list[dict] = []
    expr = (expr or "").strip()
    if not expr:
        return out

    res = shape.validate(expr)
    if not res["ok"]:
        err = res.get("error") or {}
        msg = err.get("message") or "格式错误"
        pos = err.get("pos")
        if isinstance(pos, int):
            msg = f"{msg}（第 {pos + 1} 字符）"
        out.append(_issue("error", err.get("code") or "syntax", field, msg, seq))
        return out

    _prefix, _body, node = _parse_expr(expr)
    if node is None:
        return out

    seen: set[str] = set()
    for ch in node.chars():
        unit = repr(ch)
        base = "[" + ch.shape + "]"
        if unit in existing or base in existing or unit in seen:
            continue
        seen.add(unit)
        out.append(
            _issue("warn", "missing-unit", field,
                   f"部件 {unit} 还没有单独记录（需要一条抽构 = {base} 的记录）", seq)
        )
    return out


def _cited_spans(spec: str) -> list[tuple[int, int]]:
    """`244-245+248` → [(244, 245), (248, 248)]；登记页码和引用页码都用它解析。"""
    out: list[tuple[int, int]] = []
    for part in _PAGE_SPLIT_RE.split(spec or ""):
        nums = [int(n) for n in _NUM_RE.findall(part)]
        if nums:
            out.append((min(nums), max(nums)))
    return out


def _covered(n: int, spans: list[tuple[int, int]]) -> bool:
    """页码 n 是否落在登记的某一段里。"""
    return any(lo <= n <= hi for lo, hi in spans)


def check_refs(items: list[dict], seq: int) -> list[dict]:
    """引用的文献是否存在、页码是否在登记范围内。"""
    out: list[dict] = []
    for r in items:
        rid = (r.get("id") or "").strip()
        if not rid:
            continue
        rec = refs.get(rid)
        if not rec:
            out.append(_issue("error", "no-ref", "notes", f"引用了不存在的文献 {rid}", seq))
            continue
        registered = _cited_spans(rec.get("pages") or "")
        if not registered:
            continue                     # 没登记页码（或不是数字），没法比对
        pages = (r.get("pages") or "").strip()
        for a, b in _cited_spans(pages):
            if not (_covered(a, registered) and _covered(b, registered)):
                out.append(_issue(
                    "error", "page-range", "notes",
                    f"{rid} 引用了第 {pages} 页，超出登记的页码 "
                    f"{refs.format_pages(rec.get('pages'))}", seq))
                break
    return out


def _counts(issues: list[dict]) -> dict:
    return {
        "count": len(issues),
        "error_count": sum(1 for i in issues if i["level"] == "error"),
        "warn_count": sum(1 for i in issues if i["level"] == "warn"),
    }


def check_char(char: str) -> dict:
    """一个字的全部条：逐条核验，返回问题列表。"""
    existing = unit_index()
    defs = unit_defs()
    issues: list[dict] = []
    for e in entrystore.entries_of(char):
        seq = e["seq"]
        issues += check_expression(e["con"], "con", existing, seq)
        issues += check_unique_unit(e, defs)
        issues += check_expression(e["ref_con"], "ref_con", existing, seq)
        issues += check_refs(e["refs"], seq)
    return {"char": char, "issues": issues, **_counts(issues)}


# ─── 全局汇总（左栏区段计数用） ────────────────────────────

_CACHE: dict = {"token": None, "value": None}


def summary(codepoint_of=None) -> dict:
    """全库核验计数：`{total, by_block, by_char, ref_dups, ref_dup_count}`。

    `codepoint_of(char) -> int` 用来判断区段；不传就都算「其他」。
    逐条检查的结果按 `entrystore.data_token()` 缓存，数据变了自动重算；
    引用键重复是全局问题，每次现算（只在文献库加载时扫一遍，很便宜）。
    """
    token = entrystore.data_token()
    if _CACHE["token"] == token and _CACHE["value"] is not None:
        return _with_ref_dups(dict(_CACHE["value"]))

    existing = unit_index()
    defs = unit_defs()
    by_char: dict[str, int] = {}
    by_block: dict[str, int] = {}
    total = 0

    for e in entrystore.all_entries():
        char = e["char"]
        seq = e["seq"]
        issues = check_expression(e["con"], "con", existing, seq)
        issues += check_unique_unit(e, defs)
        issues += check_expression(e["ref_con"], "ref_con", existing, seq)
        issues += check_refs(e["refs"], seq)
        if not issues:
            continue
        n = len(issues)
        total += n
        by_char[char] = by_char.get(char, 0) + n
        cp = 0
        if codepoint_of is not None:
            try:
                cp = int(codepoint_of(char) or 0)
            except (TypeError, ValueError):
                cp = 0
        key = blocks.classify(cp)
        by_block[key] = by_block.get(key, 0) + n

    value = {"total": total, "by_block": by_block, "by_char": by_char}
    _CACHE["token"] = token
    _CACHE["value"] = value
    return _with_ref_dups(dict(value))


def _with_ref_dups(value: dict) -> dict:
    """把引用键重复（全局问题）挂到汇总结果上。"""
    value["ref_dups"] = refs.duplicates()
    value["ref_dup_count"] = len(value["ref_dups"])
    return value
