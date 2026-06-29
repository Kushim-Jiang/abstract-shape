"""
抽象构形数据管理后端 - FastAPI
核心数据结构：每个字符可以有多个 con/ref/comm 标注
"""

import json
from pathlib import Path

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel

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
    """按 Unicode 区块排序：URO → 兼容 → ExtA → ExtB → ..."""
    cp = entry.get("codepoint", "U+0")
    try:
        val = int(cp.replace("U+", ""), 16)
    except (ValueError, AttributeError):
        return (99, 0)

    # 定义区块优先级
    if 0x4E00 <= val <= 0x9FFF:
        block = 0  # URO
    elif 0xF900 <= val <= 0xFAFF:
        block = 1  # 兼容（CJK Compatibility）
    elif 0xFA00 <= val <= 0xFAFF:
        block = 1
    elif 0x3400 <= val <= 0x4DBF:
        block = 2  # ExtA
    elif 0x20000 <= val <= 0x2A6DF:
        block = 3  # ExtB
    elif 0x2A700 <= val <= 0x2B73F:
        block = 4  # ExtC
    elif 0x2B740 <= val <= 0x2B81F:
        block = 5  # ExtD
    elif 0x2B820 <= val <= 0x2CEAF:
        block = 6  # ExtE
    elif 0x2CEB0 <= val <= 0x2EBEF:
        block = 7  # ExtF
    elif 0x30000 <= val <= 0x3134F:
        block = 8  # ExtG
    elif 0x31350 <= val <= 0x323AF:
        block = 9  # ExtH
    elif 0x2EBF0 <= val <= 0x2EE5F:
        block = 10  # ExtI
    else:
        block = 99  # 其他

    return (block, val)


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
