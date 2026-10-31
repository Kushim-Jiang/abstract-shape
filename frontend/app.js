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
  bi: [],
  biTotal: 0,
  biOffset: 0,
  biLimit: 100,
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
    if (view === "write") { if (typeof initWriter === "function") initWriter(); }
    else if (view === "chars") loadChars();
    else if (view === "browse-ob") loadOB();
    else if (view === "browse-bi") loadBI();
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
//  广义汉字（字表）
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
    return '<div class="char-card" onclick="openInWriter(\'' + esc(c.char) + '\')">'
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
    openInWriter(data.char);
  } else {
    alert("\u6240\u6709\u5B57\u7B26\u90FD\u5DF2\u6807\u6CE8\uFF01");
  }
});

/** 在「写作」视图里打开某个字（从别的视图跳过来） */
function openInWriter(ch) {
  var btn = document.querySelector('.nav-btn[data-view="write"]');
  if (btn) btn.click();
  if (typeof window.writerOpenChar === "function") window.writerOpenChar(ch);
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

// ─── 字形下的「汉字字形」标注 ──────────────────────────

function glyphStore(kind) { return kind === "ob" ? state.ob : state.bi; }
function glyphRender(kind) { if (kind === "ob") renderOB(); else renderBI(); }

/** 卡片下方的一排汉字字形小标签 + 添加按钮 */
function ziTagsHtml(kind, idx, annos) {
  var html = '<div class="zi-tags">';
  (annos || []).forEach(function(a, i) {
    if (!a.con) return;
    html += '<span class="zi-tag' + (a.ref ? ' has-ref' : '') + '" title="' + esc(a.ref || a.comm || "") + '">'
      + esc(a.con)
      + '<button class="zi-del" data-kind="' + kind + '" data-i="' + idx + '" data-ai="' + i + '" title="删除">&times;</button>'
      + '</span>';
  });
  html += '<button class="zi-add" data-kind="' + kind + '" data-i="' + idx + '" title="添加汉字字形">\uFF0B</button>';
  return html + '</div>';
}

/** 卡片容器上做事件代理（容器只创建一次，内容每次重绘） */
function bindGlyphCards(containerId, kind) {
  var box = document.getElementById(containerId);
  if (!box) return;
  box.addEventListener("click", function(ev) {
    var del = ev.target.closest(".zi-del");
    if (del) {
      ev.stopPropagation();
      delGlyphZi(kind, +del.getAttribute("data-i"), +del.getAttribute("data-ai"));
      return;
    }
    var add = ev.target.closest(".zi-add");
    if (add) {
      ev.stopPropagation();
      openZiInput(add, kind, +add.getAttribute("data-i"));
    }
  });
}

/** 把 ＋ 按钮换成输入框；回车保存，Esc 取消 */
function openZiInput(btn, kind, idx) {
  var input = document.createElement("input");
  input.className = "zi-input";
  input.setAttribute("placeholder", "\u6C49\u5B57\u5B57\u5F62");
  btn.parentNode.replaceChild(input, btn);
  input.focus();

  var done = false;
  function cancel() {
    if (done) return;
    done = true;
    glyphRender(kind);
  }
  async function commit() {
    if (done) return;
    var raw = input.value.trim();
    if (!raw) { cancel(); return; }
    done = true;
    var tokens = raw.split(/[\s,\uFF0C\u3001;\uFF1B]+/).filter(Boolean);
    for (var t = 0; t < tokens.length; t++) {
      await addGlyphZi(kind, idx, tokens[t]);
    }
    glyphRender(kind);
  }
  input.addEventListener("keydown", function(e) {
    if (e.isComposing) return;
    if (e.key === "Enter") { e.preventDefault(); commit(); }
    else if (e.key === "Escape") { e.preventDefault(); cancel(); }
  });
  input.addEventListener("blur", function() { commit(); });
}

async function addGlyphZi(kind, idx, con) {
  var item = glyphStore(kind)[idx];
  if (!item) return;
  var res = await apiPost("/" + kind + "/annotate", { num: item.num, glyph: item.glyph || "", con: con });
  if (res && res.annotations) item.annotations = res.annotations;
}

async function delGlyphZi(kind, idx, ai) {
  var item = glyphStore(kind)[idx];
  if (!item) return;
  var res = await apiPost("/" + kind + "/annotate/delete", { num: item.num, glyph: item.glyph || "", index: ai });
  if (res && res.annotations) item.annotations = res.annotations;
  glyphRender(kind);
}

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
  container.innerHTML = state.ob.map(function(o, i) {
    return '<div class="char-card glyph-card">'
      + '<div class="char-glyph ob-glyph">' + o.glyph + '</div>'
      + '<div class="char-cp">' + esc(o.num) + '</div>'
      + ziTagsHtml("ob", i, o.annotations)
      + '</div>';
  }).join("");
  renderPagination("ob-pagination", state.obTotal, state.obLimit, state.obOffset, function(off) {
    state.obOffset = off; loadOB();
  });
}

document.getElementById("ob-search-btn").addEventListener("click", function() { state.obOffset = 0; loadOB(); });
document.getElementById("ob-search").addEventListener("keydown", function(e) { if (e.key === "Enter") { state.obOffset = 0; loadOB(); } });

// ═══════════════════════════════════════════════════════════
//  金文
// ═══════════════════════════════════════════════════════════

async function loadBI() {
  var q = document.getElementById("bi-search").value.trim();
  var data = q
    ? await api("/bi/search?q=" + encodeURIComponent(q) + "&limit=" + state.biLimit + "&offset=" + state.biOffset)
    : await api("/bi/search?limit=" + state.biLimit + "&offset=" + state.biOffset);
  state.bi = data.results || [];
  state.biTotal = data.total || 0;
  renderBI();
}

function renderBI() {
  var container = document.getElementById("bi-list");
  document.getElementById("bi-count").textContent = state.biTotal + " \u6761";
  if (!state.bi.length) { container.innerHTML = '<div class="empty">\u6682\u65E0\u6570\u636E</div>'; return; }
  container.innerHTML = state.bi.map(function(b, i) {
    return '<div class="char-card glyph-card">'
      + '<div class="char-glyph bi-glyph">' + b.glyph + '</div>'
      + '<div class="char-cp">' + esc(b.num) + '</div>'
      + ziTagsHtml("bi", i, b.annotations)
      + '</div>';
  }).join("");
  renderPagination("bi-pagination", state.biTotal, state.biLimit, state.biOffset, function(off) {
    state.biOffset = off; loadBI();
  });
}

document.getElementById("bi-search-btn").addEventListener("click", function() { state.biOffset = 0; loadBI(); });
document.getElementById("bi-search").addEventListener("keydown", function(e) { if (e.key === "Enter") { state.biOffset = 0; loadBI(); } });

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
bindGlyphCards("ob-list", "ob");
bindGlyphCards("bi-list", "bi");
if (typeof initWriter === "function") initWriter();
