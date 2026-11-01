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
  verify: null,        // 当前字的核验结果
  verifySummary: null, // 全库核验计数（左栏区段标签）
  initialized: false,
  page: 1,            // 左侧列表当前页
  perPage: 100,       // 每页多少个字
  obSel: [],          // 当前条选中的甲骨文编号
  biSel: [],          // 当前条选中的金文编号
  xzSel: [],          // 当前条选中的小篆序号（只有这些会保存）
  xzDefault: [],      // 按字形表映射默认显示的小篆序号（不保存）
  glyphIndex: null,   // 甲骨文 / 金文的 编号→字形 对照表（只取一次）
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
  const by = (WR.verifySummary && WR.verifySummary.by_block) || {};
  box.innerHTML = WR.blocks.map(function (b) {
    const n = by[b.key] || 0;
    return '<button class="blk-chip" data-block="' + b.key + '">' + MD.esc(b.name) +
      (n ? '<span class="blk-err" title="' + n + ' 处核验问题">' + n + "</span>" : "") +
      "</button>";
  }).join("");

  // 顶部「全部 / ✓ 已写」与下方区段共用同一套点击逻辑
  // （「▶ 未写」是动作按钮，不是筛选，单独处理，这里排除掉）
  bindBlockChipClicks();
}

/** 给区段 chip 绑点击（只绑一次；innerHTML 重画后新元素再绑） */
function bindBlockChipClicks() {
  document.querySelectorAll(".block-filter .blk-chip[data-block]").forEach(function (el) {
    if (el.getAttribute("data-bound")) return;
    el.setAttribute("data-bound", "1");
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
    const bad = ((WR.verifySummary && WR.verifySummary.by_char) || {})[c.char] || 0;
    return '<div class="doc-item' + (c.char === WR.current ? " active" : "") +
      '" data-char="' + MD.esc(c.char) + '">' +
      '<span class="di-char">' + c.char + "</span>" +
      '<span class="di-cp">' + MD.esc((c.codepoint || "").replace("U+", "")) + "</span>" +
      (bad ? '<span class="di-err" title="' + bad + ' 处核验问题"></span>' : "") +
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

/** 跳到「当前列表里第一个有核验问题的字」 */
async function jumpFirstIssue() {
  if ($("doc-search").value.trim()) {
    $("doc-search").value = "";
    await loadCharList(false);
  }
  if (!WR.verifySummary) await loadVerifySummary();
  const by = (WR.verifySummary && WR.verifySummary.by_char) || {};
  const idx = WR.chars.findIndex(function (c) { return by[c.char]; });
  if (idx < 0) {
    setSaveState("没有核验问题", "ok");
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

// ─── 三栏拖拽调宽 ────────────────────────────────────────//
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
  await loadGlyphIndex();          // 甲骨文 / 金文的字形靠对照表画，先备好
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
  refreshVerify();

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
  const form = cur || { seq: 0, con: "", ref_con: "", notes: "" };
  WR.obSel = ((cur && cur.ob) || []).slice();
  WR.biSel = ((cur && cur.bi) || []).slice();
  WR.xzSel = ((cur && cur.xz) || []).slice();

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
  renderGlyphChips("ob");
  renderGlyphChips("bi");
  renderGlyphChips("xz");
  if (!WR.xzSel.length) loadSealDefaults(d.char);
  if (!isNew) renderShapeStatus(WR.shape);
  refreshPreview();
  applyVerifyMarks();
}

function renderEntryForm(e) {
  return (
    '<div class="ent-body">' +

    '<div class="nf-row nf-pair">' +
    '<div class="nf-cell">' +
    '<label class="nf-label">抽构</label>' +
    '<input id="ent-con" class="nf-input nf-con ent-con" type="text" spellcheck="false" ' +
    'value="' + MD.esc(e.con || "") + '">' +
    "</div>" +
    '<div class="nf-cell">' +
    '<label class="nf-label">参考抽构</label>' +
    '<input id="ent-ref-con" class="nf-input ent-ref-con" type="text" spellcheck="false" ' +
    'value="' + MD.esc(e.ref_con || "") + '">' +
    "</div>" +
    "</div>" +

    '<div id="ent-shape-status" class="shape-status"></div>' +

    '<div class="nf-row nf-pair">' +
    '<div class="nf-cell">' +
    '<label class="nf-label">甲骨文' +
    '<span class="hint">可多选</span></label>' +
    '<div class="glyph-pick">' +
    '<div class="glyph-chips" id="ent-ob-chips"></div>' +
    '<button class="btn-sm" id="ent-ob-add" title="选择甲骨文字形">＋ 选择</button>' +
    "</div>" +
    "</div>" +
    '<div class="nf-cell">' +
    '<label class="nf-label">金文' +
    '<span class="hint">可多选</span></label>' +
    '<div class="glyph-pick">' +
    '<div class="glyph-chips" id="ent-bi-chips"></div>' +
    '<button class="btn-sm" id="ent-bi-add" title="选择金文字形">＋ 选择</button>' +
    "</div>" +
    "</div>" +
    '<div class="nf-cell">' +
    '<label class="nf-label">小篆' +
    '<span class="hint">可多选</span></label>' +
    '<div class="glyph-pick">' +
    '<div class="glyph-chips" id="ent-xz-chips"></div>' +
    '<button class="btn-sm" id="ent-xz-add" title="选择小篆字形">＋ 选择</button>' +
    "</div>" +
    "</div>" +
    "</div>" +

    '<div class="nf-row">' +
    '<label class="nf-label">札记</label>' +
    '<textarea id="ent-notes" class="nf-textarea ent-notes" spellcheck="false">' +
    MD.esc(e.notes || "") + "</textarea>" +
    "</div>" +

    "</div>"
  );
}

// ─── 甲骨文 / 金文 / 小篆：每条各选若干字形 ───────────────
//
// 三种字体都把字形放在私用区，码位 = 0xF0000 + 序号 - 1：
//   甲骨文 → ob.jsonl 的 num（如 0001），字体 ZihuiSongJGW
//   金文   → bi.jsonl 的字形本身（编号是拓片号，会重号），字体 ZihuiSongJW
//   小篆   → seal.ndjson 的 num（如 01998），字体 sw-ccz-1963-rev1
// 候选项由后端按字查好，这里只负责多选。

const GLYPH_KINDS = {
  ob: { cls: "ob-glyph", chips: "ent-ob-chips", picker: "甲骨文", hint: "搜索编号 / 释文中的字", api: "ob" },
  bi: { cls: "bi-glyph", chips: "ent-bi-chips", picker: "金文", hint: "搜索编号 / 释文中的字", api: "bi" },
  xz: { cls: "xz-glyph", chips: "ent-xz-chips", picker: "小篆", hint: "搜索序号 / 字", api: "seal" },
};

function glyphChar(id) {
  const n = parseInt(String(id).replace(/[^0-9]/g, ""), 10);
  return n >= 1 ? String.fromCodePoint(0xF0000 + n - 1) : "";
}

/** 编号 → 字形字符：小篆能算，甲骨文 / 金文的编号去过重（`0001A`），查对照表 */
function glyphOf(kind, id) {
  if (kind === "xz") return glyphChar(id);
  const hit = ((WR.glyphIndex || {})[kind] || {})[id];
  return hit || (String(id).replace(/[0-9]/g, "") ? "" : glyphChar(id));
}

/** 甲骨文 / 金文编号对照表只取一次 */
async function loadGlyphIndex() {
  if (WR.glyphIndex) return WR.glyphIndex;
  try {
    WR.glyphIndex = await wrGet("/glyphs/index");
  } catch (e) {
    WR.glyphIndex = { ob: {}, bi: {} };
  }
  return WR.glyphIndex;
}

/** 给 markdown 渲染器用：`[ob:0001A]` 这类标记要换成字体里的字形 */
function glyphLookup(kind, id) {
  const k = kind === "seal" ? "xz" : kind;
  return glyphOf(k, id);
}
window.GLYPH_LOOKUP = glyphLookup;

function glyphSel(kind) {
  if (kind === "ob") return WR.obSel;
  if (kind === "bi") return WR.biSel;
  return WR.xzSel;
}

function glyphSet(kind, list) {
  if (kind === "ob") WR.obSel = list;
  else if (kind === "bi") WR.biSel = list;
  else WR.xzSel = list;
}

function glyphClass(kind) { return (GLYPH_KINDS[kind] || GLYPH_KINDS.ob).cls; }

/** 小篆的「默认选中」：按 seal.ndjson 的映射查出来，但不落盘 */
async function loadSealDefaults(char) {
  WR.xzDefault = [];
  if (!char) return;
  try {
    const d = await wrGet("/glyphs/seal?char=" + encodeURIComponent(char) + "&limit=8");
    if (WR.current !== char || WR.xzSel.length) return;
    WR.xzDefault = (d.results || []).map(function (r) { return r.num; });
    renderGlyphChips("xz");
  } catch (e) { /* 查不到就没有默认 */ }
}

/** 把当前条已选的字形画成一排小方块，点一下取消选择 */
function renderGlyphChips(kind) {
  const box = $(GLYPH_KINDS[kind].chips);
  if (!box) return;
  const sel = glyphSel(kind);
  const defs = kind === "xz" && !sel.length ? (WR.xzDefault || []) : [];
  if (!sel.length && !defs.length) {
    box.innerHTML = '<span class="glyph-empty">未选</span>';
    return;
  }
  const chip = function (id, isDefault) {
    return '<span class="glyph-chip' + (isDefault ? " is-default" : "") +
      '" data-id="' + MD.esc(id) + '" title="' +
      (isDefault ? "按字表映射默认选中，未保存" : "点击取消选择") + '">' +
      '<span class="g ' + glyphClass(kind) + '">' + MD.esc(glyphOf(kind, id)) + "</span>" +
      '<span class="n">' + MD.esc(id) + "</span>" +
      (isDefault ? '<span class="d">默认</span>' : "") + "</span>";
  };
  box.innerHTML = sel.map(function (id) { return chip(id, false); }).join("") +
    defs.map(function (id) { return chip(id, true); }).join("");
  box.querySelectorAll(".glyph-chip:not(.is-default)").forEach(function (el) {
    el.addEventListener("click", function () {
      const id = el.getAttribute("data-id");
      const list = glyphSel(kind);
      const i = list.indexOf(id);
      if (i >= 0) list.splice(i, 1);
      renderGlyphChips(kind);
      markDirty(true);
      setSaveState("未保存");
      refreshPreview();
    });
  });
}

/** 打开选字形面板：先列这个字的候选，也能按编号 / 字搜索整张表 */
function openGlyphPicker(kind) {
  const old = document.querySelector(".gp-overlay");
  if (old) old.remove();

  const meta = GLYPH_KINDS[kind];
  const isSeal = kind === "xz";
  const picked = glyphSel(kind);
  // 小篆还没选过时，先把映射出来的默认项勾上
  const sel = new Set(picked.length ? picked : (isSeal ? (WR.xzDefault || []) : []));
  const ov = document.createElement("div");
  ov.className = "gp-overlay";
  ov.innerHTML =
    '<div class="gp-box">' +
    '<div class="gp-head">' +
    '<span class="gp-title">选择' + meta.picker + "</span>" +
    '<input id="gp-q" type="text" placeholder="' + meta.hint + '">' +
    '<span class="hint" id="gp-count"></span>' +
    '<button class="btn-primary btn-sm" id="gp-done">完成</button>' +
    '<button class="btn-sm" id="gp-cancel">取消</button>' +
    "</div>" +
    '<div class="gp-body"><div class="gp-grid" id="gp-grid"></div></div>' +
    "</div>";
  document.body.appendChild(ov);

  const grid = ov.querySelector("#gp-grid");
  const countEl = ov.querySelector("#gp-count");
  const qEl = ov.querySelector("#gp-q");

  function cellHtml(it) {
    const id = it.num;
    const sub = isSeal ? (it.char || "") : (it.con || []).join("、");
    return '<button class="gp-cell' + (sel.has(id) ? " on" : "") + '" data-id="' +
      MD.esc(id) + '" title="' + MD.esc(sub) + '">' +
      '<span class="gp-g ' + glyphClass(kind) + '">' +
      it.glyph + "</span>" +
      '<span class="gp-n">' + MD.esc(it.num) + "</span>" +
      (sub ? '<span class="gp-z">' + MD.esc(sub.slice(0, 6)) + "</span>" : "") +
      "</button>";
  }

  async function fill(q) {
    let data;
    try {
      data = await wrGet("/glyphs/" + meta.api +
        "?char=" + encodeURIComponent(WR.current || "") +
        "&q=" + encodeURIComponent(q || ""));
    } catch (e) {
      grid.innerHTML = '<div class="empty">读取失败：' + MD.esc(e.message) + "</div>";
      return;
    }
    const items = data.results || [];
    countEl.textContent = items.length + " / " + (data.total || 0) +
      (data.browse ? "（该字还没标注，列出全部）" : "");
    grid.innerHTML = items.length
      ? items.map(cellHtml).join("")
      : '<div class="empty">没有候选，换个搜索词试试</div>';
    grid.querySelectorAll(".gp-cell").forEach(function (el) {
      el.addEventListener("click", function () {
        const id = el.getAttribute("data-id");
        if (sel.has(id)) { sel.delete(id); el.classList.remove("on"); }
        else { sel.add(id); el.classList.add("on"); }
      });
    });
  }

  let timer = null;
  qEl.addEventListener("input", function () {
    clearTimeout(timer);
    timer = setTimeout(function () { fill(qEl.value.trim()); }, 200);
  });

  function close() { ov.remove(); document.removeEventListener("keydown", onKey); }
  function onKey(ev) { if (ev.key === "Escape") close(); }
  document.addEventListener("keydown", onKey);
  ov.addEventListener("click", function (ev) { if (ev.target === ov) close(); });
  ov.querySelector("#gp-cancel").addEventListener("click", close);
  ov.querySelector("#gp-done").addEventListener("click", function () {
    // 保持候选里的先后顺序：先已选的原有顺序，再补新选的
    const list = glyphSel(kind);
    const kept = list.filter(function (id) { return sel.has(id); });
    sel.forEach(function (id) { if (kept.indexOf(id) < 0) kept.push(id); });
    if (kind === "ob") WR.obSel = kept;
    else if (kind === "bi") WR.biSel = kept;
    else WR.xzSel = kept;
    close();
    renderGlyphChips(kind);
    markDirty(true);
    setSaveState("未保存");
    refreshPreview();
  });

  fill("");
  qEl.focus();
}

/** 把各框收回 WR.doc.entries 里当前那条；新建时返回一个草稿对象 */
function collectEntry() {
  const d = WR.doc;
  if (!d) return null;
  const cur = (d.entries || []).filter(function (e) { return e.seq === WR.activeSeq; })[0];
  const target = cur || { seq: 0, con: "", ref_con: "", notes: "" };
  const conEl = $("ent-con");
  if (conEl) target.con = conEl.value.trim();
  const rcEl = $("ent-ref-con");
  if (rcEl) target.ref_con = rcEl.value.trim();
  const ntEl = $("ent-notes");
  if (ntEl) target.notes = ntEl.value;
  target.ob = WR.obSel.slice();
  target.bi = WR.biSel.slice();
  target.xz = WR.xzSel.slice();
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

  // 甲骨文 / 金文 / 小篆：每条各选若干字形
  const obAdd = $("ent-ob-add");
  if (obAdd) obAdd.addEventListener("click", function () { openGlyphPicker("ob"); });
  const biAdd = $("ent-bi-add");
  if (biAdd) biAdd.addEventListener("click", function () { openGlyphPicker("bi"); });
  const xzAdd = $("ent-xz-add");
  if (xzAdd) xzAdd.addEventListener("click", function () { openGlyphPicker("xz"); });

  // 实时：校验抽构 + 刷新预览
  const con = $("ent-con");
  if (con) {
    con.addEventListener("input", onEntryInput);
    if (window.SHAPEFMT) SHAPEFMT.bind(con, { onFormatted: afterShapeFormat });
  }
  const rc = $("ent-ref-con");
  if (rc) {
    rc.addEventListener("input", onEntryInput);
    if (window.SHAPEFMT) SHAPEFMT.bind(rc, { onFormatted: afterShapeFormat });
  }
  const nt = $("ent-notes");
  if (nt) nt.addEventListener("input", onEntryInput);
}

let _shapeTimer = null;
let _shapeToken = 0;

function onEntryInput(ev) {
  const el = ev && ev.target;
  if (el && window.SHAPEFMT && (el.id === "ent-con" || el.id === "ent-ref-con")) {
    SHAPEFMT.normalizeChars(el);   // 全角括号立刻转掉，规范写法等停顿后再回写
  }
  markDirty(true);
  setSaveState("未保存");
  collectEntry();
  refreshPreview();
  clearTimeout(_shapeTimer);
  _shapeTimer = setTimeout(validateShape, 220);
}

/** 抽构 / 参考抽构被自动格式化后：收回草稿、刷新预览 */
function afterShapeFormat() {
  markDirty(true);
  setSaveState("未保存");
  collectEntry();
  refreshPreview();
}

async function validateShape() {
  const token = ++_shapeToken;
  const conEl = $("ent-con");
  if (!conEl) return;
  const expr = conEl.value.trim();
  if (!expr) { WR.shape = null; renderShapeStatus(null); return; }
  try {
    const res = await wrSend("/shape/validate", { expr: expr });
    if (token !== _shapeToken) return;          // 输入还在继续，丢掉过期结果
    WR.shape = res;
    renderShapeStatus(res);
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

// ─── 预览：自动生成参考文献表 ──────────────────────────────
//
// 札记里的 `[ref:C001.244-245+248]` 会把 C001 收集进文末的参考文献表，
// 按 第一作者 → 年份 → 篇名 排序。

const CITE_ID_RE = /\[\s*ref\s*[:：]\s*([^\[\]\.．\s]+)/gi;
const CITE_COLLATOR = new Intl.Collator("zh-Hans-CN");

let _previewToken = 0;

/** 该字所有条里引到的文献编号，去重、保持出现顺序 */
function citedIds(d) {
  const ids = [];
  ((d && d.entries) || []).forEach(function (e) {
    const notes = e.notes || "";
    let m;
    CITE_ID_RE.lastIndex = 0;
    while ((m = CITE_ID_RE.exec(notes))) {
      if (ids.indexOf(m[1]) < 0) ids.push(m[1]);
    }
  });
  return ids;
}

/** 排序键：第一作者 / 年份 / 篇名；文献库里没有的排最后 */
function citeSortKeys(rec) {
  if (!rec) return ["\uffff", "", ""];
  return [
    (rec.author && rec.author[0]) || "",
    String(rec.year || rec.date || ""),
    rec.article_title || rec.book_title || "",
  ];
}

function cmpCite(a, b) {
  const ka = citeSortKeys(a.rec);
  const kb = citeSortKeys(b.rec);
  for (let i = 0; i < ka.length; i++) {
    const c = CITE_COLLATOR.compare(ka[i], kb[i]);
    if (c) return c;
  }
  return CITE_COLLATOR.compare(a.id, b.id);
}

/** 预览用的文档：新条还没保存时，把表单里的草稿也并进去 */
function previewDoc() {
  const d = WR.doc;
  if (!d) return d;
  const entries = d.entries || [];
  if (entries.some(function (e) { return e.seq === WR.activeSeq; })) return d;
  const val = function (id) { const el = $(id); return el ? el.value : ""; };
  const draft = {
    seq: entries.reduce(function (m, e) { return Math.max(m, e.seq || 0); }, 0) + 1,
    con: val("ent-con").trim(),
    ref_con: val("ent-ref-con").trim(),
    ob: WR.obSel.slice(),
    bi: WR.biSel.slice(),
    xz: WR.xzSel.slice(),
    notes: val("ent-notes"),
  };
  if (!draft.con && !draft.ref_con && !(draft.notes || "").trim() &&
      !draft.ob.length && !draft.bi.length && !draft.xz.length) return d;
  return Object.assign({}, d, { entries: entries.concat([draft]) });
}

function refreshPreview() {
  if (!WR.doc) return;
  const el = $("doc-preview");
  if (!el) return;
  const token = ++_previewToken;
  const doc = previewDoc();
  el.innerHTML = MD.render(renderMarkdown(doc));
  bindPreviewImages(el);
  appendCiteList(el, token, doc);
}

async function appendCiteList(box, token, doc) {
  const ids = citedIds(doc || WR.doc);
  if (!ids.length) return;

  let map = window.REF && window.REF.byId;
  if (!map && window.REF && window.REF.ensureAll) {
    try { map = await window.REF.ensureAll(); } catch (e) { map = {}; }
  }
  if (token !== _previewToken || !box.isConnected) return;   // 预览已经重画过

  const items = ids.map(function (id) {
    let rec = null;
    if (map) {
      rec = map[id] || null;
      if (!rec) {
        const hit = Object.keys(map).find(function (k) {
          return k.toLowerCase() === id.toLowerCase();
        });
        rec = hit ? map[hit] : null;
      }
    }
    return { id: id, rec: rec };
  }).sort(cmpCite);

  const sec = document.createElement("section");
  sec.className = "cite-list";
  sec.innerHTML = '<div class="cite-h">参考文献</div>' +
    items.map(function (it) {
      return '<div class="cite-row"><span class="cite-id">' + MD.esc(it.id) +
        '</span><span class="cite-text">' + citeHtml(it.rec) + "</span></div>";
    }).join("");
  box.appendChild(sec);
}

/** 文献库里的一条 → 预览里的引用文本；有网址时把篇名 / 书名做成链接 */
function citeHtml(rec) {
  if (!rec || !rec.citation) {
    return '<span class="cite-missing">文献库里没有这个编号</span>';
  }
  const text = String(rec.citation);
  const url = String(rec.url || "").trim();
  const title = String(rec.article_title || rec.book_title || "").trim();
  const needle = title ? "《" + title + "》" : "";
  const at = (url && needle) ? text.indexOf(needle) : -1;
  if (at < 0 || !/^https?:\/\//i.test(url)) return MD.esc(text);
  return MD.esc(text.slice(0, at)) +
    '<a class="cite-link" href="' + MD.esc(url) + '" target="_blank" ' +
    'rel="noopener noreferrer">' + MD.esc(needle) + "</a>" +
    MD.esc(text.slice(at + needle.length));
}

// ─── 预览里的图片：点选 + 拖动右下角改宽度 ────────────────
//
// 预览是只读渲染结果，改宽度最终要写回札记正文里的 `{w=…}`，
// 所以拖动只改 DOM，松手时再回写并重画。

function bindPreviewImages(root) {
  if (!root) return;
  root.querySelectorAll(".md-fig").forEach(function (fig) {
    const img = fig.querySelector("img");
    const handle = fig.querySelector(".md-fig-handle");
    if (!img) return;
    fig.addEventListener("click", function (ev) {
      ev.stopPropagation();
      root.querySelectorAll(".md-fig.active").forEach(function (f) {
        if (f !== fig) f.classList.remove("active");
      });
      fig.classList.add("active");
    });
    if (handle) handle.addEventListener("mousedown", function (ev) {
      ev.preventDefault();
      ev.stopPropagation();
      startImageResize(fig, img, ev);
    });
  });
}

function startImageResize(fig, img, ev) {
  const startX = ev.clientX;
  const startW = img.getBoundingClientRect().width || fig.offsetWidth || 100;
  const box = fig.parentElement || fig;
  const maxW = Math.max(box.clientWidth || 0, 80);
  fig.classList.add("resizing");
  WR.imgResizing = true;
  const cursor = document.body.style.cursor;
  document.body.style.cursor = "nwse-resize";

  function onMove(e) {
    let w = Math.round(startW + (e.clientX - startX));
    w = Math.max(24, Math.min(w, maxW));
    fig.dataset.w = String(w);
    fig.style.width = w + "px";
  }
  function onUp() {
    document.removeEventListener("mousemove", onMove);
    document.removeEventListener("mouseup", onUp);
    document.body.style.cursor = cursor;
    fig.classList.remove("resizing");
    WR.imgResizing = false;
    const w = parseInt(fig.dataset.w, 10) || 0;
    if (w) applyImageWidth(img.getAttribute("src") || "", w);
  }
  document.addEventListener("mousemove", onMove);
  document.addEventListener("mouseup", onUp);
}

/** 把宽度写回札记正文：找到含该 src 的图片写法，替换 / 补上 `{w=N}` */
function applyImageWidth(src, w) {
  const d = WR.doc;
  if (!d || !src) return;
  const esc = src.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
  const re = new RegExp("!\\[([^\\]]*)\\]\\(" + esc + "\\)(\\s*\\{[^}\\n]*\\})?", "g");
  let hit = null;

  (d.entries || []).forEach(function (e) {
    const notes = e.notes || "";
    if (!notes || notes.indexOf(src) < 0) return;
    const next = notes.replace(re, function (_, alt, attr) {
      const rest = String(attr || "").replace(/[{}]/g, " ")
        .replace(/(?:^|\s)w(?:idth)?\s*=\s*\d+/gi, " ")
        .replace(/\s+/g, " ").trim();
      return "![" + alt + "](" + src + "){" + (rest ? rest + " w=" + w : "w=" + w) + "}";
    });
    if (next !== notes) { e.notes = next; hit = e; }
  });

  if (!hit) return;
  const ta = $("ent-notes");
  if (ta && hit.seq === WR.activeSeq) ta.value = hit.notes;
  markDirty(true);
  setSaveState("未保存");
  refreshPreview();
}

// ─── 核验（右栏「核验」+ 左栏区段计数） ────────────────────
//
// 规则在 `backend/verify.py`：抽构/参考抽构的格式、部件是否单独有记录、
// 引用页码是否越界。核验面板只放当前字，全库计数挂在左栏区段标签上。

async function refreshVerify() {
  const d = WR.doc;
  if (!d) return;
  let res = null;
  try {
    res = await wrGet("/verify/" + encodeURIComponent(d.char));
  } catch (e) { res = null; }
  if (!WR.doc || WR.doc.char !== d.char) return;   // 已经切到别的字了
  WR.verify = res;
  renderVerifyPanel();
  applyVerifyMarks();
  renderVerifyBadge();
}

async function loadVerifySummary() {
  try {
    WR.verifySummary = await wrGet("/verify");
  } catch (e) {
    WR.verifySummary = null;
  }
  renderBlockChips();
  renderVerifyTotal();
  renderCharList();
  renderVerifyPanel();
}

function renderVerifyTotal() {
  const total = (WR.verifySummary && WR.verifySummary.total) || 0;

  const badge = $("doc-verify-total");
  if (badge) {
    badge.style.display = total ? "" : "none";
    badge.textContent = total ? "核验 " + total : "";
    badge.title = total ? "全库共 " + total + " 处核验问题" : "";
  }

  const all = document.querySelector('.block-filter .blk-chip[data-block="__all__"]');
  if (all) {
    all.innerHTML = "全部" + (total
      ? '<span class="blk-err" title="全库 ' + total + ' 处核验问题">' + total + "</span>"
      : "");
  }
  // 区段 chip 的可点击性会随 innerHTML 变化丢失，这里重绑
  bindBlockChipClicks();
}

function renderVerifyBadge() {
  const n = (WR.verify && WR.verify.count) || 0;
  const bad = (WR.verify && WR.verify.error_count) || 0;

  const tab = $("tab-verify-badge");
  if (tab) {
    tab.style.display = n ? "" : "none";
    tab.textContent = String(n);
    tab.className = "tab-badge" + (bad ? " bad" : "");
  }

  const st = $("doc-verify-state");
  if (st) {
    st.textContent = n ? "核验 " + n + " 处" : "";
    st.className = "verify-state" + (n ? (bad ? " bad" : " warn") : "");
  }
}

function renderVerifyPanel() {
  const box = $("panel-verify");
  if (!box) return;
  const v = WR.verify;
  const issues = (v && v.issues) || [];
  const title = !v ? "未核验"
    : issues.length ? issues.length + " 处问题" : "没有发现问题";

  let html = '<div class="vf-head"><span class="vf-title">' + title + "</span>" +
    '<span class="we-spacer"></span>' +
    '<button class="btn-sm" id="vf-reload" title="重新核验">⟳</button></div>';

  html += issues.length
    ? issues.map(function (i) {
      const key = (WR.doc ? WR.doc.char : "") + "-" + i.seq;
      return '<div class="vf-item ' + MD.esc(i.level) + '" data-seq="' + i.seq + '">' +
        '<div class="vf-where"><code>' + MD.esc(key) + "</code>" +
        '<span class="vf-field">' + MD.esc(i.field_name || i.field) + "</span>" +
        '<span class="vf-code">' + MD.esc(i.code) + "</span></div>" +
        '<div class="vf-msg">' + MD.esc(i.message) + "</div></div>";
    }).join("")
    : '<div class="empty">这个字没有核验问题</div>';

  // 全局问题：文献引用键重复（不挂在某个字上）
  const dups = (WR.verifySummary && WR.verifySummary.ref_dups) || [];
  if (dups.length) {
    html += '<div class="vf-global"><div class="vf-g-title">引用键重复 ' + dups.length +
      " 个</div><ul>" + dups.map(function (d) {
        const srcs = (d.sources || []).join("、");
        return "<li><code>" + MD.esc(d.id) + "</code>" +
          (srcs ? "　" + MD.esc(srcs) : "") + "</li>";
      }).join("") + "</ul></div>";
  }

  box.innerHTML = html;

  const re = $("vf-reload");
  if (re) re.addEventListener("click", function () { refreshVerify(); });
  box.querySelectorAll(".vf-item").forEach(function (el) {
    el.addEventListener("click", function () {
      const seq = parseInt(el.getAttribute("data-seq"), 10);
      if (!seq || seq === WR.activeSeq) return;
      collectEntry();
      WR.activeSeq = seq;
      renderEditor();
    });
  });
}

/** 当前条有问题的字段标红 */
function applyVerifyMarks() {
  const issues = (WR.verify && WR.verify.issues) || [];
  const bad = {};
  issues.forEach(function (i) { if (i.seq === WR.activeSeq) bad[i.field] = true; });

  [["con", "ent-con"], ["ref_con", "ent-ref-con"], ["notes", "ent-notes"]].forEach(function (p) {
    const el = $(p[1]);
    if (el) el.classList.toggle("is-bad", !!bad[p[0]]);
  });
}

/** 该字所有条合并的 Markdown（预览用） */
function renderMarkdown(d) {
  const es = (d.entries || []).filter(function (e) { return e.seq > 0; });
  const lines = ["# " + d.char, ""];
  if (!es.length) {
    lines.push("（还没有条）");
    return lines.join("\n") + "\n";
  }
  // 抽构指向这个字的其它条（如 㞼 的 `=[丞]`）：本条没选字形时从它们增补
  const sources = d.ref_sources || [];
  const supplemented = {};
  const GLYPH_LINES = [["ob", "甲骨文", "ob"], ["bi", "金文", "bi"], ["xz", "小篆", "seal"]];
  es.forEach(function (e) {
    lines.push("## " + d.char + "-" + e.seq, "");
    if (e.con) lines.push("- 抽构：`" + e.con + "`");
    if (e.ref_con) lines.push("- 参考抽构：`" + e.ref_con + "`");
    GLYPH_LINES.forEach(function (g) {
      const key = g[0];
      let ids = (e[key] || []).slice();
      let from = [];
      if (!ids.length) {
        sources.forEach(function (s) {
          (s[key] || []).forEach(function (id) {
            const mark = key + ":" + id;
            if (ids.indexOf(id) >= 0 || supplemented[mark]) return;
            ids.push(id);
            supplemented[mark] = true;
            if (from.indexOf(s.char) < 0) from.push(s.char);
          });
        });
      }
      if (!ids.length) return;
      lines.push("- " + g[1] + "：" + ids.map(function (id) {
        return "[" + g[2] + ":" + id + "]";
      }).join("") + (from.length ? " > " + from.map(function (ch) {
        return "|" + ch + "|";
      }).join(" ") : ""));
    });
    if (e.con || e.ref_con || (e.ob && e.ob.length) ||
        (e.bi && e.bi.length) || (e.xz && e.xz.length)) lines.push("");
    if ((e.notes || "").trim()) { lines.push(e.notes.trim(), ""); }
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
  // 保存时也落规范写法（`⿱[九][乙]`），免得手快在格式化前就保存
  if (check.normalized) payload.con = check.normalized;
  if (payload.ref_con) {
    try {
      const rc = await wrSend("/shape/validate", { expr: payload.ref_con });
      if (rc.ok && rc.normalized) payload.ref_con = rc.normalized;
    } catch (e) { /* 参考抽构的报错交给后端 */ }
  }

  try {
    setSaveState("保存中…");
    const r = await wrSend("/entries/" + encodeURIComponent(d.char), {
      seq: WR.activeSeq || 0,
      con: payload.con || "",
      ref_con: payload.ref_con || "",
      ob: WR.obSel.slice(),
      bi: WR.biSel.slice(),
      xz: WR.xzSel.slice(),
      notes: payload.notes || "",
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
    refreshVerify();
    loadVerifySummary();
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
  refreshVerify();
  loadVerifySummary();
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

/** 在左侧字表里定位到某个字（翻到它所在的页，清掉搜索/区段过滤） */
function focusChar(ch) {
  if ($("doc-search").value.trim()) $("doc-search").value = "";
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
}

function gotoChar() {
  const c = window.prompt("跳到哪个字？");
  if (!c || !c.trim()) return;
  confirmLeave(function () { focusChar(c.trim()); });
}

/** 从别的视图（广义汉字）跳到某个字 */
function writerOpenChar(ch) {
  confirmLeave(function () { focusChar(ch); });
}

window.writerOpenChar = writerOpenChar;

// ─── 事件绑定 ────────────────────────────────────────────

/** 右侧面板切换：`refs`（文献） / `materials`（资料） / `verify`（核验） */
function switchRefTab(name) {
  if (name !== "materials" && name !== "verify") name = "refs";
  document.querySelectorAll("#view-write .ref-tab").forEach(function (t) {
    t.classList.toggle("active", t.getAttribute("data-panel") === name);
  });
  document.querySelectorAll("#view-write .ref-panel").forEach(function (p) {
    p.classList.toggle("active", p.id === "panel-" + name);
  });
  if (name === "refs" && window.REF && window.REF.init) window.REF.init();
}

window.switchRefTab = switchRefTab;

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
  $("doc-first-issue").addEventListener("click", jumpFirstIssue);

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
    tab.addEventListener("click", function () { switchRefTab(tab.getAttribute("data-panel")); });
  });

  // 预览里点 `[ref:C001.244-245+248]` → 右侧打开该文献
  const prev = $("doc-preview");
  if (prev) prev.addEventListener("click", function (ev) {
    const chip = ev.target.closest ? ev.target.closest(".md-reflink") : null;
    const id = chip && chip.getAttribute("data-ref");
    if (!id) return;
    ev.preventDefault();
    if (window.REF && window.REF.open) window.REF.open(id);
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
    loadVerifySummary();
  })();
}
