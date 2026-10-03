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
| left | the full character list (97712), grouped by Unicode block, paginated 100/page; each row shows how many notes that character has |
| middle | the note editor: 抽构 / 参考抽构 / 札记 / 参考文献, with an 编辑·预览 toggle |
| right | 文献 (BibTeX-style reference editor) and 资料 (抽构表 / 广韵 / IES / 词表, read-only) |

Keyboard: `Ctrl+S` save, `Ctrl+E` toggle edit/preview, `Ctrl+↑` `Ctrl+↓` previous
/ next character, `Ctrl+G` jump to a character.

The `▶ 未写` button jumps to the first character in the current filter that has
no notes yet.

### Data model

One **note** is one line of
[`abstract-shape/abstract-shape.ndjson`](abstract-shape/abstract-shape.ndjson),
keyed by `(character, seq)`:

```json
{"char": "丂", "seq": 1, "con": "⿱一丂", "ref_con": "*考",
 "notes": "……", "refs": [{"id": "L005", "pages": "12—15"}]}
```

| Field | Meaning |
| --- | --- |
| `char` | the character |
| `seq` | note number within that character, from 1; referenced as `丂-1` |
| `con` | the abstract shape — an IDS expression, validated by `backend/shape.py` |
| `ref_con` | a comparative shape; `=字` / `*字` are annotation conventions and skip IDS validation |
| `notes` | the note body, free Markdown |
| `refs` | citations; `id` is the reference key, `pages` is **the range cited here** |

A character can have any number of notes. `pages` on a citation is distinct from
the reference's own page range (`refs.pages`): a book may span 100–300 while a
particular note cites only 120–135.

Plain-string citations (`"L005"`, `"L005:12-15"`) are still accepted and are
upgraded on load, so older files keep working.

### Abstract-shape syntax

A shape is either a single component or an IDC operator followed by its
operands:

```
<expr> ::= <char> | <op> <expr> <expr> | <op> <expr> <expr> <expr>
<char> ::= 汉字 | 汉字(变体)
```

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

- `backend/data/papers.json` — 97 upstream records, **read-only**; saving one
  writes an override instead of touching the upstream file;
- `abstract-shape/references.ndjson` — locally added / edited records (`R001`…).

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
