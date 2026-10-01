"""
抽象构形数据管理后端 - FastAPI
核心数据结构：每个字符可以有多个 con/ref/comm 标注
"""

import json
from pathlib import Path

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, PlainTextResponse
from pydantic import BaseModel

from . import blocks, entrystore, refs, shape, sheettable

DATA_DIR = Path(__file__).parent / "data"

app = FastAPI(title="抽象构形管理", version="2.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ─── 数据加载 ──────────────────────────────────────────────

_characters: list[dict] = []  # 按 codepoint 排序
_char_map: dict[str, dict] = {}  # char -> entry
_papers: list[dict] = []
_paper_map: dict[str, str] = {}
_ob: list[dict] = []
_extra: list[dict] = []
_cross_refs: dict | None = None  # 交叉索引（懒加载）


def _load_json(name: str) -> dict:
    path = DATA_DIR / name
    if path.exists():
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


def _load_jsonl(name: str) -> list[dict]:
    """逐行读取 jsonl 文件"""
    path = DATA_DIR / name
    if not path.exists():
        return []
    records = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                records.append(json.loads(line))
    return records


def _save_jsonl(name: str, records: list[dict]):
    """将列表写出为 jsonl"""
    path = DATA_DIR / name
    with open(path, "w", encoding="utf-8") as f:
        for r in records:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")


def _build_cross_refs():
    """构建所有数据源的字符交叉索引（懒加载）"""
    idx: dict = {}

    # ── guangyun ──
    gy = _load_json("guangyun.json")

    # 构建 声首 → 声系(series+group) 映射
    ss_map: dict[str, dict] = {}
    for r in gy.get("initial_distribution", {}).get("rows", []):
        for cell_key, cell_val in r.get("cells", {}).items():
            for ch in cell_val.replace(" ", ""):
                if ch not in ss_map:
                    ss_map[ch] = {"series": r["series"], "group": r["group"]}

    # 从 full_table 构建 shengshou → xiesheng_domain 映射
    _xs_map: dict[str, str] = {}
    for r in gy.get("full_table", []):
        ss = r.get("shoushou", "")
        xd = r.get("xiesheng_domain", "")
        if xd and ss and ss not in _xs_map:
            _xs_map[ss] = xd
    # 也搜 special_table
    for r in gy.get("special_table", []):
        ss = r.get("shoushou", "")
        xd = r.get("xiesheng_domain", "")
        if xd and ss and ss not in _xs_map:
            _xs_map[ss] = xd

    gy_idx: dict[str, list[dict]] = {}
    for tbl in ("rhyme_table", "full_table", "special_table"):
        for r in gy.get(tbl, []):
            ss = r.get("shoushou", "")
            # 优先用本行自带的 xiesheng_domain，否则从映射取
            xd = r.get("xiesheng_domain", "") or _xs_map.get(ss, "")
            entry = {
                "table": tbl,
                "type": r.get("type", ""),
                "shengshou": ss,
                "secondary": r.get("secondary", ""),
                "xiesheng_domain": xd,
                "status": r.get("status", ""),
                "qieyu": r.get("qieyu", ""),
                "qiepin": r.get("qiepin", ""),
                "chars_raw": r.get("chars_raw", ""),
                "corrections": r.get("corrections", {}),
                "series": ss_map.get(ss, {}).get("series", ""),
                "group_name": ss_map.get(ss, {}).get("group", ""),
            }
            if r.get("notes_raw"):
                entry["notes_raw"] = r["notes_raw"]
            if r.get("notes"):
                entry["notes"] = r["notes"]
            for ch in r.get("chars", []):
                gy_idx.setdefault(ch, []).append(entry)
    idx["guangyun"] = gy_idx

    # ── shanggu ──
    sg = _load_json("shanggu.json")
    sg_idx: dict[str, dict] = {}
    for r in sg.get("dictionary", []):
        sg_idx[r["char"]] = {
            "reading": r.get("reading", ""),
            "pinyin": r.get("pinyin", ""),
            "xiesheng": r.get("xiesheng", ""),
            "meaning": r.get("meaning", ""),
        }
    idx["shanggu"] = sg_idx

    # ── unify_eiso ──
    ue = _load_json("unify_eiso.json")
    ue_idx: dict[str, list[dict]] = {}
    for key, val in ue.items():
        for ch in key:
            ue_idx.setdefault(ch, []).append({"group": key, "label": val})
    idx["unify_eiso"] = ue_idx

    # ── similar_fei ──
    sf = _load_json("similar_fei.json")
    sf_idx: dict[str, list[dict]] = {}
    for key, val in sf.items():
        for ch in key:
            sf_idx.setdefault(ch, []).append({"group": key, "label": val})
    idx["similar_fei"] = sf_idx

    # ── ies ──
    ies_path = DATA_DIR / "ies20240314.txt"
    ies_dict: dict[str, list[str]] = {}
    if ies_path.exists():
        with open(ies_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or "\t" not in line:
                    continue
                parts = line.split("\t")
                ch = parts[0]
                vals = [v for v in parts[1:] if v]
                if ch and vals:
                    ies_dict[ch] = vals
    idx["ies"] = ies_dict

    # ── ids ──
    ids_path = DATA_DIR / "ids_lv2.txt"
    ids_dict: dict[str, list[str]] = {}
    if ids_path.exists():
        with open(ids_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or "\t" not in line:
                    continue
                parts = line.split("\t")
                ch = parts[0]
                vals = []
                for v in parts[1:]:
                    v = v.strip()
                    if v:
                        # ids 文件中分号分隔多个 IDS
                        for sub in v.split(";"):
                            sub = sub.strip()
                            if sub:
                                vals.append(sub)
                if ch and vals:
                    ids_dict[ch] = vals
    idx["ids"] = ids_dict

    # ── jianhuazi ──
    jh = _load_json("jianhuazi.json")
    jh_idx: dict[str, dict] = {}
    for r in jh.get("jianhuazi", []):
        jh_idx[r["zi"]] = r
    idx["jianhuazi"] = jh_idx

    return idx


def _codepoint_sort_key(entry: dict) -> tuple:
    """按 Unicode 区段排序：基本 → 兼容 → 部首 → 扩展A → 扩展B → …"""
    cp = entry.get("codepoint", "U+0")
    try:
        val = int(cp.replace("U+", ""), 16)
    except (ValueError, AttributeError):
        return (len(blocks.BLOCKS), 0)
    return blocks.sort_key(val)


def _migrate_annotations():
    """将旧的 annotation 迁移为 annotations 数组"""
    global _characters
    changed = False
    for entry in _characters:
        annos = entry.get("annotations")
        if annos is not None:
            continue  # 已经是新格式
        # 尝试从 abstracts 提取
        old_anno = None
        for ab in entry.get("abstracts", []):
            a = ab.get("annotation") or {}
            if a.get("con") or a.get("recon") or a.get("comm"):
                old_anno = a
                break
        if old_anno:
            entry["annotations"] = [
                {
                    "con": old_anno.get("con", ""),
                    "ref": old_anno.get("recon", old_anno.get("ref", "")),
                    "comm": old_anno.get("comm", ""),
                }
            ]
        else:
            entry["annotations"] = []
        entry.pop("abstracts", None)
        changed = True
    if changed:
        _save_characters()
        print("  ✓ 已迁移 annotations 格式")


def load_data():
    global _characters, _char_map, _papers, _paper_map, _ob, _extra

    _characters = _load_jsonl("characters.jsonl")
    # 排序：按 Unicode codepoint
    _characters.sort(key=_codepoint_sort_key)
    _char_map = {entry["char"]: entry for entry in _characters}

    # 迁移标注格式
    _migrate_annotations()

    # 参考文献
    paper_data = _load_json("papers.json")
    _papers = paper_data.get("papers", [])
    _paper_map = {p["id"]: p["citation"] for p in _papers}

    # 其他数据
    _ob = _load_jsonl("ob.jsonl")
    _extra = _load_json("extra.json").get("extra", [])

    print(f"  字符: {len(_characters)}")
    print(f"  参考文献: {len(_papers)}")
    print(f"  甲骨文: {len(_ob)}")
    print(f"  未编码字: {len(_extra)}")

    print(f"  字符: {len(_characters)}")
    print(f"  参考文献: {len(_papers)}")
    print(f"  甲骨文: {len(_ob)}")
    print(f"  未编码字: {len(_extra)}")


@app.on_event("startup")
async def startup():
    load_data()


# ─── Helper ────────────────────────────────────────────────


def _has_annotation(entry: dict) -> bool:
    """检查字符是否有任何标注"""
    annos = entry.get("annotations", [])
    return any(a.get("con") or a.get("ref") or a.get("comm") for a in annos)


# ─── API 路由 ──────────────────────────────────────────────


@app.get("/api/stats")
def get_stats():
    annotated = sum(1 for e in _characters if _has_annotation(e))
    gy_data = _load_json("guangyun.json")
    return {
        "characters": len(_characters),
        "annotated": annotated,
        "unannotated": len(_characters) - annotated,
        "papers": len(_papers),
        "ob": len(_ob),
        "extra": len(_extra),
        "guangyun": len(gy_data.get("rhyme_table", [])),
        "shengsheng": len(gy_data.get("initial_distribution", {}).get("rows", [])),
        "gy_references": len(_load_json("papers_gy.json")),
    }


@app.get("/api/characters/search")
def search_characters(
    q: str = Query("", description="搜索关键词"),
    limit: int = Query(50, description="返回条数上限"),
    offset: int = Query(0, description="偏移量"),
    unannotated: bool = Query(False, description="仅未标注"),
):
    """搜索字符，按 codepoint 排序"""
    results = []
    if q:
        for entry in _characters:
            if q in entry["char"]:
                results.append(entry)
                continue
            for a in entry.get("annotations", []):
                if q in a.get("con", "") or q in a.get("ref", "") or q in a.get("comm", ""):
                    results.append(entry)
                    break
    elif unannotated:
        results = [e for e in _characters if not _has_annotation(e)]
    else:
        results = _characters

    total = len(results)
    page_results = results[offset : offset + limit]
    slim = [
        {
            "char": e["char"],
            "codepoint": e.get("codepoint", ""),
            "annotations": e.get("annotations", []),
        }
        for e in page_results
    ]
    return {"total": total, "offset": offset, "limit": limit, "results": slim}


@app.get("/api/characters/first-unannotated")
def first_unannotated():
    for entry in _characters:
        if not _has_annotation(entry):
            return {"char": entry["char"], "codepoint": entry.get("codepoint", "")}
    return {"char": None, "codepoint": None}


@app.get("/api/characters/{char:path}/neighbors")
def get_neighbors(char: str):
    """返回某字符在全局排序中的上一字和下一字"""
    for i, entry in enumerate(_characters):
        if entry["char"] == char:
            prev_char = _characters[i - 1]["char"] if i > 0 else None
            next_char = _characters[i + 1]["char"] if i < len(_characters) - 1 else None
            return {"prev": prev_char, "next": next_char}
    return {"prev": None, "next": None}


@app.get("/api/characters/{char:path}/cross-refs")
def get_cross_refs(char: str):
    """返回某字符在所有数据源中的交叉信息"""
    global _cross_refs
    if _cross_refs is None:
        _cross_refs = _build_cross_refs()

    result: dict[str, object] = {}

    for src in ("guangyun", "shanggu", "unify_eiso", "similar_fei", "ies", "ids", "jianhuazi"):
        data = _cross_refs.get(src, {})
        if isinstance(data, dict) and char in data:
            result[src] = data[char]

    return result


# ─── 批量编辑：按 IDS 部件搜索 ────────────────────────────


@app.get("/api/characters/search-by-ids-component")
def search_by_ids_component(
    component: str = Query(..., description="IDS 中包含的部件字"),
    limit: int = Query(200, description="返回条数上限"),
    offset: int = Query(0, description="偏移量"),
):
    """搜索所有 IDS 中包含指定部件的字符"""
    global _cross_refs
    if _cross_refs is None:
        _cross_refs = _build_cross_refs()

    ids_data = _cross_refs.get("ids", {})
    matched: list[dict] = []

    for ch, ids_list in ids_data.items():
        for ids_str in ids_list:
            if component in ids_str:
                entry = _char_map.get(ch)
                if entry:
                    matched.append(entry)
                break

    total = len(matched)
    page = matched[offset : offset + limit]
    slim = [
        {
            "char": e["char"],
            "codepoint": e.get("codepoint", ""),
            "annotations": e.get("annotations", []),
            "ids": ids_data.get(e["char"], []),
        }
        for e in page
    ]
    return {"total": total, "offset": offset, "limit": limit, "results": slim}


# ─── 批量保存标注 ──────────────────────────────────────────


class BatchAnnotateItem(BaseModel):
    char: str
    con: str = ""
    ref: str = ""
    comm: str = ""


class BatchAnnotateRequest(BaseModel):
    items: list[BatchAnnotateItem]


@app.post("/api/characters/batch-annotate")
def batch_annotate(data: BatchAnnotateRequest):
    """批量保存标注：对每个字符的抽构（con）进行批量更新"""
    updated = 0
    errors: list[dict] = []
    for item in data.items:
        if item.char not in _char_map:
            errors.append({"char": item.char, "error": "not found"})
            continue
        entry = _char_map[item.char]
        annos = entry.get("annotations", [])
        if annos:
            annos[0]["con"] = item.con
            if item.ref:
                annos[0]["ref"] = item.ref
            if item.comm:
                annos[0]["comm"] = item.comm
        else:
            entry["annotations"] = [{"con": item.con, "ref": item.ref, "comm": item.comm}]
        updated += 1
    if updated:
        _save_characters()
    return {"status": "ok", "updated": updated, "errors": errors}


# ─── 字符详情 ────────────────────────────────────────────


@app.get("/api/characters/{char:path}")
def get_character(char: str):
    if char in _char_map:
        entry = _char_map[char]
        return {
            "char": entry["char"],
            "codepoint": entry.get("codepoint", ""),
            "annotations": entry.get("annotations", []),
        }
    raise HTTPException(status_code=404, detail=f"字符 {char} 未找到")


# ─── 标注 API ─────────────────────────────────────────────


class AnnotationAdd(BaseModel):
    char: str
    con: str = ""
    ref: str = ""
    comm: str = ""


@app.post("/api/characters/annotate")
def add_annotation(data: AnnotationAdd):
    """新增一条 con/ref/comm 标注"""
    char = data.char
    if char not in _char_map:
        raise HTTPException(status_code=404, detail=f"字符 {char} 未找到")
    entry = _char_map[char]
    if "annotations" not in entry:
        entry["annotations"] = []
    entry["annotations"].append({"con": data.con, "ref": data.ref, "comm": data.comm})
    _save_characters()
    return {"status": "ok", "annotations": entry["annotations"]}


class AnnotationDelete(BaseModel):
    char: str
    index: int


@app.post("/api/characters/annotate/delete")
def delete_annotation(data: AnnotationDelete):
    char = data.char
    if char not in _char_map:
        raise HTTPException(status_code=404, detail=f"字符 {char} 未找到")
    entry = _char_map[char]
    annos = entry.get("annotations", [])
    if 0 <= data.index < len(annos):
        del annos[data.index]
        _save_characters()
    return {"status": "ok", "annotations": annos}


class AnnotationEdit(BaseModel):
    char: str
    index: int
    con: str = ""
    ref: str = ""
    comm: str = ""


@app.post("/api/characters/annotate/update")
def update_annotation(data: AnnotationEdit):
    char = data.char
    if char not in _char_map:
        raise HTTPException(status_code=404, detail=f"字符 {char} 未找到")
    entry = _char_map[char]
    annos = entry.get("annotations", [])
    if 0 <= data.index < len(annos):
        if data.con is not None:
            annos[data.index]["con"] = data.con
        if data.ref is not None:
            annos[data.index]["ref"] = data.ref
        if data.comm is not None:
            annos[data.index]["comm"] = data.comm
        _save_characters()
    return {"status": "ok", "annotations": annos}


class ExtraCreate(BaseModel):
    con: str = ""
    ref: str = ""
    comm: str = ""


@app.post("/api/extra")
def create_extra(data: ExtraCreate):
    entry = {"con": data.con, "ref": data.ref, "comm": data.comm}
    _extra.append(entry)
    _save_extra()
    return {"status": "ok", "entry": entry}


def _save_characters():
    _save_jsonl("characters.jsonl", _characters)


def _save_extra():
    path = DATA_DIR / "extra.json"
    with open(path, "w", encoding="utf-8") as f:
        json.dump({"extra": _extra}, f, indent=2, ensure_ascii=False)


# ─── 其他数据 API ─────────────────────────────────────────


@app.get("/api/papers")
def list_papers():
    return {"papers": _papers}


@app.get("/api/papers/search")
def search_papers(q: str = Query("", description="搜索关键词")):
    if not q:
        return {"papers": _papers}
    return {
        "papers": [
            p
            for p in _papers
            if q.lower() in p["id"].lower() or q in p.get("citation", "") or q in p.get("raw_title", "")
        ]
    }


@app.get("/api/ob/search")
def search_ob(q: str = Query(""), limit: int = Query(100), offset: int = Query(0)):
    def ob_match(o):
        if q in str(o.get("glyph", "")) or q in o.get("num", ""):
            return True
        for a in o.get("annotations", []):
            if q in a.get("con", "") or q in a.get("ref", "") or q in a.get("comm", ""):
                return True
        return False

    results = [o for o in _ob if ob_match(o)] if q else _ob
    total = len(results)
    return {"total": total, "results": results[offset : offset + limit]}


class OBAnnotation(BaseModel):
    num: str
    glyph: str = ""
    con: str = ""
    ref: str = ""
    comm: str = ""


class OBAnnotationEdit(BaseModel):
    num: str
    glyph: str = ""
    index: int
    con: str = ""
    ref: str = ""
    comm: str = ""


class OBAnnotationDelete(BaseModel):
    num: str
    glyph: str = ""
    index: int


def _find_ob_entry(num: str) -> dict | None:
    for e in _ob:
        if e.get("num") == num:
            return e
    return None


def _save_ob():
    _save_jsonl("ob.jsonl", _ob)


@app.post("/api/ob/annotate")
def ob_add_annotation(data: OBAnnotation):
    entry = _find_ob_entry(data.num)
    if not entry:
        entry = {"num": data.num, "glyph": data.glyph, "annotations": []}
        _ob.append(entry)
    if "annotations" not in entry:
        entry["annotations"] = []
    entry["annotations"].append({"con": data.con, "ref": data.ref, "comm": data.comm})
    _save_ob()
    return {"status": "ok", "annotations": entry["annotations"]}


@app.post("/api/ob/annotate/update")
def ob_update_annotation(data: OBAnnotationEdit):
    entry = _find_ob_entry(data.num)
    if not entry:
        return {"status": "error", "detail": "not found"}
    annos = entry.get("annotations", [])
    if 0 <= data.index < len(annos):
        if data.con is not None:
            annos[data.index]["con"] = data.con
        if data.ref is not None:
            annos[data.index]["ref"] = data.ref
        if data.comm is not None:
            annos[data.index]["comm"] = data.comm
        _save_ob()
    return {"status": "ok", "annotations": annos}


@app.post("/api/ob/annotate/delete")
def ob_delete_annotation(data: OBAnnotationDelete):
    entry = _find_ob_entry(data.num)
    if not entry:
        return {"status": "error", "detail": "not found"}
    annos = entry.get("annotations", [])
    if 0 <= data.index < len(annos):
        del annos[data.index]
        _save_ob()
    return {"status": "ok", "annotations": annos}


@app.get("/api/extra")
def list_extra():
    return {"extra": _extra}


@app.get("/api/geta")
def list_geta():
    return {"geta": _load_json("geta.json").get("geta", [])}


@app.get("/api/duantian")
def list_duantian():
    return {"duantian": _load_json("duantian.json").get("duantian", [])}


@app.get("/api/shengsheng")
def list_shengsheng():
    """从 guangyun.json 读取上古聲首分布表"""
    g = _load_json("guangyun.json")
    return {"shengsheng": g.get("initial_distribution", {}).get("rows", [])}


@app.get("/api/guangyun")
def list_guangyun():
    """从 guangyun.json 读取《廣韻》小韻諧聲劃分"""
    g = _load_json("guangyun.json")
    return {"guangyun": g.get("rhyme_table", [])}


@app.get("/api/gy/full-table")
def list_gy_full_table():
    """《廣韻》全聲系表"""
    g = _load_json("guangyun.json")
    return {"full_table": g.get("full_table", [])}


@app.get("/api/gy/special")
def list_gy_special():
    """《廣韻》特殊字表"""
    g = _load_json("guangyun.json")
    return {"special_table": g.get("special_table", [])}


@app.get("/api/gy/references")
def list_gy_references():
    """gy 参考文献"""
    g = _load_json("papers_gy.json")
    return {"references": g}


@app.get("/api/jianhuazi")
def list_jianhuazi():
    return {"jianhuazi": _load_json("jianhuazi.json").get("jianhuazi", [])}


@app.get("/api/ids")
def list_ids():
    return {"ids": _load_json("ids.json").get("ids", {})}


# ─── 抽象构形札记（Markdown 文档） ─────────────────────────
#
# 设计：文件即事实来源。每个字符一个目录，主文件 <char>/<char>.md。
# 前端只负责把「标题 + 各行札记」转成结构化 JSON，其余 Markdown 原样回写。


class NoteModel(BaseModel):
    label: str = ""
    con: str = ""
    ref: str = ""
    status: str = ""
    comm: str = ""
    refs: list[str] = []


class EntrySaveRequest(BaseModel):
    seq: int = 0              # 0 = 自动分配下一个条号
    con: str = ""             # 抽构（IDS）
    ref_con: str = ""         # 参考抽构
    notes: str = ""           # 札记正文（Markdown）
    # 引用列表。每项 `{id, pages}`：`id` 是文献编号，`pages` 是本次引用的页码。
    # 也接受旧的纯字符串写法（`"L005"` / `"L005:12-15"`）。
    refs: list[dict | str] = []


class ShapeValidateRequest(BaseModel):
    expr: str = ""


def _doc_char_or_400(char: str) -> str:
    """校验字符。单个字符就是一条记录的主键，不允许空值。"""
    c = (char or "").strip()
    if not c:
        raise HTTPException(status_code=400, detail="字符不能为空")
    if "\n" in c or "\r" in c:
        raise HTTPException(status_code=400, detail="字符不能包含换行")
    return c


#: 抽构表索引（懒加载，构建约 3 秒）
_sheet_index: dict | None = None


def _get_sheet_index() -> dict:
    global _sheet_index
    if _sheet_index is None:
        _sheet_index = sheettable.build_index()
    return _sheet_index


@app.get("/api/sheet/{char:path}")
def get_sheet_entry(char: str):
    """抽构表（input/abstract_*.txt）里该字的原始记录 + 变体 + 上级抽构。"""
    return sheettable.lookup(_doc_char_or_400(char), _get_sheet_index())


@app.get("/api/xiangxing")
def get_xiangxing():
    """象形部件的自然分类码（input/xiangxing.txt）。"""
    return {"xiangxing": sheettable.load_xiangxing()}


@app.get("/api/materials/{char:path}")
def get_materials(char: str):
    """右侧参考资料一次性打包：抽构表 / 广韵 / IES / 词表（上古·词表等）。"""
    ch = _doc_char_or_400(char)

    global _cross_refs
    if _cross_refs is None:
        _cross_refs = _build_cross_refs()

    out: dict = {"char": ch, "sheet": None, "guangyun": [], "ies": [], "lexicon": []}

    # 抽构表
    try:
        out["sheet"] = sheettable.lookup(ch, _get_sheet_index())
    except Exception:
        pass

    # 广韵：谐声划分 + 声系
    gy = _cross_refs.get("guangyun", {})
    if isinstance(gy, dict) and ch in gy:
        rows = gy[ch]
        if isinstance(rows, dict):
            rows = [rows]
        out["guangyun"] = rows

    # IES 中古音
    ies = _cross_refs.get("ies", {})
    if isinstance(ies, dict) and ch in ies:
        v = ies[ch]
        out["ies"] = v if isinstance(v, list) else [v]

    # 词表 / 上古音：shanggu + jianhuazi + 象形分类
    lex: list[dict] = []
    sg = _cross_refs.get("shanggu", {})
    if isinstance(sg, dict) and ch in sg:
        lex.append({"source": "上古音", "data": sg[ch]})
    jh = _cross_refs.get("jianhuazi", {})
    if isinstance(jh, dict) and ch in jh:
        lex.append({"source": "简化字", "data": jh[ch]})
    xx = sheettable.load_xiangxing()
    if ch in xx:
        lex.append({"source": "象形分类", "data": xx[ch]})
    out["lexicon"] = lex

    return out


# ─── 参考文献（BibTeX 式） ─────────────────────────────────


@app.get("/api/refs")
def list_refs(q: str = Query("")):
    """全部文献（自建覆盖内置），带格式化引用文本。"""
    items = refs.list_all(q)
    for r in items:
        r["citation"] = refs.citation(r)
    return {"refs": items, "fields": refs.FIELDS, "types": refs.ENTRY_TYPES,
            "stats": refs.stats()}


@app.get("/api/refs/{rid:path}/bibtex")
def ref_bibtex(rid: str):
    """导出某条文献的 BibTeX。"""
    r = refs.get(rid)
    if not r:
        raise HTTPException(status_code=404, detail=f"文献 {rid} 不存在")
    return PlainTextResponse(refs.to_bibtex(r), media_type="text/plain; charset=utf-8")


@app.get("/api/refs/{rid:path}")
def get_ref(rid: str):
    r = refs.get(rid)
    if not r:
        raise HTTPException(status_code=404, detail=f"文献 {rid} 不存在")
    r = dict(r)
    r["citation"] = refs.citation(r)
    r["bibtex"] = refs.to_bibtex(r)
    r["builtin"] = refs.is_builtin(r["id"])
    return r


@app.post("/api/refs")
def save_ref(data: dict):
    """新增 / 覆盖一条文献。"""
    rec = refs.save(data)
    rec = dict(rec)
    rec["citation"] = refs.citation(rec)
    rec["bibtex"] = refs.to_bibtex(rec)
    rec["builtin"] = False
    return {"status": "ok", "ref": rec}


@app.delete("/api/refs/{rid:path}")
def delete_ref(rid: str):
    ok = refs.delete(rid)
    if not ok:
        raise HTTPException(
            status_code=400,
            detail="只能删除自建文献；内置文献来自上游 papers.json，请勿修改",
        )
    return {"status": "ok"}


@app.get("/api/blocks")
def list_blocks():
    """Unicode 区段清单（前端左侧列表按此顺序排列）。"""
    return {"blocks": blocks.as_list()}


@app.get("/api/all-characters")
def list_all_characters():
    """全部汉字，按区段 + 码位排序；带上每个字已有的条数。"""
    cnt = entrystore.counts()
    out = []
    for entry in _characters:
        ch = entry["char"]
        cp = entry.get("codepoint", "")
        try:
            val = int(cp.replace("U+", ""), 16)
        except ValueError:
            val = 0
        out.append({
            "char": ch,
            "codepoint": cp,
            "block": blocks.classify(val),
            "entries": cnt.get(ch, 0),
        })
    return {"characters": out, "total": len(out)}


@app.post("/api/shape/validate")
def validate_shape(data: ShapeValidateRequest):
    """校验抽构表达式（前端输入框实时调用）。"""
    return shape.validate(data.expr)


@app.get("/api/shape/grammar")
def shape_grammar():
    """抽构运算符表（供前端帮助与语法提示）。"""
    return {
        "operators": [
            {
                "char": op,
                "name": shape.IDC.NAME[op],
                "arity": arity,
            }
            for op, arity in shape.IDC.ARITY.items()
        ]
    }


# ─── 条（entry）API ───────────────────────────────────────
#
# 一条 = 一行 ndjson，键是 (字, 条号)，前端引用写作 `丂-1`。


@app.get("/api/entries/stats")
def entries_stats():
    """整体统计：共几条、覆盖几个字。"""
    return entrystore.stats()


@app.get("/api/entries")
def list_entries(q: str = Query(""), only: str = Query("")):
    """列出条。`q` 搜字符 / 抽构 / 札记；`only=有` 只列有内容的字。"""
    counts_map = entrystore.counts()
    query = (q or "").strip().lower()
    out = []
    for ch in entrystore.characters_with_entries():
        es = entrystore.entries_of(ch)
        if only == "count" and not es:
            continue
        for e in es:
            if query and query not in ch.lower() \
                    and query not in (e["con"] or "").lower() \
                    and query not in (e["ref_con"] or "").lower() \
                    and query not in (e["notes"] or "")[:4000].lower() \
                    and not any(query in entrystore.ref_label(r).lower() for r in e["refs"]):
                continue
            out.append({
                "key": entrystore.entry_key(ch, e["seq"]),
                "char": ch,
                "seq": e["seq"],
                "con": e["con"],
                "ref_con": e["ref_con"],
                "notes": e["notes"],
                "refs": e["refs"],
                "refs_text": entrystore.refs_text(e["refs"]),
                "summary": " ".join((e["notes"] or "").split())[:160],
                "total": counts_map.get(ch, 0),
            })
    return {"entries": out, "count": len(out)}


@app.get("/api/entries/{char:path}/counts")
def entry_counts(char: str):
    """一个字有几条 + 已用条号。"""
    c = _doc_char_or_400(char)
    es = entrystore.entries_of(c)
    return {
        "char": c,
        "count": len(es),
        "seqs": [e["seq"] for e in es],
        "next_seq": entrystore.next_seq(c),
    }


@app.get("/api/entries/{char:path}/neighbors")
def get_doc_neighbors(char: str):
    """全部汉字序列里的上一条 / 下一条（按区段 + 码位）"""
    c = _doc_char_or_400(char)
    for i, entry in enumerate(_characters):
        if entry["char"] == c:
            return {
                "prev": _characters[i - 1]["char"] if i > 0 else None,
                "next": _characters[i + 1]["char"] if i < len(_characters) - 1 else None,
                "index": i,
                "total": len(_characters),
            }
    return {"prev": None, "next": None, "index": -1, "total": len(_characters)}


@app.get("/api/entries/{char:path}")
def get_char_entries(char: str):
    """一个字的全部条 + 码位 / 区段 / 合并预览。"""
    c = _doc_char_or_400(char)
    es = entrystore.entries_of(c)

    entry = _char_map.get(c)
    cp = (entry or {}).get("codepoint", "")
    try:
        val = int(cp.replace("U+", ""), 16)
    except ValueError:
        val = 0

    return {
        "char": c,
        "codepoint": cp,
        "block": blocks.name_of(blocks.classify(val)) if cp else "",
        "entries": es,
        "count": len(es),
        "next_seq": entrystore.next_seq(c),
        "preview": entrystore.render_character(c),
    }


@app.post("/api/entries/{char:path}")
def save_entry(char: str, data: EntrySaveRequest):
    """新增 / 覆盖一条。`seq` 为 0 时自动分配下一个条号。"""
    c = _doc_char_or_400(char)
    check = entrystore.validate_entry(data.con, data.ref_con)
    if not check["con"].get("ok"):
        err = check["con"].get("error") or {}
        raise HTTPException(
            status_code=400,
            detail=f"抽构格式错误：{err.get('message', '')}",
        )
    if not check["ref_con"].get("ok"):
        err = check["ref_con"].get("error") or {}
        raise HTTPException(
            status_code=400,
            detail=f"参考抽构格式错误：{err.get('message', '')}",
        )
    # 旧引用里填过的页码，本次没传就保留（避免前端只传 id 时抹掉页码）
    old = entrystore.get_entry(c, data.seq) if data.seq else None
    refs = data.refs
    if old:
        refs = entrystore.merge_legacy_refs(old.get("refs"), refs)

    rec = entrystore.write_entry(
        c, data.seq, con=data.con, ref_con=data.ref_con,
        notes=data.notes, refs=refs,
    )
    return {
        "status": "ok",
        "entry": rec,
        "key": entrystore.entry_key(c, rec["seq"]),
        "preview": entrystore.render_character(c),
        "count": entrystore.count_entries(c),
        "shape": check,
    }


# 注意：更具体的路径必须声明在 `/api/entries/{char:path}` 之前，
# 否则 {char:path}（path 转换器含 `/`）会把 `一/1` 整个吃掉，当成一个字叫「一/1」，
# 于是单条删除静默返回 {"deleted": 0}，界面删了、切走再回来又出现。


@app.delete("/api/entries/{char}/seq/{seq}")
def delete_one_entry(char: str, seq: int):
    """删掉单独一条。

    路径用 `seq/` 前缀而不是 `/{char:path}/{seq}`：后者会和上面的
    `/api/entries/{char:path}` 抢，导致永远匹配不到。
    """
    c = _doc_char_or_400(char)
    return {"status": "ok", "deleted": entrystore.delete_entry(c, seq)}


@app.delete("/api/entries/{char:path}")
def delete_char_entries(char: str):
    """删掉这个字的全部条。"""
    c = _doc_char_or_400(char)
    return {"status": "ok", "deleted": entrystore.delete_character(c)}


@app.post("/api/entries/render")
def render_entries(data: dict):
    """不落盘，直接预览一组条（前端实时用）。"""
    char = _doc_char_or_400(str(data.get("char") or ""))
    entries = data.get("entries") or []
    tmp: list[str] = []
    lines = [f"# {char}", ""]
    for i, e in enumerate(entries, start=1):
        seq = e.get("seq") or i
        lines.append(entrystore.entry_key(char, int(seq)))
        lines.append("")
        if e.get("con"):
            lines.append(f"- 抽构：`{e['con']}`")
        if e.get("ref_con"):
            lines.append(f"- 参考抽构：`{e['ref_con']}`")
        if e.get("con") or e.get("ref_con"):
            lines.append("")
        notes = (e.get("notes") or "").strip()
        if notes:
            lines.append(notes)
            lines.append("")
        refs = e.get("refs") or []
        if refs:
            lines.append("文献：" + entrystore.refs_text(refs))
            lines.append("")
    tmp.append("\n".join(lines).replace("\n\n\n", "\n\n").rstrip() + "\n")
    return {"preview": tmp[0]}


# ─── 静态文件服务 ──────────────────────────────────────────

FRONTEND_DIR = Path(__file__).parent.parent / "frontend"


@app.get("/")
def serve_index():
    return FileResponse(FRONTEND_DIR / "index.html")


@app.get("/{path:path}")
def serve_static(path: str):
    file_path = FRONTEND_DIR / path
    if file_path.exists() and file_path.is_file():
        return FileResponse(file_path)
    return FileResponse(FRONTEND_DIR / "index.html")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=8000)
