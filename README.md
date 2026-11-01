# Abstract-Shape

## Introduction

This repository stores analyses of _abstract shapes_ for [CJKV Unified Ideographs](https://en.wikipedia.org/wiki/CJK_Unified_Ideographs).

The purpose of analyzing abstract shapes is to establish the graphic specification of each character. This is accomplished by analyzing the classes to which the components it contains belong and describing the structure formed by the components.

The graphic specification of components has two sources. The first source is diachronic graphic evolution, which is supported by the systematic changes in Han ideographs. It can be noted that many changes at the writing system level still keep the internal structure of the characters. The second source is language, i.e., the characters containing the component are in the same harmonic scope.

We use prefix expressions composed of components to describe the abstract shape of a character. Each component is either shaped like `[A]` or shaped like `[A(B)]`. The operator is IDC, but define them more abstractly, for example, a character containing three identical components, regardless of how the three components are arranged, we always use `⿲`.

The visualization of this repository is implemented in [another repository](https://github.com/Kushim-Jiang/kushim-jiang.github.io), and [here is the link](https://kushim-jiang.github.io/tools/abstract-shape/).

## Contribute

- Asking

  - Create an [issue](https://github.com/Kushim-Jiang/abstract-shape/issues).
  - Create an [issue](https://github.com/Kushim-Jiang/kushim-jiang.github.io/issues).
  - [Email me.](https://kushim-jiang.github.io/pages/contact/)

- Updating

  1. Clone this repo as the `RepoA`.
  2. Edit the [`RepoA > abstract_shape.xlsx`](input/abstract_shape.xlsx).
  3. Install the required packages in the [`RepoA > requirements.txt`](requirements.txt).
  4. Run Python file [`RepoA > build_txt.py`](src/build_txt.py) to update all the text files.
  5. Pull your request.

- Previewing

  1. Clone [`Kushim-Jiang > kushim-jiang.github.io`](https://github.com/kushim-Jiang/kushim-jiang.github.io) in the same root as the `RepoB`.
  2. Run Python file [`RepoA > build_json.py`](src/build_json.py) to update the JSON file in [`RepoB > assets > abstract.json`](https://github.com/Kushim-Jiang/kushim-jiang.github.io/blob/main/assets/abstract.json).
  3. Run `jekyll s` in the `RepoB` to preview your changes.
## Web editor

A local editing UI for the abstract-shape corpus. Everything lives in one
ndjson file, so the whole corpus is a single file and `git diff` stays readable.

```
./start.bat                    # picks a free port and opens the server
```

`start.bat` first kills any previous instance still listening on
ports 8000–8100, then reuses the lowest free port.

Open **写作**. Three columns, all three widths draggable (double-click a divider
to reset):

| Column | Contents |
| --- | --- |
| left | the full character list (97712), grouped by Unicode block, paginated 100/page; each row shows how many notes that character has, and the block chips carry a red count of 核验 problems (`基本 3`) |
| middle | the note editor: 抽构 / 参考抽构 / 甲骨文 / 小篆 / 札记, with an 编辑·预览 toggle |
| right | 文献 (BibTeX-style reference editor), 资料 (抽构表 / 广韵 / IES / 词表, read-only) and 核验 (what is wrong with the current character) |

Keyboard: `Ctrl+S` save, `Ctrl+E` toggle edit/preview, `Ctrl+↑` `Ctrl+↓` previous
/ next character, `Ctrl+G` jump to a character.

The `▶ 未写` button jumps to the first character in the current filter that has
no notes yet.

### 甲骨文 / 金文 字形标注

The 甲骨文 and 金文 views list the glyphs themselves (`backend/data/ob.jsonl`,
`bi.jsonl`). Under each glyph, the 汉字字形 it stands for are shown as chips:

* `＋` opens a one-line input — type the character and press Enter; spaces, `,`、
  `、` or `;` split several characters into several chips at once; `Esc` cancels;
* `×` deletes that chip;
* the toolbar search matches 编号 and the annotated characters too.

Each chip is one entry of `annotations` (`con`), so existing records keep working:

```json
{"num": "0002", "glyph": "󰀁",
 "annotations": [{"con": "匕(妣)", "ref": "", "comm": ""}, {"con": "匕(比)", "ref": "", "comm": ""}]}
```

`num` is unique in both files, so a record is located by `num`; the endpoints are
`POST /api/ob/annotate`, `/api/ob/annotate/delete` and the same pair for
`/api/bi/…`. 甲骨文 numbers are the corpus's running numbers; 金文 numbers follow
the source book — see below.

### Shape input formatting

抽构 / 参考抽构 are formatted as you type:

* full-width `（）［］` become half-width, spaces are dropped;
* once the expression parses, the canonical form is written back with every
  component in brackets — `⿰木木` → `⿰[木][木]`, `⿱九乙（ᄅ）` → `⿱[九][乙(ᄅ)]`,
  `=下` → `=[下]` (the `= ~ * ?` prefix is kept);
* the parser accepts the tolerant spellings (`⿱九乙`, `[⿱九乙]`, `[乙](ᄅ)`), so
  the formatted text always parses again;
* the caret keeps its place measured in "meaningful" characters, and IME
  composition is never touched mid-word.

Characters that cannot be a component (`, . : ; !` ASCII punctuation, digits,
full-width punctuation) raise `非法字符` instead of being silently accepted.

### Verification (核验)

`backend/verify.py` checks every note and the right column's 核验 tab lists what
it finds for the current character; the left block chips show the whole-corpus
count per Unicode block, and the toolbar shows the current character's count.
Fields with problems are outlined in red.

| Code | Level | Rule |
| --- | --- | --- |
| `bad-char` | error | a component is punctuation / a digit |
| `arity` | error | an IDC operator has the wrong number of operands |
| `bracket` / `extra` | error | brackets do not pair, or there is trailing junk |
| `missing-unit` | warning | a component `[下]` has no record of its own whose 抽构 is `[下]` |
| `dup-unit` | error | two or more records use the same shape as their 抽构 — `[下]`, `⿰[虫][下]`, `[與]=⿶[舁][牙]` (head included), anything; only one may own it, the rest must be `=…` |
| `no-ref` | error | a cited reference id does not exist |
| `page-range` | error | a cited page falls outside the reference's own `pages` |

Reference pages use the same notation as the inline citations: `224-225+226-227`
(`-` = range, `+` = separate spans). The 文献 form converts `— — 、` etc. on
input and the backend re-normalizes on save, so both sides always compare
apples to apples; a citation is accepted only if each of its spans fits inside
one registered span.

Reference **keys** are checked globally too: the same key written twice in
`references.ndjson`, or a custom record re-using a built-in key, shows up as
「引用键重复」 in the 文献 tab and at the bottom of 核验. Citing the same
reference several times inside one note is fine.

### Data model

One **note** is one line of
[`abstract-shape/abstract-shape.ndjson`](abstract-shape/abstract-shape.ndjson),
keyed by `(character, seq)`:

```json
{"char": "丂", "seq": 1, "con": "⿱一丂", "ref_con": "*考",
 "notes": "…… [ref:C001.244-245+248]"}
```

| Field | Meaning |
| --- | --- |
| `char` | the character |
| `seq` | note number within that character, from 1; referenced as `丂-1` |
| `con` | the abstract shape — an IDS expression, validated by `backend/shape.py` |
| `ref_con` | a comparative shape; `=字` / `*字` are annotation conventions and skip IDS validation |
| `ob` | oracle-bone forms attached to this note — `num`s from `backend/data/ob.jsonl`, e.g. `["0200"]` |
| `bi` | bronze-inscription forms — `num`s from `backend/data/bi.jsonl`, e.g. `["01001", "01001A"]` |
| `xz` | small-seal forms attached to this note — `num`s from `backend/data/seal.ndjson`, e.g. `["01998"]` |
| `notes` | the note body, free Markdown; citations are written inline (see below) |

`ob` / `bi` / `xz` are picked in the editor (甲骨文 / 金文 / 小篆 rows, multi-select;
candidates come from `/api/glyphs/ob`, `/api/glyphs/bi` and `/api/glyphs/seal`).

**`num` is the key.** A number in `ob.jsonl` / `bi.jsonl` covers several glyphs, so
`backend/scripts/renumber_glyphs.py` gave every repeat a letter suffix in file order
(`0001`, `0001A`, `0001B`, …); `seal.ndjson` is 1–11108 and never collides. All
three tables are keyed by a unique `num`.

The glyphs live in the private use area (fonts `ZihuiSongJGW.ttf`,
`ZihuiSongJW.otf`, `frontend/sw-ccz-1963-rev1.ttf`). Only the seal codepoint can
be computed — `0xF0000 + num - 1` — because its `num` is still the font index;
the oracle-bone / bronze ids cannot, so the frontend fetches the whole
`num → glyph` table once from `/api/glyphs/index`. `seal.ndjson` carries
`{num, glyph, char}` (11108 forms, `char` = the table's `zi_strict` when it has
one, otherwise `zi`). In Markdown the forms are written `[ob:0001,0200]`,
`[bi:01001A]` and `[seal:01998]`.

### 金文 number = 卷 × 1000 + 卷内号

The bronze corpus is numbered per volume, each volume restarting at `001`, so a
number is `[卷][三位卷内号]` written as five digits: `01001` (卷1 号1) … `01193`,
`02001` (卷2 号1) … `02452`, … `14350` (卷14).

`bi.jsonl` was stored with a flat 1–4419 running number, which lost the volume
breaks. `backend/data/bi_volumes.json` records how many numbers each volume has
and which numbers the book skips:

```json
{"volumes": [193, 452, 466, 265, 325, 371, 442, 283, 243, 303, 192, 338, 197, 351],
 "holes": ["07086"]}
```

and `backend/scripts/number_bi_volumes.py` walks the file in order, assigning
`卷 × 1000 + 卷内号` and skipping the holes (`07085` is followed by `07087`). When
several glyphs share one number they keep an `A`/`B`/… suffix (`01001`, `01001A`,
`01001B`). The table then yields 4420 numbers while the file holds 4419, so 卷14
ends at `14350` — one number of the book has no bronze forms in this corpus.

### Citations

Citations are part of the note body — there is no separate reference list per note:

| Syntax | Meaning |
| --- | --- |
| `[ref:C001]` | the reference, no particular page |
| `[ref:C001.244-245+248]` | C001, pp. 244–245 and 248 |
| `[ref:C001.12+15-16]` | C001, p. 12 and pp. 15–16 |

`-` separates the ends of a range, `+` joins separate spans; `,` `、` `;` `~` `—`
are normalized to those two when the note is saved. Page numbers here are
**the pages cited by this note**, distinct from the reference's own page range
(`refs.pages`): a book may span 100–300 while a particular note cites only
120–135. In the preview each citation becomes a chip that opens the reference
in the 文献 panel.

The API still returns `refs` on every note
(`[{"id": "C001", "pages": "244-245+248"}]`), but it is parsed from `notes` on
save and load — the file has no `refs` field unless an older file already did.

### Abstract-shape syntax

A shape is either a single component or an IDC operator followed by its
operands:

```
<shape> ::= [<char>=] <expr>
<expr>  ::= <char> | <op> <expr> <expr> | <op> <expr> <expr> <expr>
<char>  ::= 汉字 | 汉字(变体)
```

The optional `[與]=` head spells out which character is being decomposed, so
`[與]=⿶[舁][牙]` reads「與 分解为 ⿶舁牙」. The head is not a component: it does
not count as a leaf, it is kept (in brackets) by the formatter, and 核验 treats
`[與]=…` and `…` as two different definitions — the same head + body written
twice is still a `dup-unit`.

17 operators are supported (`backend/shape.py` → `IDC.ARITY`):

| | | | |
| --- | --- | --- | --- |
| `⿰` 左右 | `⿱` 上下 | `⿲` 左中右 | `⿳` 上中下 |
| `⿸` 左上包围 | `⿺` 左下包围 | `⿹` 右上包围 | `⿽` 右下包围 |
| `⿵` 上三包围 | `⿷` 左三包围 | `⿶` 下三包围 | `⿼` 右三包围 |
| `⿴` 全包围 | `⿻` 重叠 | `⿾` 镜像 | `⿿` 旋转 |
| `〾` 近似形 | | | |

The editor validates as you type and reports the exact position of a mistake:

```
⿰日       ✕ 「⿰」（左右）需要 2 个部件，只给了 1 个   第 3 字符
⿱一去     ✓ 2 个部件，深 1    ⿱[一][去]
⿰木(木)木  ✓ 2 个部件，深 1    ⚠ 重复部件 木，确认是否应该用 ⿰/⿱ 之外的运算符
```

### References

`backend/refs.py` keeps BibTeX-shaped records (18 fields: author, editor, title,
journal, booktitle, publisher, address, year, date, volume, number, pages,
edition, url, doi, note). Two sources, merged by `id`:

- `backend/data/papers.json` — 95 upstream records, **read-only**; saving one
  writes an override instead of touching the upstream file;
- `abstract-shape/references.ndjson` — locally added / edited records (`R001`…).

The citation line is built from the fields, and `date` wins over `year`. `date`
takes the month/day shorthand, so `3` = 3月 and `3.12` = 3月12日 with the year
coming from `year`; a full `2007-05-01` (or `2007/5/1`, `2007.5.1`,
`2007年5月1日`) carries its own year. Everything is stored as `2007-05-01`,
`2007-05`, `03-12` or `03`, and printed as `2007年5月1日` / `2007年3月12日`; with
no date at all the citation keeps the plain `2007年`.

### Character ordering

The list follows the conventional block order, defined once in
`backend/blocks.py` and served via `/api/blocks`:

基本 → 兼容 → 部首 → 扩展A → 扩展B → 兼容扩展 → 扩展C → 扩展D → 扩展E → 扩展F → 扩展G → 扩展H → 扩展I → 扩展J → 其他

扩展I sits at the end even though its code points precede 扩展G/H — letter order
wins over code-point order. 扩展J (U+323B0–U+3347F, Unicode 17.0) follows 扩展H.

### Markdown extension

| Syntax | Meaning |
| --- | --- |
| `[[丂-1]]` | cross-reference to note 丂-1 (clickable) |
| `[[文献: L005]]` | reference link rendered as `[L005]` |
| `[ob:0001,0200]` | oracle-bone glyphs (numbers from `ob.jsonl`) |
| `[bi:01001A]` | bronze-inscription glyphs (`num` from `bi.jsonl`) |
| `[seal:01998]` | small-seal glyphs (`num` from `seal.ndjson`) |

The older `[[卜:…]]` / `[[金:…]]` / `[[篆:…]]` spellings still render.

### Migrating old data

`backend/scripts/migrate_to_entries.py` converts the earlier single-record
format (`{char, con, analysis, references}`) into the note model above. It backs
the file up before writing.

## Contribute

- Asking

  - Create an [issue](https://github.com/Kushim-Jiang/abstract-shape/issues).
  - Create an [issue](https://github.com/Kushim-Jiang/kushim-jiang.github.io/issues).
  - [Email me.](https://kushim-jiang.github.io/pages/contact/)

- Updating

  1. Clone this repo as the `RepoA`.
  2. Edit the shape sheet, [`RepoA > input/abstract_main.txt`](input/abstract_main.txt) (and the other `input/abstract_*.txt` volumes).
  3. Install the required packages in the [`RepoA > requirements.txt`](requirements.txt).
  4. Run Python file [`RepoA > src/build_txt.py`](src/build_txt.py) to update all the text files.
  5. Pull your request.

- Previewing

  1. Clone [`Kushim-Jiang > kushim-jiang.github.io`](https://github.com/Kushim-Jiang/kushim-jiang.github.io) in the same root as the `RepoB`.
  2. Run Python file [`RepoA > src/build_json.py`](src/build_json.py) to update the JSON file in [`RepoB > assets > abstract.json`](https://github.com/Kushim-Jiang/kushim-jiang.github.io/blob/main/assets/abstract.json).
  3. Run `jekyll s` in the `RepoB` to preview your changes.
