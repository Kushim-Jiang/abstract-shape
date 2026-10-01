"""
CJK 汉字区段（Unicode block）定义

前端左侧列表按「基本 → 兼容 → 部首 → 扩展A → 扩展B → …」排列，
顺序与命名都从这里出，后端 `/api/blocks` 直接吐给前端，
避免两边各写一份导致不一致。
"""

from __future__ import annotations

#: (key, 中文名, 起, 止) —— 列表顺序即显示顺序
BLOCKS: list[tuple[str, str, int, int]] = [
    ("uro",   "基本",   0x4E00, 0x9FFF),
    ("comp",  "兼容",   0xF900, 0xFAFF),
    ("rad",   "部首",   0x2E80, 0x2FDF),
    ("exta",  "扩展A",  0x3400, 0x4DBF),
    ("extb",  "扩展B",  0x20000, 0x2A6DF),
    ("comps", "兼容扩展", 0x2F800, 0x2FA1F),
    ("extc",  "扩展C",  0x2A700, 0x2B73F),
    ("extd",  "扩展D",  0x2B740, 0x2B81F),
    ("exte",  "扩展E",  0x2B820, 0x2CEAF),
    ("extf",  "扩展F",  0x2CEB0, 0x2EBEF),
    ("extg",  "扩展G",  0x30000, 0x3134F),
    ("exth",  "扩展H",  0x31350, 0x323AF),
    ("exti",  "扩展I",  0x2EBF0, 0x2EE5F),
    ("extj",  "扩展J",  0x323B0, 0x3347F),
    ("other", "其他",   0x0000, 0x10FFFF),
]

#: key -> (中文名, order)
_BY_KEY = {k: (name, i) for i, (k, name, _, _) in enumerate(BLOCKS)}


def classify(codepoint: int) -> str:
    """返回码位所属区段 key。"""
    for key, _name, lo, hi in BLOCKS:
        if lo <= codepoint <= hi:
            return key
    return "other"


def sort_key(codepoint: int) -> tuple[int, int]:
    """排序键：先按区段顺序，再按码位。"""
    key = classify(codepoint)
    order = _BY_KEY.get(key, (None, len(BLOCKS)))[1]
    return (order, codepoint)


def name_of(key: str) -> str:
    return _BY_KEY.get(key, ("其他", len(BLOCKS)))[0]


def as_list() -> list[dict]:
    """给前端的区段清单。"""
    return [
        {"key": k, "name": n, "start": lo, "end": hi}
        for k, n, lo, hi in BLOCKS
    ]
