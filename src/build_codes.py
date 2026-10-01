# -*- coding: utf-8 -*-
"""Convert abstract-shape component data into the compact code form.

Output line shape (tab separated, exactly four fields incl. the literal "#"):

    U+4EBA	I1	# [人]

            char      IDC        note (optional)
      U+4EBA  I1  # [人]

Rules
-----
* `char`/`is`/`to`/`new_ids` targets  ->  `U+XXXX` (upper-case, zero padded to 4
  digits, 5 or 6 for the supplementary planes).
* IDC operators                       ->  Latin abbreviations (LTR, UTB, UTB3,
  SUR, ... see IDC_LATIN).
* `[...]` component references        ->  the family code from the natural
  classification (A1, B2, ...), see xiangxing_taxonomy.md.
* every `X` inside `[...]`            ->  `*X`'s form-position code, e.g. `*X01`.
* `{...}` (phonetic-value braces)     ->  `{...}` kept as braces, contents left
  alone (they are words, not glyphs).
* `「...」` references                 ->  `U+XXXX (CODE)`.
* `to`                                ->  appended to the note as `c.f. ...`.
* `is`                                ->  emitted as an extra `= ...` field in
  the IDC column, so `亻` renders as `= I1`.

Usage
-----
    python src/build_codes.py <input.jsonl> [-o out.txt]
"""

from __future__ import annotations

import io
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GROUP_HEADER = "# group: 象物 / 象人 / 象工 / 记号 / 衍生; family: A..Z"

# --------------------------------------------------------------- IDC -----
IDC_LATIN = {
    "⿰": "LTR",
    "⿱": "UTB",
    "⿲": "LTR3",
    "⿳": "UTB3",
    "⿴": "SUR",
    "⿵": "SUR-UD",
    "⿶": "SUR-BU",
    "⿷": "SUR-LT",
    "⿸": "SUR-UL",
    "⿹": "SUR-UR",
    "⿺": "SUR-LL",
    "⿻": "OVL",
    "⿼": "SUR-LB",
    "⿽": "SUR-LU",
    "⿾": "MIRROR",
    "⿿": "ROTATE",
    "〾": "SIMILAR",
    "↔": "REF",
}
IDC_RE = re.compile("[" + "".join(IDC_LATIN) + "]")

# ------------------------------------------------------------ helpers ----
FALLBACK_COMPONENT: dict[str, str] = {}  # filled at runtime, see extras below


def uplus(char: str) -> str:
    """`人` -> `U+4EBA`; keeps the first char only, ignores combining marks."""
    return "U+" + format(ord(char), "04X")


def uplus_run(text: str) -> str:
    """`兩個字` -> `U+XXXX U+XXXX`."""
    return " ".join(uplus(c) for c in text)


def load_index() -> dict[str, str]:
    """component -> classification code (A1/B2/...) from input/xiangxing.txt."""
    sys.path.insert(0, os.path.join(ROOT, "src"))
    import build_xiangxing as bx  # noqa: PLC0415

    counters: dict[str, int] = {}
    index: dict[str, str] = {}
    with io.open(os.path.join(ROOT, "input", "xiangxing.txt"), encoding="utf-8") as f:
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


# -------------------------------------------------------------------------
# components that appear in the corpus but are NOT among the 435 in
# input/xiangxing.txt.  They are assigned by semantic judgement:
# decomposable ones go to Y, the rest to the nearest family.
# Replace these with the real numbers once xiangxing.txt is extended.
# -------------------------------------------------------------------------
EXTRA_COMPONENT = {
    # Y = 合体式与整体象形 (decomposable / already a composed shape)
    "今": ("Y11", "decomposable: ⿱[亼][𠃌]"),
    "介": ("Y12", "decomposable: ⿱[人][八]"),
    # U = 数字与序数 (U2 is 一, so 二 is the third numeral in this sequence)
    "二": ("U16", "numeral, continues the U block"),
}


def component_code(c: str, index: dict[str, str], extras: dict[str, str]) -> str:
    if c.startswith("*"):
        name = c[1:]
        return "*X%02d" % (ord(name[0]) if name else 0x2A)
    if c in index:
        return index[c]
    if c in EXTRA_COMPONENT:
        code, why = EXTRA_COMPONENT[c]
        extras[c] = "%s  (%s)" % (code, why)
        return code
    extras[c] = "U?  (undecomposable, needs a family)"
    return "U?"


# ------------------------------------------------------------ compile ----
def compile_ids(ids: str, index: dict[str, str], extras: dict[str, str]) -> str:
    """`⿰[人][乙]` -> `LTR I1 U10`."""
    out: list[str] = []
    i = 0
    while i < len(ids):
        ch = ids[i]
        if ch in IDC_LATIN:
            out.append(IDC_LATIN[ch])
            i += 1
        elif ch == "[":
            j = ids.index("]", i)
            out.append(component_code(ids[i + 1 : j], index, extras))
            i = j + 1
        elif ch.isspace():
            i += 1
        else:
            # bare glyphs are not expected inside `ids`, keep the codepoint
            out.append(uplus(ch))
            i += 1
    return " ".join(out)


# ------------------------------------------------------------- note ------
# Ordered rules, applied on the *Chinese* text.  Rules run before the generic
# phrase table, so that verb-object orders come out right; each rule replaces
# its match with a placeholder that later stages leave alone.
CITATION_RE = re.compile("《([^》]*)》")
QUOTE_RE = re.compile("「([^」]*)」")
BRACE_RE = re.compile("｛([^｝]*)｝")
PLACEHOLDER = "\x00%d\x00"

NOTE_RULES = [
    # (regex over the Chinese text, English template, group count)
    #   {Q1}/{Q2}/{Q} slots are filled by resolve(); {T} stays verbatim
    (r"声符由「([^」]*)」改换为「([^」]*)」",
     "the phonetic changed from {Q1} to {Q2}", 2),
    (r"以「([^」]*)」代替「([^」]*)」",
     "{Q1} replaces {Q2}", 2),
    (r"《([^》]*)》构件", "a {T} component", 1),
    (r"从「([^」]*)」上析出", "split off from the top of {Q}", 1),
]

# phrase table, longest source first
NOTE_PHRASES = [
    ("商周金文", "Shang-Zhou bronze inscriptions "),
    ("后人附会", "later folk-etymologised as "),
    ("口诀字", "mnemonic glyph for "),
    ("偏旁构件", "component used as a side form"),
    ("左声符", "left-hand phonetic"),
    ("右声符", "right-hand phonetic"),
    ("下声符", "bottom phonetic"),
    ("隶定", "clericalisation"),
    ("见于", "seen in "),
    ("用作", "used as "),
    ("所改", "modified by "),
    ("上析出", "split off from the top of "),
    ("析出", "split off from "),
    ("声符", "phonetic"),
    ("代替", "replacing"),
    ("改换为", "replaced by "),
    ("构件", "component"),
    ("从", "derived from "),
    ("见", "see "),
    ("以", "by "),
    ("爲", "as "),
    ("为", "as "),
    ("改", "changed"),
    ("来", ""),
    ("乃", ""),
]


def _protect(text: str, store: list[str]) -> str:
    """Replace 《》 titles with placeholders so later rules cannot see them."""
    def sub(m: re.Match) -> str:
        store.append(m.group(1))
        return PLACEHOLDER % (len(store) - 1)

    return CITATION_RE.sub(sub, text)


def _restore(text: str, store: list[str], index: dict[str, str], extras: dict[str, str]) -> str:
    def sub(m: re.Match) -> str:
        return store[int(m.group(1))]

    return re.sub(r"\x00(\d+)\x00", sub, text)


def resolve(text: str, index: dict[str, str], extras: dict[str, str]) -> str:
    """Turn glyph references in a fragment into `U+XXXX (CODE)`.

    Called on every fragment produced by a NOTE_RULES replacement, so that a
    rule never has to know about codepoints.  Long runs (sentences) are left
    alone because they are not glyph references.
    """
    if "。" in text or "，" in text or len(text) > 6:
        return text
    parts = []
    for c in text:
        if c in index:
            parts.append("%s (%s)" % (uplus(c), index[c]))
        else:
            parts.append(uplus(c))
    return " ".join(parts)


def translate_ref(inner: str, index: dict[str, str] | None = None) -> str:
    """`合` -> `U+5408 (Y..)`; quoted citations are returned as-is."""
    if not inner:
        return inner
    if index is None:
        return " ".join(uplus(c) for c in inner)
    return resolve(inner, index, {})


def translate_note_full(note: str, index: dict[str, str], extras: dict[str, str]) -> str:
    titles: list[str] = []
    note = _protect(note, titles)

    # rule-based sentences first: each rule returns a finished English sentence
    # whose glyph slots are marked with {} so that resolve() can fill them in.
    for pattern, template, ngroups in NOTE_RULES:
        def repl(m: re.Match, template: str = template, ngroups: int = ngroups) -> str:
            groups = [m.group(i) for i in range(1, ngroups + 1)]
            slots = {
                "Q1": resolve(groups[0], index, extras),
                "Q2": resolve(groups[1], index, extras) if ngroups > 1 else "",
                "Q": resolve(groups[0], index, extras),
                "T": groups[0],
            }
            return template.format(**slots)

        note = re.sub(pattern, repl, note)

    # remaining quoted refs become codepoints + classification code
    note = QUOTE_RE.sub(lambda m: "`%s`" % translate_ref(m.group(1), index), note)
    # phonetic-value braces: contents are words, not glyphs
    note = BRACE_RE.sub(lambda m: "[%s]" % m.group(1), note)

    # generic phrases, longest first
    for src, dst in NOTE_PHRASES:
        note = note.replace(src, dst)

    note = _restore(note, titles, index, extras)
    # tidy spacing and separators
    note = re.sub(r"\s+", " ", note).strip()
    note = re.sub(r"，\s*", ", ", note)
    note = re.sub(r"。\s*", ". ", note)
    note = re.sub(r"\s+([,.）)])", r"\1", note)
    note = re.sub(r"\s*，\s*", ", ", note)
    note = re.sub(r"`\s*`", " ", note)
    return note.strip()


# -------------------------------------------------------------- main -----
def main() -> None:
    argv = [a for a in sys.argv[1:] if not a.startswith("-")]
    out_path = None
    if "-o" in sys.argv:
        out_path = sys.argv[sys.argv.index("-o") + 1]

    with io.open(argv[0], encoding="utf-8") as f:
        raw = f.read()
    body = "[" + raw.split("---")[0].strip().rstrip(",") + "]"
    rows = json.loads(body)

    index = load_index()
    extras: dict[str, str] = {}
    lines: list[str] = []

    for row in rows:
        char = row["char"]
        note_parts: list[str] = []
        idc_field = ""

        if "ids" in row:
            idc_field = compile_ids(row["ids"], index, extras)
            if "new_ids" in row:
                note_parts.append(
                    "original form `%s`" % compile_ids(row["ids"], index, extras)
                )
        elif "new_ids" in row:
            idc_field = compile_ids(row["new_ids"], index, extras)
        elif "is" in row:
            target = row["is"]
            idc_field = "= " + (index.get(target) or uplus(target))
            if target in index:
                # the IDC column already carries `= CODE`, so the note only
                # needs the codepoint + code for grep-ability
                note_parts.append("`%s (%s)`" % (uplus(target), index[target]))
            else:
                note_parts.append("`%s`" % uplus(target))

        if "to" in row:
            note_parts.append("c.f. `%s`" % uplus(row["to"]))
        if "note" in row:
            note_parts.append(translate_note_full(row["note"], index, extras))

        line = "%s\t%s" % (uplus(char), idc_field or "-")
        if note_parts:
            line += "\t# " + "; ".join(note_parts)
        else:
            line += "\t#"
        lines.append(line)

    text = "\n".join(lines) + "\n"
    if extras:
        text += "\n# --- components needing a new number in input/xiangxing.txt ---\n"
        for c, why in sorted(extras.items()):
            text += "# %s -> %s\n" % (c, why)

    if out_path:
        with io.open(out_path, "w", encoding="utf-8", newline="\n") as f:
            f.write(text)
        print("written %s (%d lines)" % (out_path, len(lines)))
    else:
        sys.stdout = io.open(sys.stdout.fileno(), "w", encoding="utf-8", closefd=False)
        print(text, end="")


if __name__ == "__main__":
    main()
