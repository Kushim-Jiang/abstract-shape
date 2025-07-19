import json
import re
from pathlib import Path

from ids import IDS


REPO_DIR = Path(__file__).parent.parent
TXT_DIR = REPO_DIR / "input"
JSON_DIR = REPO_DIR.parent / "kushim-jiang.github.io" / "assets" / "abstract.json"


FILE_NAMES = ["main", "a", "b", "ci", "gh"]
BIBLIOGRAPHY = {
    "“": "「",
    "”": "」",
    "‘": "『",
    "’": "』",
    "SW": "《说文解字》",
    "GY": "《广韵》",
    "CY": "《常用漢字表》（日本）",
    "ZG": "《中国语言资源保护工程汉语方言用字规范》",
    "JY": "《集韵》",
    "WS": "《和製漢字の辞典（2014）》",
    "FY": "《汉语方言大字典》",
}


def parse_line(line: str) -> tuple[str, str, str, str]:
    line = line.strip()
    parts = line.split("\t") + [""] * 4
    return parts[:4]


def decompose_ids(entry: dict, FOUR_REPLACE: dict, ids_repr: str) -> str:
    while True:
        new_repr = ids_repr
        for comp in re.findall(r"\[.*?\]", ids_repr):
            if comp in FOUR_REPLACE:
                new_repr = re.sub(re.escape(comp), FOUR_REPLACE[comp], new_repr)
        if new_repr == ids_repr:
            break
        assert len(new_repr) < 100, f"New representation for {entry['char']} too long: {new_repr}"
        ids_repr = new_repr
    return ids_repr


def parse_txt():
    result: list[dict] = []
    for file_name in FILE_NAMES:
        file_path = TXT_DIR / f"abstract_{file_name}.txt"
        with file_path.open("r", encoding="utf-8") as f:
            for line in f:
                char, src_one, src_two, comment = parse_line(line)
                src_one = src_one if not src_one.startswith("*") else char + "(" + src_one.removeprefix("*") + ")"
                for old, new in BIBLIOGRAPHY.items():
                    comment = comment.replace(old, new)
                result.append({"char": char, "src_one": src_one, "src_two": src_two, "comment": comment.strip()})
    return result


def parse_dict(ENTRIES: list[dict]) -> list[dict]:
    result: list[dict] = []
    for entry in ENTRIES:
        entry_dict = {"char": entry["char"]}

        if entry["src_one"] == "X":
            entry_dict["x"] = True
        elif not entry["src_one"].startswith("="):
            entry_dict["ids"] = repr(IDS.from_str(entry["src_one"]))
        else:
            entry_dict["is"] = entry["src_one"].removeprefix("=")

        if entry["src_two"] and not entry["src_two"].startswith("*"):  # assert `src_two` is raw IDS
            entry_dict["refer"] = repr(IDS.from_str(entry["src_two"]))
        elif entry["src_two"].startswith("*"):
            entry_dict["to"] = entry["src_two"].removeprefix("*")

        if entry["comment"]:
            entry_dict["note"] = entry["comment"]
        result.append(entry_dict)
    return result


def get_is_graph(ENTRIES: list[dict]) -> dict:
    graph = {}
    for entry in ENTRIES:
        a, b = entry.get("char"), entry.get("is")
        if a and b:
            graph.setdefault(b, set()).add(a)
    return graph


def get_replacements(ENTRIES: list[dict], ALL_IDS: str) -> dict:
    result = {}
    chars = set(entry["char"] for entry in ENTRIES if entry["char"] not in ALL_IDS)
    ids_s = "".join(entry["ids"] for entry in ENTRIES if "ids" in entry)
    ids_s += "".join(entry["refer"] for entry in ENTRIES if "refer" in entry)
    for char in chars:
        char_repr = repr(IDS.from_str(char))
        result_repr_s = [entry["ids"] for entry in ENTRIES if entry.get("char") == char and "ids" in entry and "(" not in entry["ids"]]
        if char_repr not in result_repr_s and char_repr in ids_s and result_repr_s:
            result[char_repr] = result_repr_s[0]
    return result


def get_variants(ENTRIES: list[dict], IS_RELATION: dict, REPLACEMENTS: dict) -> dict:
    result = {}
    for entry in ENTRIES:
        if "ids" in entry:
            ids_repr = entry["ids"]
            ids_repr = decompose_ids(entry, REPLACEMENTS, ids_repr)

            chars_str = result.setdefault(ids_repr, ["", ""])
            if entry["char"] not in chars_str[0]:
                chars_str[0] += entry["char"]
            if entry["char"] in IS_RELATION:
                for c in IS_RELATION[entry["char"]]:
                    if c not in chars_str[1]:
                        chars_str[1] += c
    return result


def get_new_variants(VARIANTS: dict) -> dict:
    result = {}
    ids_repr_sorted = sorted(VARIANTS.keys())
    for ids_repr in ids_repr_sorted:
        if len(VARIANTS[ids_repr][0]) > 1:
            for variant in VARIANTS[ids_repr][0]:
                if variant not in ids_repr:
                    VARIANTS[ids_repr][0] = "".join(v for v in VARIANTS[ids_repr][0] if v != variant)
                    if variant not in VARIANTS[ids_repr][1]:
                        VARIANTS[ids_repr][1] += variant
        result[ids_repr] = VARIANTS[ids_repr][0] + "@" + VARIANTS[ids_repr][1]
        if len(VARIANTS[ids_repr][0]) > 1:
            print(f"Warning: Multiple characters for {ids_repr}: {VARIANTS[ids_repr][0]}")
    return result


def decompose(ENTRIES: list[dict], REPLACEMENTS: dict):
    for entry in ENTRIES:
        if "ids" in entry:
            ids_repr = entry["ids"]
            new_ids_repr = decompose_ids(entry, REPLACEMENTS, ids_repr)
            if new_ids_repr != ids_repr:
                entry["new_ids"] = new_ids_repr


def assert_refer(ENTRIES, REPLACEMENTS):
    ids_s = ""
    for entry in ENTRIES:
        ids = entry.get("ids") or ""
        new_ids = entry.get("new_ids") or ""
        ids_s += ids + new_ids
    for entry in ENTRIES:
        if "refer" in entry:
            decomposed_ids = decompose_ids(entry, REPLACEMENTS, entry["refer"])
            for ids in re.findall(r"\[.*?\]", decomposed_ids):
                assert ids in ids_s, f"Referenced IDS {ids} not found in all IDSs"


def txt_to_json() -> None:
    # first parsing
    ONE_ENTRIES = parse_txt()

    # second parsing
    TWO_ENTRIES = parse_dict(ONE_ENTRIES)

    # third parsing
    is_graph = get_is_graph(TWO_ENTRIES)
    is_relation = {b: "".join(sorted(as_)) for b, as_ in is_graph.items()}
    THREE_ALL = "".join(a for as_ in is_graph.values() for a in as_)

    FOUR_REPLACE = get_replacements(TWO_ENTRIES, THREE_ALL)
    FIVE_VARIANTS = get_variants(TWO_ENTRIES, is_relation, FOUR_REPLACE)
    SIX_VARIANTS = get_new_variants(FIVE_VARIANTS)

    decompose(TWO_ENTRIES, FOUR_REPLACE)
    assert_refer(TWO_ENTRIES, FOUR_REPLACE)

    # write to json
    JSON_DIR.parent.mkdir(parents=True, exist_ok=True)
    with JSON_DIR.open("w", encoding="utf-8") as f:
        json.dump({"entries": TWO_ENTRIES, "variants": SIX_VARIANTS}, f, ensure_ascii=False, indent=2)


def main():
    txt_to_json()


if __name__ == "__main__":
    main()
