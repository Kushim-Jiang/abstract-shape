const REF_FIELDS = [
  ["id", "引用键", "text", "key"],
  ["type", "类型", "type", "entrytype"],
  ["author", "作者", "list", "author"],
  ["editor", "编者", "list", "editor"],
  ["article_title", "篇名", "text", "title"],
  ["journal", "期刊", "text", "journal"],
  ["book_title", "书名 / 集名", "text", "booktitle"],
  ["publisher", "出版社", "text", "publisher"],
  ["location", "出版地", "text", "address"],
  ["year", "年", "text", "year"],
  ["date", "日期", "text", "date"],
  ["volume", "卷", "text", "volume"],
  ["number", "期", "text", "number"],
  ["pages", "页码", "text", "pages"],
  ["edition", "版次", "text", "edition"],
  ["url", "网址", "text", "url"],
  ["doi", "DOI", "text", "doi"],
  ["note", "备注", "multiline", "note"]
];

const REF = {
  list: [],
  current: null,
  filter: "",
  editing: false,
  initialized: false
};

async function loadRefs() {
  const d = await wrGet("/refs?q=" + encodeURIComponent(REF.filter));
  REF.list = d.refs || [];
  renderRefPanel();
}

function renderRefPanel() {
  const box = $("panel-refs");
  if (!box) return;

  if (REF.editing && REF.current) {
    box.innerHTML = renderRefForm(REF.current);
    bindRefForm();
    return;
  }

  const items = REF.list.map(function (r) {
    return '<div class="ref-item' + (r.id === (REF.current || {}).id ? " active" : "") +
      '" data-id="' + MD.esc(r.id) + '">' +
      '<div><span class="ri-id">' + MD.esc(r.id) + "</span>" +
      '<span class="ri-badge">' + MD.esc(refTypeName(r.type)) + "</span>" +
      (r._builtin ? '<span class="ri-badge">内置</span>' : "") + "</div>" +
      '<div class="ri-cite">' + MD.esc(r.citation || "") + "</div>" +
      "</div>";
  }).join("");

  box.innerHTML =
    '<div class="ref-search">' +
    '<input type="text" id="ref-filter" value="' + MD.esc(REF.filter) + '">' +
    "</div>" +
    '<div style="display:flex;gap:6px;margin:8px 0">' +
    '<button class="btn-primary btn-sm" id="ref-new">＋ 新增文献</button>' +
    '<button class="btn-sm" id="ref-reload">⟳</button>' +
    '<span class="badge" style="margin-left:auto">' + REF.list.length + "</span>" +
    "</div>" +
    '<div class="ref-list">' +
    (items || '<div class="empty">没有文献</div>') +
    "</div>";

  $("ref-filter").addEventListener("input", function () {
    clearTimeout(REF._t);
    const v = this.value;
    REF._t = setTimeout(function () { REF.filter = v; loadRefs(); }, 250);
  });
  $("ref-reload").addEventListener("click", loadRefs);
  $("ref-new").addEventListener("click", function () {
    REF.current = { id: "", type: "article", author: [], editor: [] };
    REF.editing = true;
    renderRefPanel();
  });
  box.querySelectorAll(".ref-item").forEach(function (el) {
    el.addEventListener("click", async function () {
      const id = el.getAttribute("data-id");
      REF.current = await wrGet("/refs/" + encodeURIComponent(id));
      REF.list.forEach(function (r) { if (r.id === id) REF.current.citation = r.citation; });
      REF.editing = true;
      renderRefPanel();
    });
  });
}

function refTypeName(t) {
  const m = { article: "期刊论文", book: "专著", incollection: "文集析出",
              inproceedings: "会议论文", thesis: "学位论文", report: "报告", misc: "其他" };
  return m[t] || t || "其他";
}

function renderRefForm(r) {
  const builtin = !!r.builtin;

  const fields = REF_FIELDS.map(function (f) {
    const key = f[0], label = f[1], kind = f[2], bib = f[3];
    if (key === "id") {
      return '<div class="ref-field"><label>' + label +
        ' <span class="bib">' + bib + "</span></label>" +
        '<input type="text" data-key="id" value="' + MD.esc(r.id || "") +
        '" ' + (builtin ? "disabled" : "") + "></div>";
    }
    if (kind === "type") {
      const opts = ["article", "book", "incollection", "inproceedings", "thesis", "report", "misc"]
        .map(function (t) {
          return '<option value="' + t + '"' + ((r.type || "misc") === t ? " selected" : "") +
            ">" + refTypeName(t) + " (" + t + ")</option>";
        }).join("");
      return '<div class="ref-field"><label>' + label +
        ' <span class="bib">' + bib + "</span></label>" +
        '<select data-key="type">' + opts + "</select></div>";
    }
    if (kind === "list") {
      const vals = (r[key] && r[key].length) ? r[key] : [""];
      const rows = vals.map(function (v) {
        return '<div class="ref-author-row">' +
          '<input type="text" data-list="' + key + '" value="' + MD.esc(v) +
          '" >' +
          '<button class="btn-sm ref-del-author">✕</button></div>';
      }).join("");
      return '<div class="ref-field"><label>' + label +
        ' <span class="bib">' + bib + "</span>" +
        '<span class="hint">可多个，一行一个</span></label>' +
        '<div class="ref-authors" data-for="' + key + '">' + rows + "</div>" +
        '<button class="btn-sm ref-add-author" data-for="' + key +
        '" style="align-self:flex-start">＋ 加一个</button></div>';
    }
    if (kind === "multiline") {
      return '<div class="ref-field"><label>' + label +
        ' <span class="bib">' + bib + "</span></label>" +
        '<textarea data-key="' + key + '" rows="3">' + MD.esc(r[key] || "") + "</textarea></div>";
    }
    return '<div class="ref-field"><label>' + label +
      ' <span class="bib">' + bib + "</span></label>" +
      '<input type="text" data-key="' + key + '" value="' + MD.esc(r[key] || "") + '"></div>';
  }).join("");

  // 把短字段两两并排
  const grouped =
    fieldByKey(fields, "id") + fieldByKey(fields, "type") +
    fieldByKey(fields, "author") + fieldByKey(fields, "editor") +
    fieldByKey(fields, "article_title") + fieldByKey(fields, "journal") +
    fieldByKey(fields, "book_title") +
    '<div class="ref-inline">' + fieldByKey(fields, "publisher") +
    fieldByKey(fields, "location") + "</div>" +
    '<div class="ref-inline">' + fieldByKey(fields, "year") +
    fieldByKey(fields, "date") + "</div>" +
    '<div class="ref-inline">' + fieldByKey(fields, "volume") +
    fieldByKey(fields, "number") + fieldByKey(fields, "pages") + "</div>" +
    fieldByKey(fields, "edition") + fieldByKey(fields, "url") +
    fieldByKey(fields, "doi") + fieldByKey(fields, "note");

  return '<div class="ref-form">' + grouped +
    '<div class="ref-form-actions">' +
    '<button class="btn-primary btn-sm" id="ref-save">保存</button>' +
    '<button class="btn-sm" id="ref-cancel">返回</button>' +
    (builtin
      ? '<span class="hint" style="color:var(--text2);font-size:11px">内置文献来自上游，保存会生成覆盖记录</span>'
      : (r.id ? '<button class="btn-sm btn-danger" id="ref-delete">删除</button>' : "")) +
    "</div>" +
    (r.id ? '<div class="ref-field"><label>BibTeX</label>' +
      '<div class="ref-bibtex">' + MD.esc(r.bibtex || toBibtexClient(r)) + "</div></div>" : "") +
    "</div>";
}

/** 从整段 HTML 里抠出某个字段的块（简单可靠：按 data-key 定位） */
function fieldByKey(fieldsHtml, key) {
  const openers = [
    '<div class="ref-field"><label>',
    '<div class="ref-field"><label>'
  ];
  // 逐个 field 块扫描（块之间不会嵌套 div.ref-field）
  let idx = 0;
  while (idx < fieldsHtml.length) {
    const start = fieldsHtml.indexOf('<div class="ref-field">', idx);
    if (start < 0) break;
    const next = fieldsHtml.indexOf('<div class="ref-field">', start + 10);
    const block = fieldsHtml.slice(start, next < 0 ? fieldsHtml.length : next);
    if (block.includes('data-key="' + key + '"') || block.includes('data-list="' + key + '"') ||
        block.includes('data-for="' + key + '"')) {
      return block;
    }
    if (next < 0) break;
    idx = next;
  }
  return "";
}

function collectRefForm() {
  const box = $("panel-refs");
  const rec = { id: "", type: "article", author: [], editor: [] };
  box.querySelectorAll("[data-key]").forEach(function (el) {
    rec[el.getAttribute("data-key")] = el.value.trim();
  });
  box.querySelectorAll(".ref-authors").forEach(function (wrap) {
    const key = wrap.getAttribute("data-for");
    rec[key] = [...wrap.querySelectorAll("input")].map(function (i) { return i.value.trim(); })
      .filter(Boolean);
  });
  return rec;
}

function bindRefForm() {
  const box = $("panel-refs");

  box.querySelectorAll(".ref-add-author").forEach(function (btn) {
    btn.addEventListener("click", function () {
      const key = btn.getAttribute("data-for");
      const wrap = box.querySelector('.ref-authors[data-for="' + key + '"]');
      const div = document.createElement("div");
      div.className = "ref-author-row";
      div.innerHTML = '<input type="text" data-list="' + key + '">' +
        '<button class="btn-sm ref-del-author" title="删除">✕</button>';
      wrap.appendChild(div);
      div.querySelector("input").focus();
      div.querySelector(".ref-del-author").addEventListener("click", function () { div.remove(); });
    });
  });
  box.querySelectorAll(".ref-del-author").forEach(function (btn) {
    btn.addEventListener("click", function () { btn.parentElement.remove(); });
  });

  $("ref-save").addEventListener("click", async function () {
    const rec = collectRefForm();
    if (!rec.author.length && !rec.article_title && !rec.book_title) {
      alert("至少填作者或标题");
      return;
    }
    try {
      const r = await wrSend("/refs", rec);
      REF.current = r.ref;
      REF.editing = false;
      await loadRefs();
      setSaveState("文献已保存", "ok");
      setTimeout(function () { setSaveState(""); }, 1600);
    } catch (e) {
      alert("保存失败：" + e.message);
    }
  });
  $("ref-cancel").addEventListener("click", function () {
    REF.editing = false;
    renderRefPanel();
  });
  const del = $("ref-delete");
  if (del) del.addEventListener("click", async function () {
    if (!confirm("删除文献 " + REF.current.id + "？")) return;
    try {
      await wrSend("/refs/" + encodeURIComponent(REF.current.id), undefined, "DELETE");
      REF.current = null;
      REF.editing = false;
      await loadRefs();
    } catch (e) { alert(e.message); }
  });
}

/** 客户端拼 BibTeX（内置文献没有后端 export 时的兜底） */
function toBibtexClient(r) {
  const lines = ["@" + (r.type || "misc") + "{" + (r.id || "") + ","];
  const bib = {};
  REF_FIELDS.forEach(function (f) { bib[f[0]] = f[3]; });
  Object.keys(bib).forEach(function (k) {
    if (k === "id" || k === "type") return;
    let v = r[k];
    if (Array.isArray(v)) v = v.join(" and ");
    if (!v) return;
    lines.push("  " + bib[k] + " = {" + v + "},");
  });
  lines.push("}");
  return lines.join("\n");
}

// ─── 对外入口 ─────────────────────────────────────────────

REF.init = function () {
  if (REF.initialized) return;
  REF.initialized = true;
  loadRefs().catch(function () {});
};

if (document.readyState === "loading") {
  document.addEventListener("DOMContentLoaded", function () { REF.init(); });
} else {
  REF.init();
}
