import os
from copy import deepcopy

import yaml


def _unicode(char: str) -> str:
    return "U+" + hex(ord(char)).upper().replace("0X", "")


def _isshape(string: str) -> bool:
    return (ord(string[0]) < 0x2FF0 or ord(string[0]) > 0x2FFF) and string != "X" and string != "↷"


def parse_ass(value: str) -> list[str]:
    value_list = list(value)
    parsed_ass = []
    continue_flag = 0
    for index in range(len(value_list)):
        if continue_flag > 0 and continue_flag < 4:
            continue_flag += 1
            continue
        else:
            continue_flag = 0
            if value_list[min(index + 1, len(value_list) - 1)] == "(":
                parsed_ass.append("".join(value_list[index : index + 4]))
                continue_flag = 1
            else:
                parsed_ass.append(value_list[index])
    return parsed_ass


class AbstractBuilder:
    def parse_ass_dict_from_yamls(self, ass_paths: list[str]):
        parsed_ass_dict = {}
        for ass_path in ass_paths:
            with open(ass_path, "r", encoding="utf-8") as f_ass:
                ass_dict: dict[str, str] = yaml.load(f_ass, Loader=yaml.FullLoader)
            for key, val in ass_dict.items():
                parsed_val = parse_ass(val)
                parsed_ass_dict[key] = parsed_val

        # dump yaml
        temp_ass_path = "abstract/ass.yaml"
        left_brace = ["", "["]
        right_brace = ["", "]"]
        temp_parsed_ass_dict = {}
        for key, val in parsed_ass_dict.items():
            temp_parsed_val = [left_brace[_isshape(value)] + value + right_brace[_isshape(value)] for value in val]
            join_parsed_val = " ".join(temp_parsed_val)
            temp_parsed_ass_dict[key] = join_parsed_val
        with open(temp_ass_path, "w", encoding="utf-8") as f_temp:
            yaml.dump(temp_parsed_ass_dict, f_temp, indent=4, allow_unicode=True)

        return parsed_ass_dict

    def parse_ass_dict(self, ass_dict: dict[str, list[str]]) -> dict[str, list[str]]:
        while True:
            temp_ass_dict = deepcopy(ass_dict)

            for key, val in ass_dict.items():
                if val[0] == "=":
                    ass_dict[key] = val[1:]
                else:
                    new_val = []
                    for index in range(len(val)):
                        if val[index] == "=":
                            continue
                        if val[index] in ass_dict.keys():
                            new_val += ass_dict[val[index]]
                        else:
                            new_val.append(val[index])
                        ass_dict[key] = new_val

            if temp_ass_dict == ass_dict:
                break

        # dump yaml
        temp_ass_path = "result/iterative_ass.yaml"
        left_brace = ["", "["]
        right_brace = ["", "]"]
        for key, val in temp_ass_dict.items():
            temp_val = [left_brace[_isshape(value)] + value + right_brace[_isshape(value)] for value in val]
            join_val = " ".join(temp_val)
            temp_ass_dict[key] = join_val
        with open(temp_ass_path, "w", encoding="utf-8") as f_temp:
            yaml.dump(temp_ass_dict, f_temp, indent=4, allow_unicode=True)

        return ass_dict

    def build_as_dict(self, ass_dict: dict[str, list[str]]) -> dict[int, str]:
        as_set = set()
        for _, val in ass_dict.items():
            for shape in val:
                if _isshape(shape):
                    as_set.add(shape)
        as_list = list(as_set)
        as_list.sort()
        indexed_dict = {i: as_list[i] for i in range(len(as_list))}

        # dump yaml
        temp_ass_path = "abstract/as_dict.yaml"
        with open(temp_ass_path, "w", encoding="utf-8") as f_temp:
            yaml.dump(indexed_dict, f_temp, indent=4, allow_unicode=True)

        return indexed_dict

    def build_indexed_ass_dict(self, ass_dict: dict[str, list[str]], as_dict: dict[int, str]) -> dict[str, list[int]]:
        inversed_as_dict = {val: key for key, val in as_dict.items()}
        indexed_dict = {}
        for key, value in ass_dict.items():
            new_value = []
            for shape in value:
                if shape in inversed_as_dict.keys():
                    new_value.append("$" + str(inversed_as_dict[shape]))
                else:
                    new_value.append(_unicode(shape))
            indexed_dict[_unicode(key)] = ", ".join(new_value)

        # dump yaml
        temp_ass_path = "abstract/indexed_ass.yaml"
        with open(temp_ass_path, "w", encoding="utf-8") as f_temp:
            yaml.dump(indexed_dict, f_temp, indent=4, allow_unicode=True)

        return indexed_dict

    def build_unification(self) -> None:
        ass_path = "result/iterative_ass.yaml"

        with open(ass_path, "r", encoding="utf-8") as f_ass:
            ass_dict: dict[str, str] = yaml.load(f_ass, Loader=yaml.FullLoader)
        parsed_ass_dict = {}
        for key, val in ass_dict.items():
            if str(val) not in parsed_ass_dict.keys():
                parsed_ass_dict[str(val)] = [str(key)]
            else:
                parsed_ass_dict[str(val)] += [str(key)]
        del parsed_ass_dict["X"]

        temp_unification_path = "result/unification.txt"
        with open(temp_unification_path, "w", encoding="utf-8") as f_temp:
            for key, val in parsed_ass_dict.items():
                if "X" not in str(key) and len(val) > 1:
                    f_temp.write("".join(val) + "\n")

    def __init__(self) -> None:
        if not os.path.exists("abstract/"):
            os.mkdir("abstract/")
        if not os.path.exists("result/"):
            os.mkdir("result/")

        parsed_ass_dict = self.parse_ass_dict_from_yamls(
            ["input/abstract_shape_main.yaml", "input/abstract_shape_a.yaml", "input/abstract_shape_comp.yaml", "input/abstract_shape_b.yaml"]
        )
        iteratively_parsed_ass_dict = self.parse_ass_dict(parsed_ass_dict)
        as_dict = self.build_as_dict(iteratively_parsed_ass_dict)
        parsed_indexed_list = self.build_indexed_ass_dict(iteratively_parsed_ass_dict, as_dict)
        self.build_unification()


if __name__ == "__main__":
    AbstractBuilder()
