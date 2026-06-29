/**
 * 抽构标注管理 - 前端
 * 核心：con（抽构）/ ref（参考抽构）/ comm（注释）
 */

const API = "";

// ─── 状态 ────────────────────────────────────────────────
const state = {
  chars: [],
  charsTotal: 0,
  charsOffset: 0,
  charsLimit: 50,
  charQuery: "",
  unannotatedOnly: false,
  ob: [],
  obTotal: 0,
  obOffset: 0,
  obLimit: 100,
  papers: [],
};

// ─── 主题切换 ────────────────────────────────────────────
function initTheme() {
  const t = localStorage.getItem("theme");
  if (t === "light") {
    document.body.classList.add("light");
    document.getElementById("theme-toggle").textContent = "\u{1F319}";
  }
}
document.getElementById("theme-toggle").addEventListener("click", () => {
  const isLight = document.body.classList.toggle("light");
  localStorage.setItem("theme", isLight ? "light" : "dark");
  document.getElementById("theme-toggle").textContent = isLight ? "\u{1F319}" : "\u2600\uFE0F";
});

// ─── 导航 ────────────────────────────────────────────────
document.querySelectorAll(".nav-btn").forEach(btn => {
  btn.addEventListener("click", () => {
    document.querySelectorAll(".nav-btn").forEach(b => b.classList.remove("active"));
    btn.classList.add("active");
    document.querySelectorAll(".view").forEach(v => v.classList.remove("active"));
    const v = document.getElementById("view-" + btn.dataset.view);
    if (v) v.classList.add("active");
    const view = btn.dataset.view;
    if (view === "chars") loadChars();
    else if (view === "browse-ob") loadOB();
    else if (view === "papers") loadPapers();
    else if (view === "extra") loadExtra();
  });
});

// ─── API ─────────────────────────────────────────────────
async function api(path) {
  const r = await fetch(API + "/api" + path);
  if (!r.ok) throw new Error("API error: " + r.status);
  return r.json();
}
async function apiPost(path, body) {
  const r = await fetch(API + "/api" + path, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!r.ok) throw new Error("API error: " + r.status);
  return r.json();
}

// ═══════════════════════════════════════════════════════════
//  标注视图
// ═══════════════════════════════════════════════════════════

async function loadChars() {
  const q = document.getElementById("char-search").value.trim();
  const limit = state.charsLimit;
  const offset = state.charsOffset;
  let path;
  if (state.unannotatedOnly) {
    path = "/characters/search?unannotated=true&limit=" + limit + "&offset=" + offset;
  } else if (q) {
    path = "/characters/search?q=" + encodeURIComponent(q) + "&limit=" + limit + "&offset=" + offset;
  } else {
    path = "/characters/search?limit=" + limit + "&offset=" + offset;
  }
  const data = await api(path);
  state.chars = data.results || [];
  state.charsTotal = data.total || 0;
  renderChars();
}

function renderChars() {
  const container = document.getElementById("char-list");
  const countEl = document.getElementById("char-count");
  countEl.textContent = state.unannotatedOnly
    ? "\u672A\u6807\u6CE8\uFF1A" + state.charsTotal + " \u6761"
    : state.charsTotal + " \u6761";
  if (!state.chars.length) {
    container.innerHTML = '<div class="empty">\u6682\u65E0\u6570\u636E</div>';
    return;
  }
  container.innerHTML = state.chars.map(function(c) {
    var annos = c.annotations || [];
    var has = annos.some(function(a) { return a.con || a.ref || a.comm; });
    var firstComm = (annos[0] && annos[0].comm) || "";
    var cons = annos.map(function(a) { return a.con; }).filter(Boolean);
    return '<div class="char-card" onclick="showCharDetail(\'' + esc(c.char) + '\')">'
      + '<div class="char-glyph">' + c.char + '</div>'
      + '<div class="char-cp">' + (c.codepoint || "") + '</div>'
      + (cons.length ? '<div class="anno-summary">' + cons.map(function(x) { return '<span class="anno-tag has">' + esc(x) + '</span>'; }).join('') + '</div>' : '<div class="anno-summary"><span class="anno-tag empty">\u672A\u6807</span></div>')
      + '<div class="char-comm">' + esc(firstComm) + '</div>'
      + '</div>';
  }).join("");

  renderPagination("char-pagination", state.charsTotal, state.charsLimit, state.charsOffset, function(off) {
    state.charsOffset = off;
    loadChars();
  });
}

document.getElementById("char-search-btn").addEventListener("click", function() {
  state.unannotatedOnly = false;
  state.charsOffset = 0;
  loadChars();
});
document.getElementById("char-search").addEventListener("keydown", function(e) {
  if (e.key === "Enter") {
    state.unannotatedOnly = false;
    state.charsOffset = 0;
    loadChars();
  }
});

document.getElementById("first-unanno-btn").addEventListener("click", async function() {
  state.unannotatedOnly = true;
  state.charsOffset = 0;
  var data = await api("/characters/first-unannotated");
  if (data.char) {
    showCharDetail(data.char);
  } else {
    alert("\u6240\u6709\u5B57\u7B26\u90FD\u5DF2\u6807\u6CE8\uFF01");
  }
});

// ═══════════════════════════════════════════════════════════
//  字符详情（标注页面：上半标注 / 下半参考资料）
// ═══════════════════════════════════════════════════════════

var _currentDetailChar = null;var _currentDetailType = "char"; // "char" | "ob"
async function showCharDetail(char) {
  _currentDetailChar = char;
  _currentDetailType = "char";
  // 切换到标注页面
  document.querySelectorAll(".nav-btn").forEach(function(b) { b.classList.remove("active"); });
  document.querySelectorAll(".view").forEach(function(v) { v.classList.remove("active"); });
  document.getElementById("view-annotate").classList.add("active");
  document.querySelector('[data-view="annotate"]').classList.add("active");

  document.getElementById("anno-char-label").textContent = char;

  // 确保参考文献已加载
  if (!state.papers || !state.papers.length) {
    var pp = await api("/papers");
    state.papers = pp.papers || [];
  }
  if (!state.gyPapers) {
    var gp = await api("/gy/references");
    state.gyPapers = gp.references || [];
  }

  var [data, xref, neighbors] = await Promise.all([
    api("/characters/" + encodeURIComponent(char)),
    api("/characters/" + encodeURIComponent(char) + "/cross-refs"),
    api("/characters/" + encodeURIComponent(char) + "/neighbors"),
  ]);
  var annos = data.annotations || [];

  // 更新导航按钮
  state.neighbors = neighbors;
  document.getElementById("anno-prev-btn").style.display = neighbors.prev ? "" : "none";
  document.getElementById("anno-next-btn").style.display = neighbors.next ? "" : "none";

  var body = document.getElementById("detail-body");
  body.innerHTML = '<div class="detail-cols">'
    + renderDetailLeft(char, data, annos)
    + renderDetailRight(char, xref)
    + '</div>';

  // 初始化参考文献筛选
  filterRefs();
}

// 上一字 / 下一字
document.getElementById("anno-prev-btn").addEventListener("click", function() {
  if (_currentDetailType === "ob") return;
  if (state.neighbors && state.neighbors.prev) showCharDetail(state.neighbors.prev);
});
document.getElementById("anno-next-btn").addEventListener("click", function() {
  if (_currentDetailType === "ob") return;
  if (state.neighbors && state.neighbors.next) showCharDetail(state.neighbors.next);
});

function renderDetailLeft(char, data, annos) {
  var html = '<div class="detail-left-panel">'
    // 字符信息
    + '<div class="detail-header">'
    + '<span class="big-glyph">' + data.char + '</span>'
    + '<div class="cp">' + (data.codepoint || "") + '</div></div>'
    // 标注列表
    + '<div class="detail-section"><h4>标注 (' + annos.length + ')</h4>';

  if (!annos.length) {
    html += '<div class="empty">暂无标注</div>';
  } else {
    for (var i = 0; i < annos.length; i++) {
      var a = annos[i];
      html += '<div class="anno-card" id="anno-card-' + i + '">'
        + '<div class="field"><span class="field-label">抽构 (con)</span>'
        + '<input class="field-input" id="edit-con-' + i + '" value="' + esc(a.con || '') + '"></div>'
        + '<div class="field"><span class="field-label">参考抽构 (ref)</span>'
        + '<input class="field-input" id="edit-ref-' + i + '" value="' + esc(a.ref || '') + '"></div>'
        + '<div class="field"><span class="field-label">注释 (comm) <span class="hint">输入关键词筛选参考文献</span></span>'
        + '<textarea class="field-input" id="edit-comm-' + i + '" rows="2" oninput="filterRefsFor(' + i + ')">' + esc(a.comm || '') + '</textarea></div>'
        + '<div class="ref-filter-row">'
        + '<input class="ref-filter-input" id="edit-ref-filter-' + i + '" placeholder="筛选参考文献…" oninput="filterRefsFor(' + i + ')">'
        + '</div>'
        + '<div id="edit-ref-suggestions-' + i + '" class="ref-suggestions"></div>'
        + '<div class="actions">'
        + '<button class="btn-sm" onclick="saveAnno(' + i + ')">保存</button>'
        + '<button class="btn-sm btn-danger" onclick="deleteAnno(' + i + ')">删除</button>'
        + '</div></div>';
    }
  }

  // 添加新标注
  html += '<div class="anno-add-inline"><h4>+ 添加新标注</h4>'
    + '<div class="field"><span class="field-label">抽构 (con) <span class="hint">如 *考、=其</span></span>'
    + '<input class="field-input" id="new-con" placeholder="抽构"></div>'
    + '<div class="field"><span class="field-label">参考抽构 (ref)</span>'
    + '<input class="field-input" id="new-ref" placeholder="参考抽构"></div>'
    + '<div class="field"><span class="field-label">注释 (comm) <span class="hint">输入作者/关键词筛选参考文献</span></span>'
    + '<textarea class="field-input" id="new-comm" rows="2" placeholder="注释" oninput="filterRefs()"></textarea></div>'
    + '<div class="ref-filter-row">'
    + '<input class="ref-filter-input" id="ref-filter" placeholder="筛选参考文献…" oninput="filterRefs()">'
    + '</div>'
    + '<div id="new-ref-suggestions" class="ref-suggestions"></div>'
    + '<button class="btn-primary btn-sm" onclick="addNewAnno()">保存</button>'
    + '</div>'
    + '</div></div>';

  return html;
}

function renderDetailRight(char, xref) {
  var keys = Object.keys(xref);
  var html = '<div class="detail-right-panel">'
    + '<h4>参考资料</h4>'
    + '<div class="xref-stack">';

  if (!keys.length) {
    html += '<div class="empty">暂无其他数据</div>';
  } else {
    // guangyun（跳过小韻表）
    if (xref.guangyun) {
      xref.guangyun.forEach(function(g) {
        if (g.table === "rhyme_table") return;
        html += '<div class="xref-card"><div class="xref-title">'
          + (g.table === "full_table" ? "廣韻·全聲系" : g.table === "special_table" ? "廣韻·特殊字" : "廣韻·小韻")
          + '</div>';
        html += '<div class="xref-row"><span class="xref-label">声首</span><span class="xref-val">' + esc(g.shengshou) + '</span></div>'
          + (g.xiesheng_domain ? '<div class="xref-row"><span class="xref-label">谐声域</span><span class="xref-val xref-series">' + esc(g.xiesheng_domain) + '</span></div>' : '')
          + (g.secondary ? '<div class="xref-row"><span class="xref-label">D列</span><span class="xref-val">' + esc(g.secondary) + '</span></div>' : '')
          + '<div class="xref-row"><span class="xref-label">韵</span><span class="xref-val">' + esc(g.status) + '</span></div>'
          + (g.type ? '<div class="xref-row"><span class="xref-label">类型</span><span class="xref-val">' + esc(g.type) + '</span></div>' : '')
          + '<div class="xref-row"><span class="xref-label">反切</span><span class="xref-val">' + esc(g.qieyu) + '切 (' + esc(g.qiepin) + ')</span></div>'
          + (g.chars_raw ? '<div class="xref-row"><span class="xref-label">列字</span><span class="xref-val xref-sm">' + esc(g.chars_raw) + '</span></div>' : '');
        // corrections
        var ckeys = Object.keys(g.corrections || {});
        if (ckeys.length) {
          html += '<div class="xref-row"><span class="xref-label">校改</span><span class="xref-val">';
          ckeys.forEach(function(k) {
            html += esc(k) + "→" + esc(g.corrections[k]) + " ";
          });
          html += '</span></div>';
        }
        // notes
        if (g.notes_raw) {
          html += '<div class="xref-row"><span class="xref-label">备注</span><span class="xref-val xref-note">' + esc(g.notes_raw.substring(0, 400)) + '</span></div>';
        }
        html += '</div>';
      });
    }
    // shanggu
    if (xref.shanggu) {
      var s = xref.shanggu;
      html += '<div class="xref-card"><div class="xref-title">上古音</div>'
        + '<div class="xref-row"><span class="xref-label">读法</span><span class="xref-val">' + esc(s.reading || '') + '</span></div>'
        + '<div class="xref-row"><span class="xref-label">拼音</span><span class="xref-val">' + esc(s.pinyin || '') + '</span></div>'
        + '<div class="xref-row"><span class="xref-label">谐声</span><span class="xref-val">' + esc(s.xiesheng || '') + '</span></div>'
        + (s.meaning ? '<div class="xref-row"><span class="xref-label">释义</span><span class="xref-val xref-meaning">' + esc(s.meaning.substring(0, 300)) + '</span></div>' : '')
        + '</div>';
    }
    // unify_eiso
    if (xref.unify_eiso) {
      html += '<div class="xref-card"><div class="xref-title">异体统一 (EISO)</div>';
      xref.unify_eiso.forEach(function(u) {
        html += '<div class="xref-row"><span class="xref-label">组</span><span class="xref-val">' + esc(u.group) + '</span></div>'
          + '<div class="xref-row"><span class="xref-label">状态</span><span class="xref-val">' + esc(u.label) + '</span></div>';
      });
      html += '</div>';
    }
    // similar_fei
    if (xref.similar_fei) {
      html += '<div class="xref-card"><div class="xref-title">疑似字</div>';
      xref.similar_fei.forEach(function(f) {
        html += '<div class="xref-row"><span class="xref-label">组</span><span class="xref-val">' + esc(f.group) + '</span></div>'
          + '<div class="xref-row"><span class="xref-label">状态</span><span class="xref-val">' + esc(f.label) + '</span></div>';
      });
      html += '</div>';
    }
    // ies
    if (xref.ies) {
      html += '<div class="xref-card"><div class="xref-title">IES</div><div class="xref-val">' + esc(xref.ies) + '</div></div>';
    }
    // jianhuazi
    if (xref.jianhuazi) {
      var j = xref.jianhuazi;
      html += '<div class="xref-card"><div class="xref-title">简化字</div>'
        + '<div class="xref-row"><span class="xref-label">简体</span><span class="xref-val">' + esc(j.simplified || '') + '</span></div>'
        + '<div class="xref-row"><span class="xref-label">繁体</span><span class="xref-val">' + esc(j.traditional || '') + '</span></div>'
        + (j.comment ? '<div class="xref-row"><span class="xref-label">注</span><span class="xref-val">' + esc(j.comment) + '</span></div>' : '')
        + '</div>';
    }
  }

  html += '</div></div>';
  return html;
}

// ─── 标注操作 ─────────────────────────────────────────

async function addNewAnno() {
  var char = _currentDetailChar;
  var con = document.getElementById("new-con").value;
  var ref = document.getElementById("new-ref").value;
  var comm = document.getElementById("new-comm").value;
  if (!con && !ref && !comm) return;
  await apiPost("/characters/annotate", { char: char, con: con, ref: ref, comm: comm });
  loadChars();
  // 跳到下一字
  if (state.neighbors && state.neighbors.next) {
    showCharDetail(state.neighbors.next);
  } else {
    showCharDetail(char);
  }
}

async function saveAnno(idx) {
  var char = _currentDetailChar;
  var con = document.getElementById("edit-con-" + idx).value;
  var ref = document.getElementById("edit-ref-" + idx).value;
  var comm = document.getElementById("edit-comm-" + idx).value;
  await apiPost("/characters/annotate/update", { char: char, index: idx, con: con, ref: ref, comm: comm });
  loadChars();
  showCharDetail(char);
}

async function deleteAnno(idx) {
  if (!confirm("确定删除这条标注？")) return;
  var char = _currentDetailChar;
  await apiPost("/characters/annotate/delete", { char: char, index: idx });
  showCharDetail(char);
  loadChars();
}

// 插入文献引用
function insertRefTag(id) {
  var ta = document.getElementById("new-comm");
  if (ta) {
    ta.value += (ta.value ? "；" : "") + "参：" + id;
    ta.focus();
  }
}

// 筛选参考文献（添加新标注）
function filterRefs() {
  var filterVal = document.getElementById("ref-filter").value.trim().toLowerCase();
  var commVal = document.getElementById("new-comm").value.toLowerCase();
  var keyword = filterVal || commVal || "";
  var sugg = document.getElementById("new-ref-suggestions");
  if (!sugg) return;

  var allRefs = buildRefList();
  if (!keyword) {
    sugg.innerHTML = '<span class="ref-hint">输入关键词筛选参考文献</span>';
    return;
  }
  var matched = allRefs.filter(function(r) {
    var text = (r.id + " " + r.label + " " + r.author).toLowerCase();
    return text.indexOf(keyword) !== -1;
  });
  if (!matched.length) {
    sugg.innerHTML = '<span class="ref-hint">无匹配</span>';
    return;
  }
  sugg.innerHTML = matched.slice(0, 20).map(function(r) {
    return '<span class="ref-tag" onclick="insertRefTag(\'' + r.id + '\')">' + esc(r.id + " " + r.label.substring(0, 80)) + '</span>';
  }).join("");
}

// 编辑标注的参考文献筛选
function filterRefsFor(idx) {
  var filterVal = document.getElementById("edit-ref-filter-" + idx).value.trim().toLowerCase();
  var commVal = document.getElementById("edit-comm-" + idx).value.toLowerCase();
  var keyword = filterVal || commVal || "";
  var sugg = document.getElementById("edit-ref-suggestions-" + idx);
  if (!sugg) return;

  var allRefs = buildRefList();
  if (!keyword) {
    sugg.innerHTML = '<span class="ref-hint">输入关键词筛选参考文献</span>';
    return;
  }
  var matched = allRefs.filter(function(r) {
    var text = (r.id + " " + r.label + " " + r.author).toLowerCase();
    return text.indexOf(keyword) !== -1;
  });
  if (!matched.length) {
    sugg.innerHTML = '<span class="ref-hint">无匹配</span>';
    return;
  }
  sugg.innerHTML = matched.slice(0, 20).map(function(r) {
    return '<span class="ref-tag" onclick="insertEditRefTag(' + idx + ',\'' + r.id + '\')">' + esc(r.id + " " + r.label.substring(0, 80)) + '</span>';
  }).join("");
}

function insertEditRefTag(idx, id) {
  var ta = document.getElementById("edit-comm-" + idx);
  if (ta) {
    ta.value += (ta.value ? "；" : "") + "参：" + id;
    ta.focus();
  }
}

function buildRefList() {
  var allRefs = (state.papers || []).map(function(p) {
    return { id: p.id, label: p.citation || p.raw_title || p.id, author: p.author || "" };
  });
  (state.gyPapers || []).forEach(function(g, idx) {
    var gid = "GY" + String(idx + 1).padStart(3, "0");
    if (!allRefs.some(function(r) { return r.id === gid; })) {
      allRefs.push({ id: gid, label: (g.author || "") + " " + (g.title || ""), author: g.author || "" });
    }
  });
  return allRefs;
}

// ═══════════════════════════════════════════════════════════
//  参考文献
// ═══════════════════════════════════════════════════════════

async function loadPapers() {
  var q = document.getElementById("paper-search").value.trim();
  var data = q ? await api("/papers/search?q=" + encodeURIComponent(q)) : await api("/papers");
  state.papers = data.papers || [];
  var container = document.getElementById("paper-list");
  document.getElementById("paper-count").textContent = state.papers.length + " \u6761";
  if (!state.papers.length) { container.innerHTML = '<div class="empty">\u6682\u65E0\u6570\u636E</div>'; return; }
  container.innerHTML = state.papers.map(function(p) {
    return '<div class="paper-item">'
      + '<span class="paper-id">' + esc(p.id) + '</span>'
      + '<span class="paper-title">' + esc(p.citation || p.raw_title || '') + '</span>'
      + (p.url ? '<div class="paper-url"><a href="' + esc(p.url) + '" target="_blank">' + esc(p.url) + '</a></div>' : "")
      + '</div>';
  }).join("");
}
document.getElementById("paper-search").addEventListener("input", loadPapers);

// ═══════════════════════════════════════════════════════════
//  甲骨文
// ═══════════════════════════════════════════════════════════

async function loadOB() {
  var q = document.getElementById("ob-search").value.trim();
  var data = q
    ? await api("/ob/search?q=" + encodeURIComponent(q) + "&limit=" + state.obLimit + "&offset=" + state.obOffset)
    : await api("/ob/search?limit=" + state.obLimit + "&offset=" + state.obOffset);
  state.ob = data.results || [];
  state.obTotal = data.total || 0;
  renderOB();
}

function renderOB() {
  var container = document.getElementById("ob-list");
  document.getElementById("ob-count").textContent = state.obTotal + " \u6761";
  if (!state.ob.length) { container.innerHTML = '<div class="empty">\u6682\u65E0\u6570\u636E</div>'; return; }
  container.innerHTML = state.ob.map(function(o) {
    var annos = o.annotations || [];
    var firstComm = (annos[0] && annos[0].comm) || "";
    var cons = annos.map(function(a) { return a.con; }).filter(Boolean);
    return '<div class="char-card" onclick="showOBDetail(\'' + esc(o.num) + '\')">'
      + '<div class="char-glyph ob-glyph">' + o.glyph + '</div>'
      + '<div class="char-cp">' + esc(o.num) + '</div>'
      + (cons.length ? '<div class="anno-summary">' + cons.map(function(x) { return '<span class="anno-tag has">' + esc(x) + '</span>'; }).join('') + '</div>' : '<div class="anno-summary"><span class="anno-tag empty">\u672A\u6807</span></div>')
      + '<div class="char-comm">' + esc(firstComm) + '</div>'
      + '</div>';
  }).join("");
  renderPagination("ob-pagination", state.obTotal, state.obLimit, state.obOffset, function(off) {
    state.obOffset = off; loadOB();
  });
}

// ─── OB 标注详情（跳转到标注页面） ──────────────────────

async function showOBDetail(num) {
  // 切换到标注页面
  document.querySelectorAll(".nav-btn").forEach(function(b) { b.classList.remove("active"); });
  document.querySelectorAll(".view").forEach(function(v) { v.classList.remove("active"); });
  document.getElementById("view-annotate").classList.add("active");
  document.querySelector('[data-view="annotate"]').classList.add("active");

  // 获取 OB 数据
  var data = await api("/ob/search?q=" + encodeURIComponent(num) + "&limit=1&offset=0");
  var entry = data.results && data.results[0];
  if (!entry) return;

  _currentDetailChar = num;
  _currentDetailType = "ob";
  document.getElementById("anno-char-label").textContent = entry.num;

  // 隐藏预览/后翻按钮（OB 暂不支持）
  document.getElementById("anno-prev-btn").style.display = "none";
  document.getElementById("anno-next-btn").style.display = "none";

  // 确保参考文献已加载
  if (!state.papers || !state.papers.length) {
    var pp = await api("/papers");
    state.papers = pp.papers || [];
  }
  if (!state.gyPapers) {
    var gp = await api("/gy/references");
    state.gyPapers = gp.references || [];
  }

  var annos = entry.annotations || [];
  var body = document.getElementById("detail-body");
  body.innerHTML = '<div class="detail-cols">'
    + renderOBLeft(entry, annos)
    + renderDetailRight(entry.num, {})
    + '</div>';
  filterRefs();
}

function renderOBLeft(entry, annos) {
  var html = '<div class="detail-left-panel">'
    + '<div class="detail-header">'
    + '<span class="ob-glyph" style="font-size:56px">' + entry.glyph + '</span>'
    + '<div class="cp">' + esc(entry.num) + '</div></div>'
    + '<div class="detail-section"><h4>标注 (' + annos.length + ')</h4>';

  if (!annos.length) {
    html += '<div class="empty">暂无标注</div>';
  } else {
    for (var i = 0; i < annos.length; i++) {
      var a = annos[i];
      html += '<div class="anno-card" id="anno-card-' + i + '">'
        + '<div class="field"><span class="field-label">抽构 (con)</span>'
        + '<input class="field-input" id="edit-con-' + i + '" value="' + esc(a.con || '') + '"></div>'
        + '<div class="field"><span class="field-label">参考抽构 (ref)</span>'
        + '<input class="field-input" id="edit-ref-' + i + '" value="' + esc(a.ref || '') + '"></div>'
        + '<div class="field"><span class="field-label">注释 (comm) <span class="hint">输入关键词筛选参考文献</span></span>'
        + '<textarea class="field-input" id="edit-comm-' + i + '" rows="2" oninput="filterRefsFor(' + i + ')">' + esc(a.comm || '') + '</textarea></div>'
        + '<div class="ref-filter-row">'
        + '<input class="ref-filter-input" id="edit-ref-filter-' + i + '" placeholder="筛选参考文献…" oninput="filterRefsFor(' + i + ')">'
        + '</div>'
        + '<div id="edit-ref-suggestions-' + i + '" class="ref-suggestions"></div>'
        + '<div class="actions">'
        + '<button class="btn-sm" onclick="obSaveAnno(' + i + ')">保存</button>'
        + '<button class="btn-sm btn-danger" onclick="obDeleteAnno(' + i + ')">删除</button>'
        + '</div></div>';
    }
  }

  html += '<div class="anno-add-inline"><h4>+ 添加新标注</h4>'
    + '<div class="field"><span class="field-label">抽构 (con) <span class="hint">如 *考、=其</span></span>'
    + '<input class="field-input" id="new-con" placeholder="抽构"></div>'
    + '<div class="field"><span class="field-label">参考抽构 (ref)</span>'
    + '<input class="field-input" id="new-ref" placeholder="参考抽构"></div>'
    + '<div class="field"><span class="field-label">注释 (comm) <span class="hint">输入作者/关键词筛选参考文献</span></span>'
    + '<textarea class="field-input" id="new-comm" rows="2" placeholder="注释" oninput="filterRefs()"></textarea></div>'
    + '<div class="ref-filter-row">'
    + '<input class="ref-filter-input" id="ref-filter" placeholder="筛选参考文献…" oninput="filterRefs()">'
    + '</div>'
    + '<div id="new-ref-suggestions" class="ref-suggestions"></div>'
    + '<button class="btn-primary btn-sm" onclick="obAddAnno()">保存</button>'
    + '</div>'
    + '</div></div>';

  return html;
}

async function obAddAnno() {
  var num = _currentDetailChar;
  var con = document.getElementById("new-con").value;
  var ref = document.getElementById("new-ref").value;
  var comm = document.getElementById("new-comm").value;
  if (!con && !ref && !comm) return;
  await apiPost("/ob/annotate", { num: num, con: con, ref: ref, comm: comm });
  showOBDetail(num);
  loadOB();
}

async function obSaveAnno(idx) {
  var num = _currentDetailChar;
  var con = document.getElementById("edit-con-" + idx).value;
  var ref = document.getElementById("edit-ref-" + idx).value;
  var comm = document.getElementById("edit-comm-" + idx).value;
  await apiPost("/ob/annotate/update", { num: num, index: idx, con: con, ref: ref, comm: comm });
  showOBDetail(num);
  loadOB();
}

async function obDeleteAnno(idx) {
  if (!confirm("确定删除这条标注？")) return;
  var num = _currentDetailChar;
  await apiPost("/ob/annotate/delete", { num: num, index: idx });
  showOBDetail(num);
  loadOB();
}
document.getElementById("ob-search-btn").addEventListener("click", function() { state.obOffset = 0; loadOB(); });
document.getElementById("ob-search").addEventListener("keydown", function(e) { if (e.key === "Enter") { state.obOffset = 0; loadOB(); } });

// ═══════════════════════════════════════════════════════════
//  未编码字
// ═══════════════════════════════════════════════════════════

async function loadExtra() {
  var data = await api("/extra");
  var items = data.extra || [];
  var container = document.getElementById("extra-list");
  if (!items.length) { container.innerHTML = '<div class="empty">\u6682\u65E0\u6570\u636E</div>'; return; }
  container.innerHTML = items.map(function(e) {
    return '<div class="anno-card">'
      + '<div class="field"><span class="field-label">\u62BD\u6784\uFF1A</span><span>' + esc(e.con) + '</span></div>'
      + '<div class="field"><span class="field-label">\u53C2\u8003\uFF1A</span><span>' + esc(e.ref) + '</span></div>'
      + '<div class="field"><span class="field-label">\u6CE8\u91CA\uFF1A</span><span>' + esc(e.comm) + '</span></div>'
      + '</div>';
  }).join("");
}
document.getElementById("extra-add-btn").addEventListener("click", function() {
  document.getElementById("extra-add-overlay").style.display = "flex";
});
document.getElementById("extra-add-close").addEventListener("click", function() {
  document.getElementById("extra-add-overlay").style.display = "none";
});
document.getElementById("extra-form").addEventListener("submit", async function(e) {
  e.preventDefault();
  var con = document.getElementById("extra-con").value;
  var ref = document.getElementById("extra-ref").value;
  var comm = document.getElementById("extra-comm").value;
  await apiPost("/extra", { con: con, ref: ref, comm: comm });
  document.getElementById("extra-add-overlay").style.display = "none";
  document.getElementById("extra-con").value = "";
  document.getElementById("extra-ref").value = "";
  document.getElementById("extra-comm").value = "";
  loadExtra();
});

// ═══════════════════════════════════════════════════════════
//  工具
// ═══════════════════════════════════════════════════════════

function esc(s) {
  if (!s) return "";
  var d = document.createElement("div");
  d.textContent = s;
  return d.innerHTML;
}

function renderPagination(containerId, total, limit, offset, onClick) {
  var totalPages = Math.ceil(total / limit);
  var cur = Math.floor(offset / limit) + 1;
  var container = document.getElementById(containerId);
  if (totalPages <= 1) { container.innerHTML = ""; return; }
  var range = 3;
  var start = Math.max(1, cur - range);
  var end = Math.min(totalPages, cur + range);
  var html = '<div class="pagination-inner">';
  if (cur > 1) html += '<button data-p="' + (cur-1) + '">\u2039</button>';
  for (var i = start; i <= end; i++) {
    html += '<button class="' + (i === cur ? 'active' : '') + '" data-p="' + i + '">' + i + '</button>';
  }
  if (cur < totalPages) html += '<button data-p="' + (cur+1) + '">\u203A</button>';
  html += '<span>' + cur + '/' + totalPages + '</span></div>';
  container.innerHTML = html;
  container.querySelectorAll("button[data-p]").forEach(function(b) {
    b.addEventListener("click", function() {
      onClick((parseInt(b.getAttribute("data-p")) - 1) * limit);
    });
  });
}

// ═══════════════════════════════════════════════════════════
//  初始化
// ═══════════════════════════════════════════════════════════

initTheme();
loadChars();
loadPapers();
