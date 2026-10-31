"""
抽构表达式（abstract shape / IDS）的解析与校验

移植自 `src/ids.py`（原版依赖 anytree）。这里用轻量节点表示，
去掉第三方依赖，方便后端直接调用做**格式校验**。

抽构表达式的语法::

    <expr>   ::= <char> | <op> <expr> <expr> | <op> <expr> <expr> <expr>
    <char>   ::= 汉字 | 汉字(变体)

  * 部件写作 `[A]`，带变体的写作 `[A(B)]`（括号里是**同形异字**的说明）；
    输入时 `[ ]` 可以省略（`A` / `A(B)`），也可以只包住变体之外的写法
    （`[A](B)`）；整个表达式外再包一层 `[]`（`[⿱一丂]`）和全角 `（）` 也认，
    解析前先归一，`normalized` 一律输出「每个部件都带 `[]`」的形式；
  * 运算符是 IDC（表意文字描述符），见 `IDC.ARITY`；
  * `〾`(VA) 是一元运算符，表示近似形；
  * 开头可以写「分解头」`[與]=`，表示这句讲的是 **與** 的分解
    （`[與]=⿶[舁][牙]`）；头本身不是部件，不计入叶子数。

对外主要提供 `validate(expr)`，返回结构化结果（含错误位置），
供前端在「抽构」输入框里实时提示。
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

# ─── 运算符（IDC） ─────────────────────────────────────────


class IDC:
    """表意文字描述符（Ideographic Description Character）。

    名字沿用原 `src/ids.py` 的缩写，便于与既有数据对照。
    """

    LR = "⿰"  # 左右
    LL = "⿲"  # 左中右
    UD = "⿱"  # 上下
    UU = "⿳"  # 上中下
    RD = "⿸"  # 左上包围
    RU = "⿺"  # 左下包围
    LD = "⿹"  # 右上包围
    LU = "⿽"  # 右下包围
    OD = "⿵"  # 上三包围
    OR = "⿷"  # 左三包围
    OU = "⿶"  # 下三包围
    OL = "⿼"  # 右三包围
    OC = "⿴"  # 全包围
    XX = "⿻"  # 重叠
    MI = "⿾"  # 镜像
    RO = "⿿"  # 旋转
    VA = "〾"  # 近似形

    ARITY: dict[str, int] = {
        LR: 2, LL: 3, UD: 2, UU: 3, RD: 2, RU: 2, LD: 2, LU: 2,
        OD: 2, OR: 2, OU: 2, OL: 2, OC: 2, XX: 2, MI: 1, RO: 1, VA: 1,
    }

    ALL = frozenset(ARITY)

    #: 中文名，用于错误提示
    NAME = {
        LR: "左右", LL: "左中右", UD: "上下", UU: "上中下",
        RD: "左上包围", RU: "左下包围", LD: "右上包围", LU: "右下包围",
        OD: "上三包围", OR: "左三包围", OU: "下三包围", OL: "右三包围",
        OC: "全包围", XX: "重叠", MI: "镜像", RO: "旋转", VA: "近似形",
    }

    @classmethod
    def arity(cls, idc: str) -> int:
        try:
            return cls.ARITY[idc]
        except KeyError:
            raise ValueError(f"未知运算符「{idc}」") from None

    @classmethod
    def describe(cls, idc: str) -> str:
        name = cls.NAME.get(idc, "?")
        return f"{idc}（{name}，{cls.ARITY.get(idc, '?')} 元）"


#: 所有 IDC 字符
IDC_CHARS = IDC.ALL


# ─── 语法错误 ──────────────────────────────────────────────


class ShapeSyntaxError(ValueError):
    """抽构表达式语法错误，带出错位置。

    `code` 给上层分类用：`bad-char`（非法字符）/ `arity`（运算符目数不够）/
    `bracket`（括号不配对）/ `extra`（表达式后面还有内容）/ `empty` / `syntax`。
    """

    def __init__(self, message: str, pos: int, code: str = "syntax"):
        super().__init__(message)
        self.message = message
        self.pos = pos
        self.code = code

    def as_dict(self) -> dict:
        return {"message": self.message, "pos": self.pos, "code": self.code}


# ─── 节点 ──────────────────────────────────────────────────


@dataclass
class Char:
    """一个部件。`variant` 是括注，如 `一(二)` 里的 `二`。"""

    shape: str
    variant: str = ""
    note: str = ""

    def __repr__(self) -> str:
        return f"[{self.shape}{'(' + self.variant + ')' if self.variant else ''}]"

    def walk(self) -> list["Char"]:
        return [self]

    def depth(self) -> int:
        return 0

    def count(self) -> int:
        return 1


@dataclass
class IDS:
    """一个抽构表达式。`operator` 为 None 时表示单个部件。"""

    operator: str | None = None
    operands: list["IDS | Char"] = field(default_factory=list)
    note: str = ""

    def __repr__(self) -> str:
        if self.operator is None:
            return "".join(repr(c) for c in self.operands)
        return self.operator + "".join(repr(c) for c in self.operands)

    # ── 遍历 ──

    def children(self) -> list["IDS | Char"]:
        return list(self.operands)

    def walk(self) -> list["IDS | Char"]:
        """前序遍历自身与全部后代。"""
        out: list[IDS | Char] = [self]
        for c in self.operands:
            out.extend(c.walk())
        return out

    def chars(self) -> list[Char]:
        """所有叶子部件。"""
        return [n for n in self.walk() if isinstance(n, Char)]

    def depth(self) -> int:
        if not self.operands:
            return 0
        return 1 + max(c.depth() for c in self.operands)

    def count(self) -> int:
        """节点总数（含运算符），与原 `IDS.count()` 一致。"""
        return 1 + sum(c.count() for c in self.operands)

    # ── 统计 ──

    def operators_used(self) -> dict[str, int]:
        out: dict[str, int] = {}
        for n in self.walk():
            if isinstance(n, IDS) and n.operator:
                out[n.operator] = out.get(n.operator, 0) + 1
        return out

    def leaves_str(self) -> str:
        return "".join(c.shape for c in self.chars())


# ─── 解析 ──────────────────────────────────────────────────

#: 输入法常见的全角标点，先换成半角再解析
_FULLWIDTH_MAP = str.maketrans({
    "（": "(", "）": ")", "［": "[", "］": "]",
})


def _skip_ws(text: str, i: int) -> int:
    while i < len(text) and text[i].isspace():
        i += 1
    return i


#: 当部件用时明显不合法的字符：ASCII 标点/数字 + 常见全角标点。
#: 数据里 `〓`（占位）、`？`（存疑）、`⺀`（部首）这类是有意用法，不算非法。
_BAD_UNIT_CHARS = set(
    "!\"#$%&'*+,-./:;<=>@\\^_`{|}~"
    "0123456789"
    "，。、；：！（）［］｛｝【】《》〈〉「」『』“”‘’·…—～　"
)


def _parse_variant(text: str, i: int) -> tuple[str, int]:
    """解析部件的变体括注 `(变体)`；没有括号就返回 `("", i)`。"""
    j = _skip_ws(text, i)
    if j >= len(text) or text[j] != "(":
        return "", i
    open_pos = j
    j = _skip_ws(text, j + 1)
    if j >= len(text):
        raise ShapeSyntaxError("「(」之后表达式结束", open_pos, "bracket")
    v = text[j]
    if v in IDC_CHARS:
        raise ShapeSyntaxError(f"括注里不能是运算符「{v}」", j, "bad-char")
    if v in "()":
        raise ShapeSyntaxError(f"括注里不能是「{v}」", j, "bad-char")
    j = _skip_ws(text, j + 1)
    if j >= len(text) or text[j] != ")":
        raise ShapeSyntaxError("缺少配对的「)」", j, "bracket")
    return v, j + 1


def parse(expr: str) -> IDS:
    """解析抽构表达式，失败抛 `ShapeSyntaxError`。

    容错的写法都会先归一：全角 `（）`、部件外包 `[]`（`[乙(ᄅ)]`、`[乙](ᄅ)`）、
    整个表达式外包一层 `[]`（`[⿱九乙]`）。`normalized` 始终输出
    `⿱[九][乙]` 这种「每个部件都带 `[]`」的形式，再解析一遍结果不变。
    """
    text = (expr or "").strip().translate(_FULLWIDTH_MAP)
    if not text:
        raise ShapeSyntaxError("抽构为空", 0, "empty")
    try:
        return _parse_text(text)
    except ShapeSyntaxError:
        # 整体外包一层 `[]`：`[⿱一丂]`
        if len(text) > 2 and text[0] == "[" and text[-1] == "]":
            return _parse_text(text[1:-1].strip())
        raise


def _parse_text(text: str) -> IDS:
    def parse_at(i: int) -> tuple[IDS | Char, int]:
        # 跳过空白
        while i < len(text) and text[i].isspace():
            i += 1
        if i >= len(text):
            raise ShapeSyntaxError("表达式意外结束", i, "arity")

        c = text[i]

        if c in IDC_CHARS:
            arity = IDC.arity(c)
            i += 1
            operands: list[IDS | Char] = []
            for _ in range(arity):
                while i < len(text) and text[i].isspace():
                    i += 1
                if i >= len(text):
                    raise ShapeSyntaxError(
                        f"「{c}」（{IDC.NAME[c]}）需要 {arity} 个部件，"
                        f"只给了 {len(operands)} 个",
                        i,
                        "arity",
                    )
                node, i = parse_at(i)
                operands.append(node)
            return IDS(c, operands), i

        if c in "()":
            raise ShapeSyntaxError(f"意料之外的「{c}」", i, "bad-char")

        # 部件：`九` / `[九]` / `乙(ᄅ)` / `[乙(ᄅ)]` / `[乙](ᄅ)`
        bracketed = False
        if c == "[":
            bracketed = True
            i = _skip_ws(text, i + 1)
            if i >= len(text):
                raise ShapeSyntaxError("「[」之后表达式结束", i, "bracket")
            c = text[i]
            if c in IDC_CHARS:
                raise ShapeSyntaxError(f"「[」里应该是部件，不是运算符「{c}」", i, "bad-char")
            if c in "[]()":
                raise ShapeSyntaxError(f"「[」里不能是「{c}」", i, "bad-char")

        if c in _BAD_UNIT_CHARS:
            raise ShapeSyntaxError(f"非法字符「{c}」", i, "bad-char")

        i += 1
        variant, i = _parse_variant(text, i)
        if bracketed:
            i = _skip_ws(text, i)
            if i >= len(text) or text[i] != "]":
                raise ShapeSyntaxError("缺少配对的「]」", i, "bracket")
            i += 1
            if not variant:
                # 变体也允许写在括号外：`[乙](ᄅ)`
                variant, i = _parse_variant(text, i)
        return Char(c, variant), i

    node, pos = parse_at(0)
    while pos < len(text) and text[pos].isspace():
        pos += 1
    if pos < len(text):
        extra = text[pos:]
        raise ShapeSyntaxError(f"表达式在「{extra[0]}」处有多余内容", pos, "extra")
    if isinstance(node, Char):
        # 单个部件也是合法抽构
        return IDS(None, [node])
    return node


def try_parse(expr: str) -> IDS | None:
    """解析失败返回 None（不抛异常）。"""
    try:
        return parse(expr)
    except ShapeSyntaxError:
        return None


# ─── 校验 ──────────────────────────────────────────────────

#: 允许的表达式前缀：`=下`（同字/异体）、`~下`（参考）、`*下`（参考抽构）、`?下`（存疑）
PREFIX_CHARS = "=~*?"


def split_prefix(expr: str) -> tuple[str, str]:
    """拆出前缀：`=下` → `("=", "下")`；没有前缀返回 `("", expr)`。"""
    s = (expr or "").strip().translate(_FULLWIDTH_MAP)
    if s and s[0] in PREFIX_CHARS:
        return s[0], s[1:].strip()
    return "", s


#: 分解头：`=` 左边那个部件，可写成 `[與]` / `與` / `[與(与)]`
_HEAD_RE = re.compile(r"^(\[[^\[\]]+\]|[^\s\[\]=()⿰-⿿〾])\s*=\s*(.*)$", re.S)


def split_head(expr: str) -> tuple[str, "Char | None", str]:
    """拆出前缀与分解头：`[與]=⿶[舁][牙]` → `("", Char("與"), "⿶[舁][牙]")`。

    没有 `部件=` 开头的就返回 `(prefix, None, 去掉前缀后的表达式)`。
    """
    s = (expr or "").strip().translate(_FULLWIDTH_MAP)
    prefix = ""
    rest = s
    if rest and rest[0] in PREFIX_CHARS:
        prefix, rest = rest[0], rest[1:].strip()
    m = _HEAD_RE.match(rest)
    if not m:
        return prefix, None, rest
    try:
        node = _parse_text(m.group(1).strip())
    except ShapeSyntaxError:
        return prefix, None, rest
    if node.operator is None and len(node.operands) == 1:
        return prefix, node.operands[0], m.group(2).strip()
    return prefix, None, rest


def validate(expr: str, *, idc_only: bool = False) -> dict:
    """校验抽构表达式，返回结构化结果。

    参数:
      expr      要校验的表达式（可带 `= ~ * ?` 前缀）
      idc_only  只接受含运算符的表达式（纯单字不算「抽构」）

    返回::

        {
          "ok": bool,
          "error": {"message": str, "pos": int, "code": str} | None,
          "normalized": str,          # 规范化后的表达式（部件加 []，前缀/分解头保留）
          "prefix": str,              # `= ~ * ?` 里的一个，没有则为空
          "head": str,                # 分解头 `[與]`，没有则为空
          "leaves": str,              # 叶子部件串
          "leaf_count": int,
          "depth": int,
          "operators": {op: count},
          "warnings": [str],
        }
    """
    text = (expr or "").strip()
    prefix, head, body = split_head(text)
    head_repr = repr(head) if head else ""
    if not body:
        # `[與]=` 这种有头没内容的不算空表达式
        if head:
            return {
                "ok": False,
                "error": {"message": "「=」之后没有抽构", "pos": len(text), "code": "empty"},
                "normalized": "", "prefix": prefix, "head": head_repr,
                "leaves": "", "leaf_count": 0, "depth": 0, "operators": {},
                "warnings": [],
            }
        return {
            "ok": True, "error": None, "normalized": "", "prefix": prefix, "head": "",
            "leaves": "", "leaf_count": 0, "depth": 0, "operators": {},
            "warnings": [], "empty": True,
        }

    try:
        node = parse(body)
    except ShapeSyntaxError as e:
        err = e.as_dict()
        # 前缀 / 分解头各占若干字符，位置补回原文
        try:
            err["pos"] += text.rindex(body)
        except ValueError:
            err["pos"] += len(prefix) + (len(head_repr) + 1 if head else 0)
        return {
            "ok": False, "error": err, "normalized": "", "prefix": prefix,
            "head": head_repr, "leaves": "", "leaf_count": 0, "depth": 0,
            "operators": {}, "warnings": [],
        }

    warnings: list[str] = []
    chars = node.chars()
    leaves = "".join(c.shape for c in chars)

    if idc_only and node.operator is None:
        warnings.append("这是单个部件，不是含运算符的抽构")

    if not chars:
        warnings.append("抽构里没有任何部件")

    # 单件运算符没意义
    for n in node.walk():
        if isinstance(n, IDS) and n.operator and len(n.operands) < 2:
            warnings.append(
                f"「{n.operator}」是 {IDC.NAME[n.operator]}，只带一个部件（可以省略）"
            )

    # 同一个部件在顶层重复出现，多半是笔误
    if len(chars) > 1:
        shapes = [c.shape for c in chars]
        dupes = {s for s in shapes if shapes.count(s) > 1}
        if dupes and node.operator not in (IDC.LL, IDC.UU):
            warnings.append(
                "重复部件 " + "、".join(sorted(dupes)) + "，确认是否应该用 ⿰/⿱ 之外的运算符"
            )

    return {
        "ok": True,
        "error": None,
        "normalized": prefix + (head_repr + "=" if head else "") + repr(node),
        "prefix": prefix,
        "head": head_repr,
        "leaves": leaves,
        "leaf_count": len(chars),
        "depth": node.depth(),
        "operators": node.operators_used(),
        "warnings": warnings,
    }


def normalize(expr: str) -> str:
    """把表达式规范化为 `[A]` 形式（解析失败则原样返回）。"""
    prefix, head, body = split_head(expr)
    node = try_parse(body) if body else None
    if node is None:
        return (expr or "")
    return prefix + (repr(head) + "=" if head else "") + repr(node)
