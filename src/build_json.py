import json
from pathlib import Path


REPO_DIR = Path(__file__).parent.parent
TXT_DIR = REPO_DIR / "input"
JSON_DIR = REPO_DIR.parent / "kushim-jiang.github.io" / "assets" / "abstract.json"


FILE_NAMES = ["main", "a", "b", "ci", "gh"]
REPLACEMENTS = {
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


def _parse_line(line: str) -> tuple[str, str, str, str]:
    line = line.strip()
    parts = line.split("\t") + [""] * 4
    return parts[:4]


def txt_to_json() -> None:
    # first parsing
    first_result = []
    for file_name in FILE_NAMES:
        file_path = TXT_DIR / f"abstract_{file_name}.txt"
        with file_path.open("r", encoding="utf-8") as f:
            for line in f:
                char, src_one, src_two, comment = _parse_line(line)
                src_one = src_one if not src_one.startswith("*") else char + "(" + src_one.removeprefix("*") + ")"
                src_two = src_two if not src_two.startswith("*") else char + "(" + src_two.removeprefix("*") + ")"
                for old, new in REPLACEMENTS.items():
                    comment = comment.replace(old, new)
                first_result.append(
                    {
                        "char": char,
                        "src_one": src_one,
                        "src_two": src_two,
                        "comment": comment.strip(),
                    }
                )

    # second parsing
    from ids import IDS

    chars = set()
    for item in first_result:
        src_one = item["src_one"]
        comment = item["comment"]
        if not src_one.startswith("="):
            try:
                ids = IDS.from_str(src_one)
                if ids and ids.count() == 1 and src_one != "X":
                    chars.add((repr(ids), comment))
            except Exception:
                pass

    # read geta.txt
    geta_path = TXT_DIR / "geta.txt"
    if geta_path.exists():
        with geta_path.open("r", encoding="utf-8") as f:
            for line in f:
                parts = line.strip().split("\t")
                if len(parts) >= 2:
                    glyph, shape = parts[:2]
                    chars.add((glyph, shape))

    # sort chars
    chars_list = sorted(list(chars), key=lambda x: x[0])

    entries = []
    for item in first_result:
        char: str = item["char"]
        src_one: str = item["src_one"]
        src_two: str = item["src_two"]
        comment: str = item["comment"]
        entry = {"char": char}
        if src_one == "X":
            entry["note"] = comment
            entry["x"] = True
            try:
                ids = IDS.from_str(src_two)
                if ids is not None:
                    entry["ref"] = repr(ids)
            except Exception:
                pass
        elif src_one.startswith("="):
            entry["note"] = comment
            try:
                to_ids = IDS.from_str(src_one[1:])
                entry["to"] = repr(to_ids)
            except Exception:
                entry["to"] = src_one[1:]
            try:
                ref_ids = IDS.from_str(src_two)
                if ref_ids is not None:
                    entry["ref"] = repr(ref_ids)
            except Exception:
                pass
        else:
            try:
                ids = IDS.from_str(src_one)
                if ids is not None:
                    entry["ids"] = repr(ids)
                    if ids.count() == 1:
                        try:
                            ref_ids = IDS.from_str(src_two)
                            if ref_ids is not None:
                                entry["ref"] = repr(ref_ids)
                        except Exception:
                            pass
                    else:
                        entry["note"] = comment
                        try:
                            ref_ids = IDS.from_str(src_two)
                            if ref_ids is not None:
                                entry["ref"] = repr(ref_ids)
                        except Exception:
                            pass
            except Exception:
                pass
        entries.append(entry)

    # sort entries by char, ids, x
    def entry_sort_key(e: dict):
        return (
            e.get("char", ""),
            e.get("ids", ""),
            str(e.get("x", False)),
        )

    entries_list = sorted(entries, key=entry_sort_key)

    # output
    output = {
        "chars": chars_list,
        "entries": entries_list,
    }
    with JSON_DIR.open("w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)


def main():
    txt_to_json()


if __name__ == "__main__":
    main()
