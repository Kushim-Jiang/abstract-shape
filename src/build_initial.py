import os
import re

import yaml

ids_filter = (
    r"[-#\(\)\*\,\.\:\;\?\[\]\{\}\^_>0123456789abBcdDfghHijJKlMnNpPqQrsStTuUvVwWxyzZ]"
)
cog_filter = r"[\(\)\*？\{\}⇄↻☷⿰⿱⿳⿸0234ABcCgHNoXZ]"
shape_filter = r"[-#\(\)\*\,\.\:\;\?\[\]\^_\{\}>↔↷⿰⿱⿲⿳⿴⿵⿶⿷⿸⿹⿺⿻012〢3〣456789abBcdDfghHijJKlMnNpPqQrsStTuUvVwWxyzZ]"


def _load(path: str):
    with open(path, "r", encoding="utf-8") as f:
        return yaml.load(f, Loader=yaml.FullLoader)


def _merge(dict_1: dict, dict_2: dict):
    res = {}
    for key in dict_1.keys() | dict_2.keys():
        res[key] = (
            ("" if key not in dict_1.keys() else dict_1.get(key))
            + ("; " if key in dict_1.keys() & dict_2.keys() else "")
            + ("" if key not in dict_2.keys() else dict_2.get(key))
        )
    return res


def _dump(path: str, obj):
    with open(path, "w", encoding="utf-8") as f:
        yaml.dump(obj, f, indent=4, allow_unicode=True)


def _sort(src: str) -> str:
    lst = list(set(list(src)))
    lst.sort()
    return "".join(lst)


def _sub(src: str, amb_dict: dict[str, str]) -> str:
    lst = list(re.sub(shape_filter, "", src))
    new_lst = []

    for char in lst:
        for key, val in amb_dict.items():
            char = re.sub(f"{key}", val, char)
        new_lst.append(char)

    return "".join(new_lst)


def _get_uni(src: str, uni_dict: dict[str, str]) -> str:
    res = ""
    for key, val in uni_dict.items():
        if src in key:
            res += key + ": " + val + "; "
    return res[:-2]


class InitialBuilder:
    INIT_CODEPOINT: int = -1
    FINA_CODEPOINT: int = -1

    def build_ids_dict(self, file_path: str) -> dict[str, list[str]]:
        ids_dict: dict[str, list[str]] = {}

        if file_path.endswith(".yaml"):
            ids_dict = _load(file_path)
        elif file_path.endswith(".txt"):
            with open(file_path, "r", encoding="utf-8") as f_ids:
                line = f_ids.readline().strip()
                while line:
                    char, idses = line.split("\t")[0], line.split("\t")[1:]
                    list_single_ids = []
                    for idses in idses:
                        list_single_ids += idses.split(";")
                    ids_dict[char] = [
                        re.sub(ids_filter, "", i) for i in list_single_ids
                    ]
                    line = f_ids.readline().strip()

        # dump yaml
        _dump("initial/built_ids.yaml", ids_dict)
        return ids_dict

    def build_cognition_dict(self, file_path: str) -> dict[str, list[str]]:
        cog_dict: dict[str, list[str]] = {}

        if file_path.endswith(".yaml"):
            cog_dict = _load(file_path)
        elif file_path.endswith(".txt"):
            with open(file_path, "r", encoding="utf-8") as f_cog:
                line = f_cog.readline().strip()
                while line:
                    str_character, str_cognition = line.split("\t")
                    str_cognition = re.sub(cog_filter, "", str_cognition)
                    if str_character in cog_dict.keys():
                        cog_dict[str_character].append(str_cognition)
                    else:
                        cog_dict[str_character] = [str_cognition]
                    line = f_cog.readline().strip()

        # dump yaml
        _dump("initial/built_cognition.yaml", cog_dict)
        return cog_dict

    def build_reference_ass(
        self,
        ids_dict: dict[str, list[str]],
        cog_dict: dict[str, list[str]],
        uni_dict: dict[str, str],
        amb_dict: dict[str, str],
        char_range: range,
    ):
        # build initial ass dict
        original_ass_dict = {}
        for codepoint in char_range:
            char = chr(codepoint)
            if char not in ids_dict.keys():
                ids_dict[char] = [char]
            if char not in cog_dict.keys():
                cog_dict[char] = []

            for ids in ids_dict[char]:
                for cognition in cog_dict[char]:
                    if (
                        set(_sub(ids, amb_dict)).issubset(set(_sort(cognition)))
                        or set(_sub(ids, amb_dict)) == set(char)
                    ) and re.sub(ids_filter, "", ids) != "":
                        original_ass_dict[char] = re.sub(ids_filter, "", ids)

        for codepoint in char_range:
            if chr(codepoint) not in original_ass_dict.keys():
                original_ass_dict[chr(codepoint)] = [chr(codepoint)]

        _dump("initial/reference_ass.yaml", original_ass_dict)

        temp_path = "initial/reference.txt"
        with open(temp_path, "w", encoding="utf-8") as f_out:
            for codepoint in char_range:
                f_out.write(
                    "\t".join(
                        [
                            chr(codepoint),
                            str(ids_dict[chr(codepoint)]),
                            str(cog_dict[chr(codepoint)]),
                            _get_uni(chr(codepoint), uni_dict),
                            "".join(original_ass_dict[chr(codepoint)]),
                            chr(codepoint),
                        ]
                    )
                    + "\n"
                )
        return original_ass_dict

    def __init__(self, init: int, fina: int) -> None:
        self.INIT_CODEPOINT = init
        self.FINA_CODEPOINT = fina

        if not os.path.exists("initial/"):
            os.mkdir("initial/")

        ids_dict = self.build_ids_dict("data/ids_lv2.txt")
        # ids_dict = self.build_ids_dict("initial/built_ids.yaml")

        cog_dict = self.build_cognition_dict("data/ies20240314.txt")
        # cog_dict = self.build_cognition_dict("initial/built_cognition.yaml")

        uni_dict = _merge(_load("data/unify_eiso.yaml"), _load("data/similar_fei.yaml"))
        amb_dict = _load("data/ambiguous.yaml")
        ass_reference = self.build_reference_ass(
            ids_dict,
            cog_dict,
            uni_dict,
            amb_dict,
            range(self.INIT_CODEPOINT, self.FINA_CODEPOINT + 1),
        )


if __name__ == "__main__":
    InitialBuilder(0x3400, 0x4DBF)
