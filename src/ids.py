from __future__ import annotations
from anytree import NodeMixin

IDC_ = str


class IDC:
    LR = "⿰"
    LL = "⿲"
    UD = "⿱"
    UU = "⿳"
    RD = "⿸"
    RU = "⿺"
    LD = "⿹"
    LU = "⿽"
    OD = "⿵"
    OR = "⿷"
    OU = "⿶"
    OL = "⿼"
    OC = "⿴"
    XX = "⿻"
    MI = "⿾"
    RO = "⿿"
    ALL = {LR, LL, UD, UU, RD, RU, LD, LU, OD, OR, OU, OL, OC, XX, MI, RO}

    @classmethod
    def arity(cls, idc: IDC_) -> int:
        if idc in (cls.LR, cls.UD, cls.RD, cls.RU, cls.LD, cls.LU, cls.OD, cls.OR, cls.OU, cls.OL, cls.OC):
            return 2
        elif idc in (cls.LL, cls.UU):
            return 3
        elif idc in (cls.XX, cls.MI, cls.RO):
            return 1
        else:
            raise ValueError(f"Unknown IDC: {idc}")


class Char(NodeMixin):
    def __init__(self, shape: str, note: str = ""):
        self.shape = shape
        self.note = note
        self.parent = None

    def __repr__(self) -> str:
        return f"[{self.shape}]"


class IDS(NodeMixin):
    def __init__(self, *args, note: str = ""):
        self.note = note
        self.parent = None

        if len(args) == 1 and isinstance(args[0], str):
            parsed = IDS.from_str(args[0])
            self.operator = parsed.operator
            self.char = parsed.char
            self.note = ""
            for child in parsed.children:
                child.parent = self
        elif len(args) == 1 and isinstance(args[0], (Char, IDS)):
            self.operator = None
            self.char = args[0]
        elif len(args) >= 2 and isinstance(args[0], IDC_):
            self.operator = args[0]
            operands = args[1:]
            if len(operands) != IDC.arity(self.operator):
                raise ValueError(f"{self.operator} requires {IDC.arity(self.operator)} operands, got {len(operands)}")
            for op in operands:
                if not isinstance(op, (Char, IDS)):
                    raise TypeError("Operands must be Char or IDS")
                op.parent = self
            self.char = None
        else:
            raise ValueError("Invalid IDS initialization")

    @staticmethod
    def from_str(ids: str) -> IDS:
        if not ids:
            return None

        def parse(index: int):
            while index < len(ids) and ids[index].isspace():
                index += 1
            if index >= len(ids):
                raise ValueError("Unexpected end of string")
            if ids[index] in IDC.ALL:
                operator = ids[index]
                index += 1
                operands = []
                for _ in range(IDC.arity(operator)):
                    while index < len(ids) and ids[index].isspace():
                        index += 1
                    node, index = parse(index)
                    operands.append(node)
                node = IDS(operator, *operands)
                return node, index
            else:
                c = ids[index]
                if c in IDC.ALL or c in "()":
                    raise ValueError(f"Unexpected character: {c}")
                index += 1
                if index < len(ids) and ids[index] == "(":
                    index += 1
                    if index >= len(ids):
                        raise ValueError("Unexpected end of string after '('")
                    c2 = ids[index]
                    if c2 in IDC.ALL or c2 in "()":
                        raise ValueError(f"Unexpected character in parentheses: {c2}")
                    index += 1
                    if index >= len(ids) or ids[index] != ")":
                        raise ValueError("Expected ')'")
                    index += 1
                    node = Char(f"{c}({c2})")
                    return IDS(node), index
                else:
                    node = Char(c)
                    return IDS(node), index

        node, index = parse(0)
        return node

    def __repr__(self) -> str:
        def prefix(node):
            if isinstance(node, Char):
                return repr(node)
            elif isinstance(node, IDS):
                if node.operator is None:
                    return prefix(node.char)
                else:
                    return str(node.operator) + "".join(prefix(child) for child in node.children)

        return prefix(self)

    def chars(self) -> list[Char]:
        chars = []
        for child in self.children:
            if isinstance(child, Char):
                chars.append(child)
            elif isinstance(child, IDS):
                chars.extend(child.chars())
        return chars

    def count(self) -> int:
        def count_children(node):
            if isinstance(node, Char):
                return 1
            elif isinstance(node, IDS):
                return sum(count_children(child) for child in node.children) + 1
            else:
                raise TypeError("Node must be Char or IDS")

        return count_children(self)
