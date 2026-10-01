# -*- coding: utf-8 -*-
"""Re-code input/xiangxing.txt with a Gardiner-style natural classification.

Reads  : input/xiangxing.txt   (component <TAB> legacy decimal code)
Writes : result/xiangxing_coded.tsv

The letter families are decided by the SEMANTIC DOMAIN of the depicted object
(象物 / 象人 / 象工 + 记号 and 衍生 layers), not by stroke count or radical.
Ordering inside a family follows the source file, which is already
"以类相从" (related items adjacent).

Run:  python src/build_xiangxing.py
"""

from __future__ import annotations

import io
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, "input", "xiangxing.txt")
DST = os.path.join(ROOT, "result", "xiangxing_coded.tsv")

# --------------------------------------------------------------------------
# 1. the letter families (upper layer = the three classical groups)
# --------------------------------------------------------------------------
FAMILIES = [
    # 象物 : what the world is made of
    ("A", "天象", "象物"),
    ("B", "地文土石", "象物"),
    ("C", "水冰", "象物"),
    ("D", "火", "象物"),
    ("E", "草木禾竹", "象物"),
    ("F", "飞禽", "象物"),
    ("G", "走兽", "象物"),
    ("H", "鳞甲虫豸", "象物"),
    # 象人 : the human body and its persons
    ("I", "人形与人称", "象人"),
    ("J", "头面五官", "象人"),
    ("K", "手与足", "象人"),
    ("L", "躯体内藏与毛羽", "象人"),
    # 象工 : what humans make
    ("M", "衣食丝革", "象工"),
    ("N", "饮食器皿", "象工"),
    ("O", "宫室居处", "象工"),
    ("P", "器用工具", "象工"),
    ("Q", "兵戎畋猎", "象工"),
    ("R", "行止旌旗", "象工"),
    ("S", "祭祀与语言文字", "象工"),
    # 记号 : pure marks, no depicted object
    ("T", "笔画与几何", "记号"),
    ("U", "数字与序数", "记号"),
    ("V", "抽象关系记号", "记号"),
    # 衍生 : not independently meaningful
    ("W", "形似与推演构件", "衍生"),
    ("X", "域外符号", "衍生"),
    ("Y", "合体式与整体象形", "衍生"),
    ("Z", "未定待考", "衍生"),
]
FAMILY_NAME = {code: name for code, name, _ in FAMILIES}
FAMILY_GROUP = {code: group for code, _, group in FAMILIES}

# --------------------------------------------------------------------------
# 2. range rules over the legacy decimal code (evaluated in order)
# --------------------------------------------------------------------------
RANGES = [
    ((0, 10), "U"),  # 〇一四五六七八九十
    ((100, 199), "U"),  # 乙丙丁己壬癸 (序数干支)
    ((200, 219), "T"),  # 丨丿丶𠄌𠃊𠂆〇(圓)厶
    ((300, 399), "V"),  # 小上入丩卜丯爻叕非冓丫串乄兩
    # ---- 象人 ----
    ((10000, 10299), "I"),
    ((11000, 11599), "J"),
    ((12000, 13099), "K"),
    ((14000, 14099), "L"),
    # ---- 象物 ----
    ((20000, 20099), "A"),
    ((21000, 21499), "Z"),  # 吕玉貝卪毌 : 混合块，逐项决定
    ((21500, 21699), "C"),
    ((21700, 21799), "D"),
    ((22000, 22099), "E"),
    ((25000, 25099), "B"),
    # ---- 象工 ----
    ((30000, 30499), "M"),
    ((31000, 31399), "N"),
    ((32000, 32199), "O"),
    ((33000, 33299), "Q"),
    # ---- 动物 ----
    ((40000, 41099), "G"),
    ((41100, 41999), "H"),
    ((42000, 42099), "H"),
    ((43000, 43099), "F"),
    # ---- 衍生 ----
    ((60000, 69999), "W"),  # 形似/伪构件：60xxx
    ((70000, 70199), "W"),  # 借用字形命名的伪构件
    ((70200, 70599), "X"),  # 谚文 / 卍 / 卦爻 / 其它非汉字符号
    ((70600, 99999), "W"),  # 形位码（逐笔格位码）
    ((100000, 100009), "Y"),  # 合体式与整体象形（四角式整体字）
    ((100010, 199999), "W"),  # 1xxxxx 形位码
    ((200000, 99999999), "W"),  # 更长的形位码
]

# --------------------------------------------------------------------------
# 3. per-component overrides (semantics beat the legacy block)
# --------------------------------------------------------------------------
# "改" = deliberately moved out of its legacy block, see the taxonomy document
OVERRIDE = dict([
    # 21xxx 是「财货」功能块：按自然分类必须拆开
    ("吕", "N"),  # 吕 = 铜锭象形 -> 器/金
    ("玉", "B"),  # 玉 = 石材 -> 地文
    ("貝", "H"),  # 貝 = 海贝 -> 鳞甲
    ("卪", "P"),  # 卪 = 符节
    ("毌", "V"),  # 毌 = 贯穿之形
    # 22xxx 里混着的非草木构件
    ("幺", "M"),  # 幺 = 束丝
    ("巠", "M"),  # 巠 = 织机的纵线
    ("叀", "P"),  # 叀 = 纺专
    ("世", "V"),  # 世 = 止之变形
    ("不", "E"),  # 不 = 花柎象形
    ("丂", "V"),
    ("兮", "V"),
    ("乎", "V"),
    ("帀", "V"),
    ("互", "P"),
    ("𠂂", "Z"),
    # 30xxx 是「人工物」大杂烩
    ("工", "P"),
    ("曲", "P"),
    ("巫", "S"),  # 巫 = 巫者
    ("𱖆", "P"),
    ("冊", "P"),
    ("㢧", "P"),
    ("壴", "P"),  # 壴 = 鼓
    ("𫪡", "P"),
    ("珡", "P"),  # 珡 = 琴
    ("勹", "I"),  # 勹 = 人曲形
    ("冖", "M"),  # 冖 = 覆盖
    ("庚", "Z"),
    ("南", "P"),  # 南 = 乐器
    ("甬", "P"),  # 甬 = 钟柄
    ("㐃", "P"),  # 㐃 = 锤子
    ("㐁", "M"),  # 㐁 = 席
    # 31xxx 里混着的工具
    ("力", "P"),
    ("耒", "P"),
    ("午", "P"),
    ("辰", "P"),  # 辰 = 蚌镰
    ("弋", "P"),
    ("乂", "P"),
    ("录", "P"),
    ("厄", "P"),
    ("㭉", "P"),
    ("且", "S"),  # 且 = 神主/俎
    ("氏", "Z"),
    # 32xxx 里混着的祭祀/器物
    ("示", "S"),
    ("主", "S"),
    ("瓦", "N"),
    ("帚", "P"),
    ("彗", "P"),
    ("爾", "Z"),
    ("襾", "M"),
    ("西", "Z"),  # 西 = 鸟巢，说不一
    ("𠰞", "Z"),
    ("余", "O"),
    # 33xxx 里混着的交通
    ("行", "R"),
    ("車", "R"),
    ("舟", "R"),
    ("㫃", "R"),
    ("傘", "M"),
    ("中", "Z"),
    ("亞", "O"),
    ("网", "Q"),
    ("克", "Q"),  # 克 = 人戴胄
    ("單", "Q"),
    ("𠦒", "Z"),
    ("𰅱", "Z"),
    # 4xxxx 里的鱗甲虫豸
    ("它", "H"),
    ("巴", "H"),
    ("虫", "H"),
    ("龜", "H"),
    ("黽", "H"),
    ("𬟏", "H"),
    ("萬", "H"),  # 萬 = 蠍
    ("万", "H"),
    ("禹", "H"),
    ("昆", "H"),
    ("卵", "H"),
    ("丽", "Z"),
    ("曱", "Z"),
    ("求", "Z"),
    # 人体块里的
    ("叒", "K"),  # 叒 = 三又
])

# 需要人工复核的（可能是「自然类」与「作者原判」不同）
TODO_REVIEW = {
    "業", "黄", "無", "異", "競", "文", "𦰩", "帝", "𢎘", "毛", "羽", "角",
    "禸", "釆", "白", "彡", "而", "冉", "丱", "吕", "卪", "毌", "西", "㐁",
    "庚", "南", "甬", "㐃", "𠀃", "丄", "𠁣", "𡇒", "乃", "龷", "帀", "𠂂",
    "互", "㬰", "害", "𠒅", "𢒕", "𡿩",
}


def classify(char: str, code: int) -> str:
    if char in OVERRIDE:
        return OVERRIDE[char]
    for (lo, hi), family in RANGES:
        if lo <= code <= hi:
            return family
    # 兜底：`*` 打头的一律是形似／推演构件（如 *屮 511）
    if char.startswith("*"):
        return "W"
    return "Z"


def main() -> None:
    rows = []
    with io.open(SRC, encoding="utf-8") as f:
        for line in f:
            line = line.rstrip("\n")
            if not line.strip():
                continue
            parts = line.split("\t")
            if len(parts) < 2 or not parts[1].strip().isdigit():
                rows.append((parts[0], None))
                continue
            rows.append((parts[0], int(parts[1])))

    counters: dict[str, int] = {}
    out = []
    for char, code in rows:
        family = classify(char, code if code is not None else 999999)
        counters[family] = counters.get(family, 0) + 1
        new_code = "%s%02d" % (family, counters[family])
        flags = []
        if char in OVERRIDE:
            flags.append("改")
        if char in TODO_REVIEW:
            flags.append("待核")
        out.append(
            "\t".join(
                [
                    new_code,
                    char,
                    FAMILY_NAME[family],
                    FAMILY_GROUP[family],
                    str(code) if code is not None else "",
                    "".join(flags),
                ]
            )
        )

    header = "code\tcomponent\tfamily\tgroup\tlegacy\tflag"
    with io.open(DST, "w", encoding="utf-8", newline="\n") as f:
        f.write(header + "\n")
        f.write("\n".join(out) + "\n")

    print("components : %d" % len(rows))
    print("written    : %s" % DST)
    for code, name, group in FAMILIES:
        print("  %-2s %-12s %-4s %3d" % (code, name, group, counters.get(code, 0)))


if __name__ == "__main__":
    main()
