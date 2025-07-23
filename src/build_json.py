from collections import deque
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
    "·": "・",
    "…": "⋯",
    "SW": "《说文解字》",
    "GY": "《广韵》",
    "CY": "《常用漢字表》（日本）",
    "ZG": "《中国语言资源保护工程汉语方言用字规范》",
    "JY": "《集韵》",
    "WS": "《和製漢字の辞典（2014）》",
    "FY": "《汉语方言大字典》",
}


def parse_line(line: str, num: int) -> list[str]:
    line = line.strip()
    parts = line.split("\t") + [""] * num
    return parts[:num]


def decompose_ids(REPLACEMENTS: dict, ids_repr: str) -> str:
    if ids_repr == "None":
        return None
    while True:
        new_repr = ids_repr
        for comp in re.findall(r"\[.*?\]", ids_repr):
            if comp in REPLACEMENTS:
                new_repr = re.sub(re.escape(comp), REPLACEMENTS[comp], new_repr)
        if new_repr == ids_repr:
            break
        assert len(new_repr) < 100, f"New representation too long: {new_repr}"
        ids_repr = new_repr
    return ids_repr


def parse_txt():
    result: list[dict] = []
    for file_name in FILE_NAMES:
        file_path = TXT_DIR / f"abstract_{file_name}.txt"
        with file_path.open("r", encoding="utf-8") as f:
            for line in f:
                char, src_one, src_two, comment = parse_line(line, 4)
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


def get_is_graph(ENTRIES: list[dict]) -> dict[str, set[str]]:
    graph = {}
    for entry in ENTRIES:
        a, b = entry.get("char"), entry.get("is")
        if a and b:
            graph.setdefault(b, set()).add(a)
    return graph


def find_nodes_reachable_to(graph: dict[str, set[str]], target: str) -> set[str]:
    if target not in graph:
        return set()

    visited = set()
    queue = deque()

    if target in graph:
        queue.extend(graph[target])

    while queue:
        current = queue.popleft()
        if current not in visited:
            visited.add(current)
            if current in graph:
                for neighbor in graph[current]:
                    if neighbor not in visited:
                        queue.append(neighbor)
    return visited


def get_replacements(ENTRIES: list[dict], only_is: bool) -> dict:
    result = {}

    for entry in ENTRIES:
        if not entry.get("char"):
            continue

        char_repr = repr(IDS.from_str(entry["char"]))
        if entry.get("x") is True:
            result[char_repr] = "[X]"
            continue

        if entry["char"] == "卩":
            pass
        is_entry = [e for e in ENTRIES if e.get("is") and e.get("char") == entry["char"]]
        ids_entry = [e for e in ENTRIES if e.get("ids") and e.get("char") == entry["char"]]

        if len(is_entry) == 1 and len(ids_entry) == 0:
            is_repr = repr(IDS.from_str(is_entry[0]["is"]))
            result[char_repr] = is_repr
            continue
        if not only_is:
            if len(ids_entry) == 1:
                ids_repr = ids_entry[0]["ids"]
                result[char_repr] = ids_repr
                continue

    return result


def get_variants(ENTRIES: list[dict], IS_RELATION: dict, REPLACEMENTS: dict) -> dict:
    result = {}
    for entry in ENTRIES:
        if "ids" in entry:
            ids_repr = entry["ids"]
            ids_repr = decompose_ids(REPLACEMENTS, ids_repr)

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
        result[ids_repr] = VARIANTS[ids_repr][0] + "@" + "".join(sorted(VARIANTS[ids_repr][1]))
        if len(VARIANTS[ids_repr][0]) > 1:
            print(f"Warning: Multiple characters for {ids_repr}: {VARIANTS[ids_repr][0]}")
    return result


def decompose(ENTRIES: list[dict], REPLACEMENTS: dict):
    for entry in ENTRIES:
        if "ids" in entry:
            ids_repr = entry["ids"]
            new_ids_repr = decompose_ids(REPLACEMENTS, ids_repr)
            if new_ids_repr != ids_repr:
                entry["new_ids"] = new_ids_repr


def assert_refer(ENTRIES, REPLACEMENTS, ALL):
    for entry in ENTRIES:
        if "refer" in entry:
            decomposed_ids = decompose_ids(REPLACEMENTS, entry["refer"])
            for ids in re.findall(r"\[.*?\]", decomposed_ids):
                assert ids[1:-1] not in ALL, f"Referenced IDS {ids} found in all IDSs"


def get_geta() -> dict[str, str]:
    geta_path = TXT_DIR / "geta.txt"
    if not geta_path.exists():
        return {}

    with geta_path.open("r", encoding="utf-8") as f:
        lines = f.readlines()

    result = {}
    for line in lines:
        key, value = line.split("\t")
        for old, new in BIBLIOGRAPHY.items():
            value = value.replace(old, new)
        result[key] = value.strip()
    return result


def get_extra(REPLACEMENTS: dict[str, str], ALL_IDS: str) -> list[dict[str, str]]:
    extra_path = TXT_DIR / "extra.txt"
    if not extra_path.exists():
        return []

    with extra_path.open("r", encoding="utf-8") as f:
        lines = f.readlines()
    result = []
    for line in lines:
        shape, refer, note = line.split("\t")
        line_dict = {}

        shape = repr(IDS.from_str(shape.strip()))
        shape = decompose_ids(REPLACEMENTS, shape.strip())
        for ids in re.findall(r"\[.*?\]", shape):
            assert ids[1:-1] not in ALL_IDS, f"Referenced IDS {ids} found in all IDSs"
        refer = repr(IDS.from_str(refer.strip()))
        refer = decompose_ids(REPLACEMENTS, refer.strip())
        if refer:
            for ids in re.findall(r"\[.*?\]", refer):
                assert ids[1:-1] not in ALL_IDS, f"Referenced IDS {ids} found in all IDSs"

        for old, new in BIBLIOGRAPHY.items():
            note = note.replace(old, new)

        if shape:
            line_dict["ids"] = shape
        if refer:
            line_dict["refer"] = refer
        if note:
            line_dict["note"] = note.strip()

        if line_dict:
            result.append(line_dict)

    return result


def get_ob(REPLACEMENTS: dict[str, str], ALL_IDS: str) -> dict[str, str]:
    ob_path = TXT_DIR / "ob.txt"
    if not ob_path.exists():
        return {}
    with ob_path.open("r", encoding="utf-8") as f:
        lines = f.readlines()

    line_dicts = []
    for line in lines:
        code, char, con, recon, comm = parse_line(line.strip(), 5)
        line_dict = {"code": code, "ob": char}
        if con:
            con = repr(IDS.from_str(con.strip()))
            con = decompose_ids(REPLACEMENTS, con.strip())
            for ids in re.findall(r"\[.*?\]", con):
                assert ids[1:-1] not in ALL_IDS, f"Referenced IDS {ids} found in all IDSs"
            line_dict["ids"] = con
        if recon:
            recon = repr(IDS.from_str(recon.strip()))
            recon = decompose_ids(REPLACEMENTS, recon.strip())
            for ids in re.findall(r"\[.*?\]", recon):
                assert ids[1:-1] not in ALL_IDS, f"Referenced IDS {ids} found in all IDSs"
            line_dict["refer"] = recon
        if comm:
            line_dict["note"] = comm.strip()
        if line_dict:
            line_dicts.append(line_dict)

    ids_list = []
    for item in line_dicts:
        if "ids" in item:
            if item["ids"] not in ids_list:
                ids_list.append(item["ids"])

    result = {}
    for ids in ids_list:
        chars = [item["ob"] + item["code"] for item in line_dicts if item["ids"] == ids]
        result[ids] = chars[0] + "@" + "".join(chars[1:])
    return result


def txt_to_json() -> None:
    # first parsing
    ONE_ENTRIES = parse_txt()

    # second parsing
    TWO_ENTRIES = parse_dict(ONE_ENTRIES)

    is_replacements = get_replacements(TWO_ENTRIES, only_is=True)
    for entry in TWO_ENTRIES:
        if "ids" in entry:
            entry["ids"] = decompose_ids(is_replacements, entry["ids"])

    # third parsing
    is_graph = get_is_graph(TWO_ENTRIES)

    is_relation = {b: "".join(find_nodes_reachable_to(is_graph, b)) for b in is_graph}
    THREE_ALL = "".join(a for as_ in is_graph.values() for a in as_)

    FOUR_REPLACE = get_replacements(TWO_ENTRIES, only_is=False)
    FIVE_VARIANTS = get_variants(TWO_ENTRIES, is_relation, FOUR_REPLACE)
    SIX_VARIANTS = get_new_variants(FIVE_VARIANTS)

    decompose(TWO_ENTRIES, FOUR_REPLACE)

    GETA = get_geta()
    EXTRA = get_extra(FOUR_REPLACE, THREE_ALL)
    TWO_ENTRIES.extend(EXTRA)

    assert_refer(TWO_ENTRIES, FOUR_REPLACE, THREE_ALL)

    OB = get_ob(FOUR_REPLACE, THREE_ALL)

    # write to json
    JSON_DIR.parent.mkdir(parents=True, exist_ok=True)
    with JSON_DIR.open("w", encoding="utf-8") as f:
        json.dump({"entries": TWO_ENTRIES, "variants": SIX_VARIANTS, "geta": GETA, "ob": OB}, f, ensure_ascii=False, indent=2)


def main():
    txt_to_json()


if __name__ == "__main__":
    main()
