from pathlib import Path

from pandas import DataFrame, read_excel


INPUT_DIR = Path(__file__).parent.parent / "input"
XLSX_DIR = INPUT_DIR / "abstract_shape.xlsx"
XLSX_FILE = read_excel(io=XLSX_DIR, sheet_name=None)

names_dict = {"main": "main", "ExtA": "a", "ExtB": "b", "ExtCI": "ci", "ExtGH": "gh"}


def build_historical():
    for sheet_name, file in names_dict.items():
        result = ""
        sheet: DataFrame = XLSX_FILE.get(sheet_name)
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

            with open(INPUT_DIR / f"history_{file}.txt", "w", encoding="utf-8") as f:
                f.write(result)


def build_now():
    for sheet_name, file in names_dict.items():
        result = ""
        sheet: DataFrame = XLSX_FILE.get(sheet_name)
        data: DataFrame = sheet.loc[:, ["char.1", "con", "recon", "comm"]]
        lines = data.to_csv(sep="\t", na_rep="").split("\n")

        store = ""
        for line in lines[1:]:
            try:
                num, char, construct, reconstruct, comment = line.split("\t")
                if (construct + reconstruct + comment).strip() != "":
                    store = char if char.strip() != "" else store
                    result += "\t".join([store, construct, reconstruct, comment]).rstrip() + "\n"
            except ValueError:
                pass

        with open(INPUT_DIR / f"abstract_{file}.txt", "w", encoding="utf-8") as f:
            f.write(result)


def build_geta():
    sheet: DataFrame = XLSX_FILE.get("geta")

    if sheet is not None:
        result = ""
        for _, row in sheet.iterrows():
            result += f"{row.iloc[0]}\t{row.iloc[1]}\n"
        result = result.split("\n", 1)[1]

        with open(INPUT_DIR / "geta.txt", "w", encoding="utf-8") as f:
            f.write(result)


def build_extra():
    sheet: DataFrame = XLSX_FILE.get("extra")

    if sheet is not None:
        result = ""
        for _, row in sheet.iterrows():
            shape = row.iloc[0] if not str(row.iloc[0]) == "nan" else ""
            refer = row.iloc[1] if not str(row.iloc[1]) == "nan" else ""
            note = row.iloc[2] if not str(row.iloc[2]) == "nan" else ""
            result += f"{shape}\t{refer}\t{note}\n"

        with open(INPUT_DIR / "extra.txt", "w", encoding="utf-8") as f:
            f.write(result)


def build_ob():
    sheet: DataFrame = XLSX_FILE.get("ob")

    if sheet is not None:
        result = ""

        data: DataFrame = sheet.loc[:, ["num", "glyph", "con", "recon", "comm"]]
        lines = data.to_csv(sep="\t", na_rep="").split("\r\n")

        store_code, store_char = "", ""
        for line in lines[1:]:
            try:
                num, code, char, construct, reconstruct, comment = line.split("\t")
                if (construct + reconstruct + comment).strip() != "":
                    store_code = code.zfill(4) if code.strip() != "" else store_code
                    store_char = char if char.strip() != "" else store_char
                    result += "\t".join([store_code, store_char, construct, reconstruct, comment]).rstrip() + "\n"
            except ValueError:
                pass

        with open(INPUT_DIR / f"ob.txt", "w", encoding="utf-8") as f:
            f.write(result)


def main():
    build_historical()
    build_now()
    build_geta()
    build_extra()
    build_ob()


if __name__ == "__main__":
    main()
