from pathlib import Path

from pandas import DataFrame, read_excel


input_dir = Path(__file__).parent.parent / "input"
xlsx_dir = input_dir / "abstract_shape.xlsx"
xlsx_file = read_excel(io=xlsx_dir, sheet_name=None)

names_dict = {"main": "main", "ExtA": "a", "ExtB": "b", "ExtCI": "ci", "ExtGH": "gh"}


def build_historical():
    for sheet_name, file in names_dict.items():
        result = ""
        sheet: DataFrame = xlsx_file.get(sheet_name)
        if "his" in sheet.keys():
            data: DataFrame = sheet.loc[:, ["char", "his", "his.1"]]
            lines = data.to_csv(sep="\t", na_rep="").split("\n")

            store_char = ""
            for line in lines[1:]:
                try:
                    num, char, abst, comm = line.split("\t")

                    if (abst + comm).strip() != "":
                        store_char = char if char.strip() != "" else store_char
                        result += f"{store_char}\t{abst}\t{comm}".rstrip() + "\n"
                except ValueError:
                    pass

            with open(input_dir / f"history_{file}.txt", "w", encoding="utf-8") as f:
                f.write(result)


def build_now():
    for sheet_name, file in names_dict.items():
        result = ""
        sheet: DataFrame = xlsx_file.get(sheet_name)
        data: DataFrame = sheet.loc[:, ["char.1", "con", "recon", "comm"]]
        lines = data.to_csv(sep="\t", na_rep="").split("\n")

        store = ""
        for line in lines[1:]:
            try:
                num, char, abst, reco, comm = line.split("\t")
                if (abst + reco + comm).strip() != "":
                    store = char if char.strip() != "" else store
                    result += f"{store}\t{abst}\t{reco}\t{comm}".rstrip() + "\n"
            except ValueError:
                pass

        with open(input_dir / f"abstract_{file}.txt", "w", encoding="utf-8") as f:
            f.write(result)


def main():
    build_historical()
    build_now()


if __name__ == "__main__":
    main()
