# -*- coding: utf-8 -*-
"""Scan a JSONL-ish snippet of abstract-shape data and report which
`[...]` components are NOT present in input/xiangxing.txt, and which
IDC operators occur.

Usage: python tools/scan_components.py <data.txt>
"""

from __future__ import annotations

import io
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
XY = os.path.join(ROOT, "input", "xiangxing.txt")

# ---------------------------------------------------------------- IDC ----
# Unicode IDC -> Latin abbreviation (project + community naming)
IDC_LATIN = {
    "⿰": "LTR",   # left to right            2
    "⿱": "UTB",   # up to bottom             2
    "⿲": "LTR3",  # left to right, 3         3
    "⿳": "UTB3",  # up to bottom, 3          3
    "⿴": "SUR",   # surround                 2
    "⿵": "SUR-UD",  # surround from above
    "⿶": "SUR-BU",  # surround from below
    "⿷": "SUR-LT",  # surround from left
    "⿸": "SUR-UL",  # surround from upper left
    "⿹": "SUR-UR",  # surround from upper right
    "⿺": "SUR-LL",  # surround from lower left
    "⿻": "OVL",   # overlay
    "⿼": "SUR-LB",
    "⿽": "SUR-LU",
    "⿾": "MIRROR",
    "⿿": "ROTATE",
    "〾": "SIMILAR",
    "↔": "REF",
    "=": "EQ",
    "⿸": "SUR-UL",
}


def read_xiangxing() -> dict[str, str]:
    """component -> new code (A1/B2/...)"""
    sys.path.insert(0, os.path.join(ROOT, "src"))
    import build_xiangxing as bx  # noqa: PLC0415

    counters: dict[str, int] = {}
    index: dict[str, str] = {}
    with io.open(XY, encoding="utf-8") as f:
        for line in f:
            line = line.rstrip("\n")
            if not line.strip():
                continue
            parts = line.split("\t")
            char = parts[0]
            code = int(parts[1]) if len(parts) > 1 and parts[1].strip().isdigit() else 999999
            family = bx.classify(char, code)
            counters[family] = counters.get(family, 0) + 1
            index[char] = "%s%d" % (family, counters[family])
    return index


def main() -> None:
    path = sys.argv[1]
    with io.open(path, encoding="utf-8") as f:
        raw = f.read()

    # tolerant parse: strip the "---" separator block
    raw = raw.split("---")[0]
    body = "[" + raw.strip().rstrip(",") + "]"
    rows = json.loads(body)

    index = read_xiangxing()
    seen: dict[str, int] = {}
    missing: dict[str, int] = {}
    idc: dict[str, int] = {}
    refs: dict[str, int] = {}

    for row in rows:
        blob = json.dumps(row, ensure_ascii=False)
        for c in re.findall(r"\[([^\]]*)\]", blob):
            seen[c] = seen.get(c, 0) + 1
            if c not in index:
                missing[c] = missing.get(c, 0) + 1
        for c in re.findall(r"[⿰-⿿〾↔=]", blob):
            idc[c] = idc.get(c, 0) + 1
        for c in re.findall(r"「([^」]*)」", blob):
            refs[c] = refs.get(c, 0) + 1

    print("rows        : %d" % len(rows))
    print("bracket refs: %d distinct" % len(seen))
    print()
    print("== IDC used ==")
    for c, n in sorted(idc.items()):
        print("  %s  %-7s %d" % (c, IDC_LATIN.get(c, "?"), n))
    print()
    print("== refs 「...」 ==")
    for c, n in sorted(refs.items()):
        status = "in-table" if c in index else "MISSING"
        print("  %-4s x%d  %s" % (c, n, status))
    print()
    print("== bracket components MISSING from xiangxing.txt (%d) ==" % len(missing))
    for c, n in sorted(missing.items()):
        print("  %-4s x%d" % (c, n))
    print()
    print("== all bracket components in table ==")
    for c, n in sorted(seen.items()):
        print("  %-8s %-6s x%d" % (c, index.get(c, "MISSING"), n))


if __name__ == "__main__":
    main()
