/**
 * 抽构视图（abstract shape + 分析）
 *
 * 左栏：全部汉字的列表，按 Unicode 区段分组（基本 / 兼容 / 部首 / 扩展A / ...）
 * 右栏：抽构输入（实时语法校验）+ 分析正文（Markdown）+ 文献
 *
 * 一条记录就是一个字：con（抽构）+ analysis（分析）+ references（文献）。
 * 保存后写进 abstract-shape/abstract-shape.ndjson 里该字那一行。
 */

// ─── 状态 ────────────────────────────────────────────────
const WR = {
  chars: [],          // 当前列表（全部字，或搜索结果）
  blocks: [],         // 区段定义
  blockFilter: "__all__",
  current: null,
  doc: null,
  materials: null,    // 右侧参考资料 + 左侧只读材料（抽构表/广韵/IES/词表）
  pane: "edit",       // 左框当前显示：edit | preview
  dirty: false,
  neighborInfo: { prev: null, next: null, index: -1, total: 0 },
  initialized: false,
  page: 1,            // 左侧列表当前页
  perPage: 100,       // 每页多少个字
};

function $(id) { return document.getElementById(id); }

function setSaveState(text, cls) {
  const el = $("doc-save-state");
  if (!el) return;
  el.textContent = text || "";
  el.className = "save-state" + (cls ? " " + cls : "");
}

function markDirty(on) {
  WR.dirty = !!on;
  const dot = $("doc-dirty");
  if (dot) dot.style.display = WR.dirty ? "" : "none";
}

// ─── API ─────────────────────────────────────────────────

async function wrGet(path) {
  const r = await fetch("/api" + path);
  if (!r.ok) throw new Error("API " + r.status);
  return r.json();
}

async function wrSend(path, body, method) {
  const r = await fetch("/api" + path, {
    method: method || "POST",
    headers: { "Content-Type": "application/json" },
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  if (!r.ok) {
    let detail = "API " + r.status;
    try { detail = (await r.json()).detail || detail; } catch (e) {}
    throw new Error(detail);
  }
  return r.json();
}

// ─── 列表 ────────────────────────────────────────────────

async function loadBlocks() {
  if (WR.blocks.length) return;
  const d = await wrGet("/blocks");
  WR.blocks = d.blocks || [];
  renderBlockChips();
}

function renderBlockChips() {
  const box = $("block-chips");
  if (!box) return;
  box.innerHTML = WR.blocks.map(function (b) {
    return '<button class="blk-chip" data-block="' + b.key + '">' + MD.esc(b.name) + "</button>";
  }).join("");

  // 顶部「全部 / ✓ 已写」与下方区段共用同一套点击逻辑
  // （「▶ 未写」是动作按钮，不是筛选，单独处理，这里排除掉）
  document.querySelectorAll(".block-filter .blk-chip[data-block]").forEach(function (el) {
    el.addEventListener("click", function () {
      WR.blockFilter = el.getAttribute("data-block");
      document.querySelectorAll(".block-filter .blk-chip[data-block]").forEach(function (c) {
        c.classList.remove("active");
      });
      el.classList.add("active");
      // 切区段时清掉搜索词，否则会看到「区段里只有搜索结果」
      if ($("doc-search").value) $("doc-search").value = "";
      WR.page = 1;
      loadCharList(true);
    });
  });
}

/** 取字列表：搜索走接口，否则本地按区段过滤 */
async function loadCharList(reset) {
  WR.page = 1;
  const q = $("doc-search").value.trim();
  if (q) {
    const d = await wrGet("/characters/search?q=" + encodeURIComponent(q) + "&limit=500");
    WR.chars = (d.results || []).map(function (c) {
      return { char: c.char, codepoint: c.codepoint, annotated: !!(c.annotations && c.annotations.length) };
    });
  } else {
    // 全量字列表由后端按区段排好序，前端只做过滤
    if (!WR.allChars) {
      const d = await wrGet("/all-characters");
      WR.allChars = d.characters || [];
    }
    if (WR.blockFilter === "__all__") {
      WR.chars = WR.allChars;
    } else if (WR.blockFilter === "__done__") {
      WR.chars = WR.allChars.filter(function (c) { return (c.entries || 0) > 0; });
    } else {
      WR.chars = WR.allChars.filter(function (c) { return c.block === WR.blockFilter; });
    }
  }
  renderCharList();
  if (reset && WR.chars.length && !WR.current) openDoc(WR.chars[0].char);
}
function renderCharList() {
  const box = $("doc-list");
  const total = WR.chars.length;
  const per = WR.perPage;
  const pages = Math.max(1, Math.ceil(total / per));
  if (WR.page > pages) WR.page = pages;
  if (WR.page < 1) WR.page = 1;
  const start = (WR.page - 1) * per;
  const shown = WR.chars.slice(start, start + per);

  const withEntries = WR.chars.filter(function (c) { return (c.entries || 0) > 0; }).length;
  const totalEntries = WR.chars.reduce(function (n, c) { return n + (c.entries || 0); }, 0);

  $("doc-count").textContent = withEntries
    ? withEntries + " 字 · " + totalEntries + " 条"
    : total + " 字";

  if (!shown.length) {
    box.innerHTML = '<div class="empty" style="padding:24px 12px;font-size:13px">没有字</div>';
    $("doc-pager").innerHTML = "";
    return;
  }
  box.innerHTML = shown.map(function (c) {
    const n = c.entries || 0;
    return '<div class="doc-item' + (c.char === WR.current ? " active" : "") +
      '" data-char="' + MD.esc(c.char) + '">' +
      '<span class="di-char">' + c.char + "</span>" +
      '<span class="di-cp">' + MD.esc((c.codepoint || "").replace("U+", "")) + "</span>" +
      (n ? '<span class="di-n">' + n + "</span>" : "") +
      "</div>";
  }).join("");

  renderPager(pages, total, start, shown.length);

  box.querySelectorAll(".doc-item").forEach(function (el) {
    el.addEventListener("click", function () {
      const c = el.getAttribute("data-char");
      if (c !== WR.current) confirmLeave(function () { openDoc(c); });
    });
  });
}

/** 底部分页条 */
function renderPager(pages, total, start, shownCount) {
  const el = $("doc-pager");
  if (!el) return;
  if (pages <= 1) {
    el.innerHTML = '<span class="pg-info">共 ' + total + " 字</span>";
    return;
  }

  const p = WR.page;
  // 页码窗口：首页、末页、当前页 ±2
  const nums = [];
  for (let i = 1; i <= pages; i++) {
    if (i === 1 || i === pages || Math.abs(i - p) <= 2) nums.push(i);
  }

  let html = '<button class="pg-btn" data-pg="1"' + (p === 1 ? " disabled" : "") +
    ' title="第一页">«</button>' +
    '<button class="pg-btn" data-pg="' + (p - 1) + '"' + (p === 1 ? " disabled" : "") +
    ' title="上一页">‹</button>';

  let prev = 0;
  nums.forEach(function (n) {
    if (prev && n - prev > 1) html += '<span class="pg-gap">…</span>';
    html += '<button class="pg-btn' + (n === p ? " active" : "") +
      '" data-pg="' + n + '">' + n + "</button>";
    prev = n;
  });

  html += '<button class="pg-btn" data-pg="' + (p + 1) + '"' + (p === pages ? " disabled" : "") +
    ' title="下一页">›</button>' +
    '<button class="pg-btn" data-pg="' + pages + '"' + (p === pages ? " disabled" : "") +
    ' title="最后一页">»</button>' +
    '<span class="pg-info">' + (start + 1) + "–" + (start + shownCount) + " / " + total + "</span>";

  el.innerHTML = html;
  el.querySelectorAll(".pg-btn").forEach(function (b) {
    b.addEventListener("click", function () {
      const n = parseInt(b.getAttribute("data-pg"), 10);
      if (!n || n < 1 || n > pages || n === WR.page) return;
      goPage(n);
    });
  });
}

function goPage(n) {
  WR.page = n;
  renderCharList();
  const list = $("doc-list");
  if (list) list.scrollTop = 0;
}

/** 跳到「当前列表里第一个还没写的字」 */
function jumpFirstBlank() {
  // 当前列表是搜索结果时先清掉搜索，回到区段/全量的顺序上
  if ($("doc-search").value.trim()) {
    $("doc-search").value = "";
    loadCharList(false);
  }
  const idx = WR.chars.findIndex(function (c) { return !(c.entries || 0); });
  if (idx < 0) {
    setSaveState("都写完了", "ok");
    setTimeout(function () { setSaveState(""); }, 1600);
    return;
  }
  const ch = WR.chars[idx].char;
  confirmLeave(function () {
    WR.page = Math.floor(idx / WR.perPage) + 1;
    renderCharList();
    openDoc(ch);
  });
}

// ─── 三栏拖拽调宽 ────────────────────────────────────────
//
//   [左：字表] │split-left│ [中：编辑/预览] │split-right│ [右：资料]
//
// 拖 split-left  → 改左侧宽度（中/右跟着让）
// 拖 split-right → 改右侧宽度（中跟着让）

const COL_MIN = 140;

/** 从 localStorage 恢复宽度 */
function restoreColWidths() {
  try {
    const w = JSON.parse(localStorage.getItem("wr-col-widths") || "{}");
    const L = $("pane-left"), R = $("pane-right");
    if (w.left && L) L.style.width = w.left + "px";
    if (w.right && R) R.style.width = w.right + "px";
  } catch (e) { /* 忽略坏数据 */ }
}

function saveColWidths() {
  const L = $("pane-left"), R = $("pane-right");
  try {
    localStorage.setItem("wr-col-widths", JSON.stringify({
      left: L ? Math.round(L.getBoundingClientRect().width) : 0,
      right: R ? Math.round(R.getBoundingClientRect().width) : 0,
    }));
  } catch (e) { /* 忽略 */ }
}

/** 把一个分隔条绑到目标列上。dir=1 右拖变宽，dir=-1 右拖变窄 */
function bindColSplitter(splitId, paneId, dir) {
  const bar = $(splitId);
  const pane = $(paneId);
  if (!bar || !pane) return;

  bar.addEventListener("mousedown", function (ev) {
    ev.preventDefault();
    const startX = ev.clientX;
    const startW = pane.getBoundingClientRect().width;
    const isLeft = (paneId === "pane-left");
    const other = $(isLeft ? "pane-right" : "pane-left");
    const host = isLeft ? $("view-write") : $("doc-panes");
    const hostW = (host || document.body).getBoundingClientRect().width;
    const otherW = other ? other.getBoundingClientRect().width : 0;
    // 目标列上限：留出另一侧最小值 + 分隔条
    const maxW = Math.max(COL_MIN, hostW - otherW - COL_MIN - 10);

    bar.classList.add("dragging");
    document.body.classList.add("col-resizing");

    function onMove(e) {
      const delta = (e.clientX - startX) * dir;
      const w = Math.max(COL_MIN, Math.min(maxW, startW + delta));
      pane.style.width = Math.round(w) + "px";
    }
    function onUp() {
      document.removeEventListener("mousemove", onMove);
      document.removeEventListener("mouseup", onUp);
      bar.classList.remove("dragging");
      document.body.classList.remove("col-resizing");
      saveColWidths();
    }
    document.addEventListener("mousemove", onMove);
    document.addEventListener("mouseup", onUp);
  });

  // 双击复原默认宽度
  bar.addEventListener("dblclick", function () {
    pane.style.width = (paneId === "pane-left") ? "268px" : "400px";
    saveColWidths();
  });
}

function initColResize() {
  restoreColWidths();
  bindColSplitter("split-left", "pane-left", 1);    // 右拖 → 左变宽
  bindColSplitter("split-right", "pane-right", -1); // 右拖 → 右变窄
}

async function openDoc(char) {
  const d = await wrGet("/entries/" + encodeURIComponent(char));
  WR.doc = d;
  WR.doc.char = char;
  WR.current = char;
  WR.materials = null;
  WR.activeSeq = (d.entries && d.entries.length) ? d.entries[0].seq : 0;

  $("write-empty").style.display = "none";
  $("write-editor").style.display = "flex";
  $("doc-head-char").textContent = char;
  $("doc-head-block").textContent = d.block || "";

  renderEditor();
  refreshPreview();
  setPane(WR.pane);
  markDirty(false);
  setSaveState(d.count ? d.count + " 条" : "还没有条");

  // 右侧参考资料（异步，不阻塞）
  wrGet("/materials/" + encodeURIComponent(char)).then(function (m) {
    if (WR.current !== char) return;
    WR.materials = m;
    renderSheetPanel();
    renderGuangyunPanel();
    renderIesPanel();
    renderLexiconPanel();
  }).catch(function () {});

  try {
    WR.neighborInfo = await wrGet("/entries/" + encodeURIComponent(char) + "/neighbors");
  } catch (e) {
    WR.neighborInfo = { prev: null, next: null, index: -1, total: 0 };
  }
  updateNav();
  renderCharList();
}


/** 模块有内容时显示（连标题一起），没内容时整节隐藏 */
function setSection(secId, hasData) {
  const sec = $(secId);
  if (sec) sec.style.display = hasData ? "" : "none";
}

/** 抽构表参考模块：属性 / 值 */
function renderSheetPanel() {
  const box = $("panel-sheet");
  if (!box) return;
  const s = (WR.materials || {}).sheet;
  if (!s || !s.found) {
    box.innerHTML = "";
    setSection("sec-sheet", false);
    return;
  }

  const attrs = [];
  if (s.src_one) attrs.push(["抽构", 'code:' + s.src_one]);
  if (s.src_two) attrs.push(["参考抽构", 'code:' + s.src_two]);
  if (s.sheet) attrs.push(["分卷", s.sheet]);

  if (s.variants) {
    const alts = (s.variants.split("@")[1] || "");
    if (alts) attrs.push(["同构字", alts]);
  }

  if (s.parents && s.parents.length) {
    const list = s.parents.slice(0, 30).map(function (p) {
      return '<code class="sheet-parent">' + MD.esc(p) + "</code>";
    }).join("");
    attrs.push(["上级抽构", "raw:" + list +
      (s.parents.length > 30 ? ' <span class="dim">…+' + (s.parents.length - 30) + "</span>" : "")]);
  }

  if (s.shape) attrs.push(["规范形式", 'code:' + s.shape]);

  let html = '<div class="prop-list">' + attrs.map(function (a) {
    const raw = a[1] || "";
    let v;
    if (raw.indexOf("code:") === 0) {
      v = "<code>" + MD.esc(raw.slice(5)) + "</code>";
    } else if (raw.indexOf("raw:") === 0) {
      v = raw.slice(4);
    } else {
      v = MD.esc(raw);
    }
    return '<div class="prop-row"><span class="prop-k">' + MD.esc(a[0]) +
      '</span><span class="prop-v">' + v + "</span></div>";
  }).join("") + "</div>";

  if (s.comment) {
    html += '<div class="prop-comment">' + MD.render(s.comment) + "</div>";
  }
  box.innerHTML = html || '<div class="panel-empty">只有一条空记录。</div>';
  setSection("sec-sheet", true);
}

/** 广韵面板：谐声划分 / 声首 / 声系 */
function renderGuangyunPanel() {
  const box = $("panel-guangyun");
  if (!box) return;
  const rows = (WR.materials || {}).guangyun || [];
  if (!rows.length) {
    box.innerHTML = "";
    setSection("sec-guangyun", false);
    return;
  }
  box.innerHTML = rows.map(function (r) {
    const attrs = [];
    if (r.status) attrs.push(["音韵地位", r.status]);
    if (r.shengshou) attrs.push(["声首", r.shengshou]);
    if (r.series) attrs.push(["声系", r.series]);
    if (r.group_name) attrs.push(["组", r.group_name]);
    if (r.qieyu) attrs.push(["切语", r.qieyu]);
    if (r.qiepin) attrs.push(["切拼", r.qiepin]);
    if (r.xiesheng_domain) attrs.push(["谐声域", r.xiesheng_domain]);
    if (r.secondary) attrs.push(["二等", r.secondary]);
    if (r.chars_raw) attrs.push(["小韵", r.chars_raw]);
    if (r.notes_raw) attrs.push(["注", r.notes_raw]);

    let h = '<div class="xref-card">';
    if (r.table) h += '<div class="xref-title">' + MD.esc(r.table) + "</div>";
    h += '<div class="prop-list">' + attrs.map(function (a) {
      return '<div class="prop-row"><span class="prop-k">' + MD.esc(a[0]) +
        '</span><span class="prop-v">' + MD.esc(a[1]) + "</span></div>";
    }).join("") + "</div></div>";
    return h;
  }).join("");
  setSection("sec-guangyun", true);
}

/** IES 中古音面板 */
function renderIesPanel() {
  const box = $("panel-ies");
  if (!box) return;
  const rows = (WR.materials || {}).ies || [];
  if (!rows.length) {
    box.innerHTML = "";
    setSection("sec-ies", false);
    return;
  }
  box.innerHTML = '<div class="xref-card"><div class="prop-list">' +
    rows.map(function (v) {
      const s = (typeof v === "string") ? v : JSON.stringify(v);
      return '<div class="prop-row"><span class="prop-v mono">' + MD.esc(s) + "</span></div>";
    }).join("") + "</div></div>";
  setSection("sec-ies", true);
}

/** 词表面板：上古音 / 简化字 / 象形分类 */
function renderLexiconPanel() {
  const box = $("panel-lexicon");
  if (!box) return;
  const rows = (WR.materials || {}).lexicon || [];
  if (!rows.length) {
    box.innerHTML = "";
    setSection("sec-lexicon", false);
    return;
  }
  box.innerHTML = rows.map(function (r) {
    let body;
    const d = r.data;
    if (d === null || d === undefined) body = "";
    else if (typeof d === "string") body = MD.esc(d);
    else if (Array.isArray(d)) body = MD.esc(d.map(function (x) {
      return typeof x === "string" ? x : JSON.stringify(x);
    }).join("　"));
    else {
      body = '<div class="prop-list">' + Object.keys(d).map(function (k) {
        const v = d[k];
        if (v === null || v === undefined || v === "") return "";
        const vs = (typeof v === "object") ? JSON.stringify(v) : String(v);
        return '<div class="prop-row"><span class="prop-k">' + MD.esc(k) +
          '</span><span class="prop-v">' + MD.esc(vs) + "</span></div>";
      }).filter(Boolean).join("") + "</div>";
    }
    return '<div class="xref-card"><div class="xref-title">' + MD.esc(r.source) +
      "</div>" + body + "</div>";
  }).join("");
  setSection("sec-lexicon", true);
}

function updateNav() {
  const n = WR.neighborInfo || {};
  $("doc-prev-btn").style.display = n.prev ? "" : "none";
  $("doc-next-btn").style.display = n.next ? "" : "none";
  $("doc-nav-label").textContent = n.total ? (n.index + 1) + " / " + n.total : "";
}

// ─── 编辑器：中间四条可编辑内容 ──────────────────────────
//
// 一条 = 抽构 + 参考抽构 + 札记 + 参考文献。
// 条号 seq 从 1 开始，引用写作 `字-n`（如 丂-1）。

function seqLabel(seq) {
  return WR.doc ? WR.doc.char + "-" + seq : String(seq);
}

function renderEditor() {
  const d = WR.doc;
  const box = $("note-forms");
  const es = d.entries || [];

  const bars = es.map(function (e) {
    return '<button class="ent-bar' + (e.seq === WR.activeSeq ? " active" : "") +
      '" data-seq="' + e.seq + '">' + MD.esc(seqLabel(e.seq)) + "</button>";
  }).join("");

  const cur = es.filter(function (e) { return e.seq === WR.activeSeq; })[0];
  const isNew = !cur;
  // 新建时用一条空白草稿渲染表单，seq 留 0（保存时后端分配条号）
  const form = cur || { seq: 0, con: "", ref_con: "", notes: "", refs: [] };

  box.innerHTML =
    '<div class="note-form">' +

    '<div class="ent-bars">' +
    (bars || "") +
    (isNew ? '<button class="ent-bar active" disabled>新条</button>' : "") +
    '<button class="btn-sm ent-add" id="ent-add" title="新增一条">＋ 新增条</button>' +
    '<span class="we-spacer"></span>' +
    '<span class="hint" id="ent-count">' + es.length + " 条</span>" +
    "</div>" +

    renderEntryForm(form) +

    '<div class="nf-actions">' +
    '<button class="btn-primary btn-sm" id="ent-save">保存这条</button>' +
    '<button class="btn-sm btn-danger" id="ent-delete"' +
    (isNew ? " disabled" : "") + ">" +
    (isNew ? "删除这条" : "删除 " + MD.esc(seqLabel(cur.seq))) + "</button>" +
    '<span class="we-spacer"></span>' +
    '<button class="btn-sm" onclick="gotoChar()" title="跳到某个字（Ctrl+G）">跳转…</button>' +
    '<span class="hint" style="font-size:11px;color:var(--text2)">' +
    MD.esc(d.codepoint || "") + "</span>" +
    "</div>" +

    "</div>";

  bindEditor();
  if (!isNew) renderShapeStatus(WR.shape);
  refreshPreview();
}

function renderEntryForm(e) {
  const raw = (e.refs && e.refs.length) ? e.refs : [{ id: "", pages: "" }];
  const refRows = raw.map(refRowHtml).join("");
  return (
    '<div class="ent-body">' +

    '<div class="nf-row">' +
    '<label class="nf-label">抽构</label>' +
    '<input id="ent-con" class="nf-input nf-con ent-con" type="text" spellcheck="false" ' +
    'value="' + MD.esc(e.con || "") + '">' +
    '<div id="ent-shape-status" class="shape-status"></div>' +
    "</div>" +

    '<div class="nf-row">' +
    '<label class="nf-label">参考抽构</label>' +
    '<input id="ent-ref-con" class="nf-input ent-ref-con" type="text" spellcheck="false" ' +
    'value="' + MD.esc(e.ref_con || "") + '">' +
    "</div>" +

    '<div class="nf-row">' +
    '<label class="nf-label">札记</label>' +
    '<textarea id="ent-notes" class="nf-textarea ent-notes" spellcheck="false">' +
    MD.esc(e.notes || "") + "</textarea>" +
    "</div>" +

    '<div class="nf-row">' +
    '<label class="nf-label">参考文献</label>' +
    '<div class="ent-ref-head">' +
    '<span class="erh-id">文献编号</span>' +
    '<span class="erh-pg">起始页</span>' +
    '<span class="erh-pg">终止页</span>' +
    '<span class="erh-del"></span>' +
    "</div>" +
    '<div class="ent-refs" id="ent-refs">' + refRows + "</div>" +
    '<button class="btn-sm ent-ref-add" style="align-self:flex-start">＋ 加一条文献</button>' +
    "</div>" +

    "</div>"
  );
}

/** 一行引用：文献编号 + 起始页 + 终止页 */
function refRowHtml(r) {
  const id = (typeof r === "string") ? r : (r.id || "");
  const pages = (typeof r === "string") ? "" : (r.pages || "");
  const span = splitPages(pages);
  return '<div class="ent-ref-row">' +
    '<input class="ent-ref-input" type="text" value="' + MD.esc(id) + '">' +
    '<input class="ent-ref-pg1" type="text" value="' + MD.esc(span[0]) + '">' +
    '<input class="ent-ref-pg2" type="text" value="' + MD.esc(span[1]) + '">' +
    '<button class="btn-sm ent-ref-del">✕</button>' +
    "</div>";
}

/** 把页码范围拆成 [起, 止]；只有一个页时止为空 */
function splitPages(pages) {
  const s = (pages || "").trim();
  if (!s) return ["", ""];
  const m = s.split(/\s*(?:[—–~～\-]|至|到)\s*/);
  if (m.length >= 2) return [m[0].trim(), m.slice(1).join("-").trim()];
  return [s, ""];
}

/** [起, 止] 合回页码范围字符串 */
function joinPages(pg1, pg2) {
  const a = (pg1 || "").trim();
  const b = (pg2 || "").trim();
  if (a && b) return a === b ? a : a + "—" + b;
  return a || b || "";
}

/** `L005` 或 `L005:12—15` */
function refLabel(r) {
  const id = (typeof r === "string") ? r : (r.id || "");
  const pages = (typeof r === "string") ? "" : ((r.pages || "").trim());
  return pages ? id + ":" + pages : id;
}

/** 把四个框收回 WR.doc.entries 里当前那条；新建时返回一个草稿对象 */
function collectEntry() {
  const d = WR.doc;
  if (!d) return null;
  const cur = (d.entries || []).filter(function (e) { return e.seq === WR.activeSeq; })[0];
  const target = cur || { seq: 0, con: "", ref_con: "", notes: "", refs: [] };
  const conEl = $("ent-con");
  if (conEl) target.con = conEl.value.trim();
  const rcEl = $("ent-ref-con");
  if (rcEl) target.ref_con = rcEl.value.trim();
  const ntEl = $("ent-notes");
  if (ntEl) target.notes = ntEl.value;
  const refs = [];
  document.querySelectorAll("#ent-refs .ent-ref-row").forEach(function (row) {
    const idEl = row.querySelector(".ent-ref-input");
    const p1 = row.querySelector(".ent-ref-pg1");
    const p2 = row.querySelector(".ent-ref-pg2");
    const id = idEl ? idEl.value.trim() : "";
    const pages = joinPages(p1 ? p1.value : "", p2 ? p2.value : "");
    if (!id && !pages) return;
    const rec = { id: id };
    if (pages) rec.pages = pages;
    refs.push(rec);
  });
  target.refs = refs;
  return target;
}

function bindEditor() {
  const box = $("note-forms");
  if (!box) return;

  // 条切换
  box.querySelectorAll(".ent-bar").forEach(function (b) {
    b.addEventListener("click", function () {
      collectEntry();
      WR.activeSeq = parseInt(b.getAttribute("data-seq"), 10) || 1;
      renderEditor();
    });
  });

  // 新增条
  const add = $("ent-add");
  if (add) add.addEventListener("click", function () {
    collectEntry();
    WR.activeSeq = 0;                 // 0 = 新建
    renderEditor();
    const con = $("ent-con");
    if (con) { con.value = ""; con.focus(); }
    const rc = $("ent-ref-con"); if (rc) rc.value = "";
    const nt = $("ent-notes"); if (nt) nt.value = "";
    markDirty(true);
    setSaveState("新条，未保存");
  });

  // 保存 / 删除
  const save = $("ent-save");
  if (save) save.addEventListener("click", saveEntry);
  const del = $("ent-delete");
  if (del) del.addEventListener("click", deleteEntry);

  // 实时：校验抽构 + 刷新预览
  const con = $("ent-con");
  if (con) con.addEventListener("input", onEntryInput);
  const rc = $("ent-ref-con");
  if (rc) rc.addEventListener("input", onEntryInput);
  const nt = $("ent-notes");
  if (nt) nt.addEventListener("input", onEntryInput);

  // 参考文献行
  const addRef = box.querySelector(".ent-ref-add");
  if (addRef) addRef.addEventListener("click", function () {
    const wrap = $("ent-refs");
    const div = document.createElement("div");
    div.className = "ent-ref-row";
    div.innerHTML = '<input class="ent-ref-input" type="text">' +
      '<input class="ent-ref-pg1" type="text">' +
      '<input class="ent-ref-pg2" type="text">' +
      '<button class="btn-sm ent-ref-del">✕</button>';
    wrap.appendChild(div);
    div.querySelector(".ent-ref-input").focus();
    bindRefRowDel(div);
    onEntryInput();
  });
  box.querySelectorAll(".ent-ref-row").forEach(bindRefRowDel);
}

function bindRefRowDel(row) {
  const btn = row.querySelector(".ent-ref-del");
  if (!btn) return;
  btn.addEventListener("click", function () {
    const wrap = $("ent-refs");
    if (wrap.querySelectorAll(".ent-ref-row").length <= 1) {
      row.querySelectorAll("input").forEach(function (i) { i.value = ""; });
    } else {
      row.remove();
    }
    onEntryInput();
  });
}

let _shapeTimer = null;

function onEntryInput() {
  markDirty(true);
  setSaveState("未保存");
  collectEntry();
  refreshPreview();
  clearTimeout(_shapeTimer);
  _shapeTimer = setTimeout(validateShape, 220);
}

async function validateShape() {
  const conEl = $("ent-con");
  if (!conEl) return;
  const expr = conEl.value.trim();
  if (!expr) { WR.shape = null; renderShapeStatus(null); return; }
  try {
    WR.shape = await wrSend("/shape/validate", { expr: expr });
    renderShapeStatus(WR.shape);
  } catch (e) { /* 校验失败不打断输入 */ }
}

function renderShapeStatus(res) {
  const el = $("ent-shape-status");
  if (!el) return;
  if (!res) {
    el.className = "shape-status";
    el.innerHTML = "";
    return;
  }
  if (!res.ok) {
    const err = res.error || {};
    el.className = "shape-status bad";
    el.innerHTML = "✕ " + MD.esc(err.message || "格式错误") +
      (typeof err.pos === "number"
        ? ' <span class="shape-pos">第 ' + (err.pos + 1) + " 字符</span>" : "");
    return;
  }
  const parts = ['<span class="shape-ok">✓ ' + res.leaf_count + " 个部件，深 " +
    res.depth + "</span>"];
  if (res.normalized) parts.push('<code class="shape-norm">' + MD.esc(res.normalized) + "</code>");
  el.className = "shape-status";
  el.innerHTML = parts.join(" ");
  if (res.warnings && res.warnings.length) {
    el.innerHTML += '<div class="shape-warn">⚠ ' + res.warnings.map(MD.esc).join("<br>⚠ ") + "</div>";
  }
}

function refreshPreview() {
  if (!WR.doc) return;
  const el = $("doc-preview");
  if (!el) return;
  el.innerHTML = MD.render(renderMarkdown(WR.doc));
}

/** 该字所有条合并的 Markdown（预览用） */
function renderMarkdown(d) {
  const es = (d.entries || []).filter(function (e) { return e.seq > 0; });
  const lines = ["# " + d.char, ""];
  if (!es.length) {
    lines.push("（还没有条）");
    return lines.join("\n") + "\n";
  }
  es.forEach(function (e) {
    lines.push("## " + d.char + "-" + e.seq, "");
    if (e.con) lines.push("- 抽构：`" + e.con + "`");
    if (e.ref_con) lines.push("- 参考抽构：`" + e.ref_con + "`");
    if (e.con || e.ref_con) lines.push("");
    if ((e.notes || "").trim()) { lines.push(e.notes.trim(), ""); }
    if (e.refs && e.refs.length) {
      lines.push("文献：" + e.refs.map(refLabel).filter(Boolean).join("、"), "");
    }
  });
  return lines.join("\n").replace(/\n\n\n/g, "\n\n").replace(/\s+$/, "") + "\n";
}

// ─── 保存 / 删除 ─────────────────────────────────────────

async function saveEntry() {
  const d = WR.doc;
  if (!d) return;
  const payload = collectEntry();
  if (!payload) return;

  // 提前本地校验抽构，省一次往返
  const check = await wrSend("/shape/validate", { expr: payload.con || "" });
  WR.shape = check;
  renderShapeStatus(check);
  if (!check.ok) {
    setSaveState("抽构格式错误", "err");
    const el = $("ent-con"); if (el) el.focus();
    return;
  }

  try {
    setSaveState("保存中…");
    const r = await wrSend("/entries/" + encodeURIComponent(d.char), {
      seq: WR.activeSeq || 0,
      con: payload.con || "",
      ref_con: payload.ref_con || "",
      notes: payload.notes || "",
      refs: payload.refs || [],
    });
    const saved = r.entry;
    const i = (d.entries || []).findIndex(function (x) { return x.seq === saved.seq; });
    if (i >= 0) d.entries[i] = saved;
    else d.entries.push(saved);
    d.entries.sort(function (a, b) { return a.seq - b.seq; });
    d.count = d.entries.length;
    d.next_seq = r.count + 1;
    WR.activeSeq = saved.seq;

    markDirty(false);
    setSaveState("已保存 " + r.key, "ok");
    setTimeout(function () { setSaveState(""); }, 1600);
    renderEditor();
    bumpCharCount(d.char, d.count);
  } catch (e) {
    setSaveState(e.message || "保存失败", "err");
  }
}

async function deleteEntry() {
  const d = WR.doc;
  if (!d || !WR.activeSeq) return;
  const seq = WR.activeSeq;
  if (!window.confirm("删除「" + d.char + "-" + seq + "」这一条？")) return;
  try {
    const r = await wrSend("/entries/" + encodeURIComponent(d.char) + "/seq/" + seq,
      undefined, "DELETE");
    // 后端没删到就别在前端假装删了（否则切走再回来又冒出来）
    if (!r.deleted) {
      setSaveState("这一条已经不存在", "err");
      await openDoc(d.char);
      return;
    }
  } catch (e) {
    setSaveState(e.message || "删除失败", "err");
    return;
  }
  d.entries = d.entries.filter(function (e) { return e.seq !== seq; });
  d.count = d.entries.length;
  WR.activeSeq = d.entries.length ? d.entries[0].seq : 0;
  markDirty(false);
  setSaveState("已删除");
  renderEditor();
  bumpCharCount(d.char, d.count);
}

/** 更新左侧列表里的条数 */
function bumpCharCount(char, n) {
  if (WR.allChars) {
    const c = WR.allChars.find(function (x) { return x.char === char; });
    if (c) c.entries = n;
  }
  renderCharList();
}

// ─── 编辑 / 预览 切换 ────────────────────────────────────

/** mode: "edit" | "preview" —— 左边一个框，二选一 */
function setPane(mode) {
  if (mode !== "preview") mode = "edit";
  WR.pane = mode;

  const editPane = $("pane-edit");
  const prevPane = $("pane-preview");
  const editBtn = $("sw-edit");
  const prevBtn = $("sw-preview");

  if (editPane) editPane.classList.toggle("active", mode === "edit");
  if (prevPane) prevPane.classList.toggle("active", mode === "preview");
  if (editBtn) editBtn.classList.toggle("active", mode === "edit");
  if (prevBtn) prevBtn.classList.toggle("active", mode === "preview");

  if (mode === "preview") refreshPreview();
}

function togglePane() {
  setPane(WR.pane === "preview" ? "edit" : "preview");
}

// ─── 导航 ────────────────────────────────────────────────

function confirmLeave(then) {
  if (!WR.dirty) { then(); return; }
  const save = window.confirm("有未保存的修改。\n\n「确定」= 保存后切换　「取消」= 放弃");
  if (save) saveEntry().then(function () { then(); });
  else { markDirty(false); then(); }
}

function gotoChar() {
  const c = window.prompt("跳到哪个字？");
  if (!c || !c.trim()) return;
  confirmLeave(function () {
    const ch = c.trim();
    if (WR.allChars) {
      const i = WR.allChars.findIndex(function (x) { return x.char === ch; });
      if (i >= 0) {
        WR.blockFilter = "__all__";
        document.querySelectorAll(".block-filter .blk-chip").forEach(function (b) {
          b.classList.toggle("active", b.getAttribute("data-block") === "__all__");
        });
        WR.chars = WR.allChars;
        WR.page = Math.floor(i / WR.perPage) + 1;   // 跳到这个字所在页
        renderCharList();
      }
    }
    openDoc(ch);
  });
}

// ─── 事件绑定 ────────────────────────────────────────────

function initWriter() {
  if (WR.initialized) return;
  WR.initialized = true;

  let searchTimer = null;
  $("doc-search").addEventListener("input", function () {
    clearTimeout(searchTimer);
    searchTimer = setTimeout(function () { loadCharList(false); }, 200);
  });
  $("doc-refresh-btn").addEventListener("click", async function () {
    WR.allChars = null;
    await loadCharList(true);
  });
  $("doc-first-blank").addEventListener("click", jumpFirstBlank);

  $("sw-edit").addEventListener("click", function () { setPane("edit"); });
  $("sw-preview").addEventListener("click", function () { setPane("preview"); });

  $("doc-prev-btn").addEventListener("click", function () {
    if (WR.neighborInfo.prev) confirmLeave(function () { openDoc(WR.neighborInfo.prev); });
  });
  $("doc-next-btn").addEventListener("click", function () {
    if (WR.neighborInfo.next) confirmLeave(function () { openDoc(WR.neighborInfo.next); });
  });

  // 右侧参考资料面板切换
  document.querySelectorAll("#view-write .ref-tab").forEach(function (tab) {
    tab.addEventListener("click", function () {
      const name = tab.getAttribute("data-panel");
      document.querySelectorAll("#view-write .ref-tab").forEach(function (t) {
        t.classList.toggle("active", t === tab);
      });
      document.querySelectorAll("#view-write .ref-panel").forEach(function (p) {
        p.classList.toggle("active", p.id === "panel-" + name);
      });
      if (name === "refs" && window.REF && window.REF.init) window.REF.init();
    });
  });

  document.addEventListener("keydown", function (e) {
    const view = $("view-write");
    if (!view || !view.classList.contains("active")) return;
    if (!(e.ctrlKey || e.metaKey)) return;
    if (e.key === "s") { e.preventDefault(); saveEntry(); }
    else if (e.key === "e") { e.preventDefault(); togglePane(); }
    else if (e.key === "ArrowUp") {
      e.preventDefault();
      if (WR.neighborInfo.prev) confirmLeave(function () { openDoc(WR.neighborInfo.prev); });
    } else if (e.key === "ArrowDown") {
      e.preventDefault();
      if (WR.neighborInfo.next) confirmLeave(function () { openDoc(WR.neighborInfo.next); });
    } else if (e.key === "g") { e.preventDefault(); gotoChar(); }
  });

  window.addEventListener("beforeunload", function (e) {
    if (WR.dirty) { e.preventDefault(); e.returnValue = ""; }
  });

  setPane("edit");
  initColResize();
  (async function () {
    await loadBlocks();
    await loadCharList(true);
  })();
}
