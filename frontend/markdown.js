/**
 * 抽构札记 - 轻量 Markdown 渲染器
 *
 * 目标：把 Markdown 渲染成「读起来像论文」的 HTML，同时保证
 * 渲染结果不会引入 XSS（先转义，再生成标签）。
 *
 * 支持：标题 / 粗体 / 斜体 / 行内代码 / 代码块 / 引用 / 有序无序列表 /
 *       任务列表 / 表格 / 分隔线 / 链接 / 图片 / 自动链接
 * 扩展：[[丂-1]] 跨札记引用、[[文献: ID]] 文献引用
 */

/** HTML 转义 */
function mdEsc(s) {
  return String(s == null ? "" : s)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#39;");
}

/** 行内元素解析（输入必须是已转义的文本） */
function mdInline(text, opts) {
  opts = opts || {};
  let s = text;

  // 行内代码 `code`（先抽出来，避免内部被其它规则改动）
  const codes = [];
  s = s.replace(/`([^`\n]+)`/g, function (_, c) {
    codes.push(c);
    return "\u0000C" + (codes.length - 1) + "\u0000";
  });

  // 跨札记引用 [[丂-1]] / [[丂-1-2]]（字符-序号，字符可含连字符时贪心匹配到最后的序号）
  s = s.replace(/\[\[\s*([^\[\]:：]+?)-(\d+)\s*\]\]/g, function (_, ch, n) {
    const ref = ch + "-" + n;
    return '<a class="md-noteref" href="#" data-ref="' + ref +
      '" title="引用札记 ' + ref + '">' + ref + "</a>";
  });

  // 文献引用 [[文献: ID]]（也兼容 [[参: ID]]）
  s = s.replace(/\[\[(?:文献|参)\s*[:：]\s*([^\]]+?)\]\]/g, function (_, id) {
    return '<span class="md-reflink" data-ref="' + id + '">[' + id + "]</span>";
  });

  // 图片 ![alt](src)
  s = s.replace(/!\[([^\]]*)\]\(([^)\s]+)\)/g, function (_, alt, src) {
    if (!/^(https?:|data:image)/i.test(src)) return esc0(alt) + " (" + esc0(src) + ")";
    return '<img src="' + src + '" alt="' + alt + '">';
  });

  // 链接 [text](url)
  s = s.replace(/\[([^\]]+)\]\(([^)\s]+)\)/g, function (_, txt, href) {
    const safe = /^javascript:/i.test(href) ? "#" : href;
    return '<a href="' + safe + '" target="_blank" rel="noopener noreferrer">' + txt + "</a>";
  });

  // 粗体 / 斜体 / 删除线
  s = s.replace(/\*\*([^*\n]+)\*\*/g, "<strong>$1</strong>");
  s = s.replace(/(^|[^*\w])\*([^*\n]+)\*/g, "$1<em>$2</em>");
  s = s.replace(/(^|[^_\w])_([^_\n]+)_/g, "$1<em>$2</em>");
  s = s.replace(/~~([^~\n]+)~~/g, "<del>$1</del>");

  // 还原行内代码
  s = s.replace(/\u0000C(\d+)\u0000/g, function (_, i) {
    return "<code>" + codes[+i] + "</code>";
  });

  return s;
}

function esc0(s) {
  return String(s == null ? "" : s);
}

/** 行内渲染入口：先转义，再解析 */
function mdInlineRaw(text, opts) {
  return mdInline(mdEsc(text), opts);
}

const MD = (function () {

  /** 渲染一个 Markdown 文本块为 HTML 片段（不含 <p> 包装） */
  function renderBody(text) {
    const lines = String(text == null ? "" : text).split("\n");
    const out = [];
    let i = 0;

    while (i < lines.length) {
      const line = lines[i];
      const trimmed = line.trim();

      // ── 空行 ──
      if (!trimmed) { i++; continue; }

      // ── 围栏代码块 ──
      const fence = trimmed.match(/^(```+|~~~+)\s*([\w+-]*)\s*$/);
      if (fence) {
        const marker = fence[1][0].repeat(3);
        const lang = fence[2];
        const buf = [];
        i++;
        while (i < lines.length && !lines[i].trim().startsWith(marker)) {
          buf.push(lines[i]);
          i++;
        }
        i++; // 跳过结束围栏
        out.push(
          "<pre><code" +
          (lang ? ' class="language-' + mdEsc(lang) + '"' : "") +
          ">" + mdEsc(buf.join("\n")) + "</code></pre>"
        );
        continue;
      }

      // ── 分隔线 ──
      if (/^(-{3,}|\*{3,}|_{3,})$/.test(trimmed)) {
        out.push("<hr>");
        i++;
        continue;
      }

      // ── 标题 ──
      const h = trimmed.match(/^(#{1,6})\s+(.*)$/);
      if (h) {
        const lvl = h[1].length;
        out.push("<h" + lvl + ">" + mdInlineRaw(h[2]) + "</h" + lvl + ">");
        i++;
        continue;
      }

      // ── 表格（第二行是 |---| 分隔）──
      if (trimmed.includes("|") && i + 1 < lines.length &&
          /^\s*\|?[\s:|-]+\|[\s:|-]*$/.test(lines[i + 1]) &&
          /-/.test(lines[i + 1])) {
        const head = splitRow(trimmed);
        const aligns = splitRow(lines[i + 1]).map(function (c) {
          const t = c.trim();
          if (/^:.*:$/.test(t)) return "center";
          if (/:$/.test(t)) return "right";
          if (/^:/.test(t)) return "left";
          return "";
        });
        i += 2;
        const rows = [];
        while (i < lines.length && lines[i].trim().includes("|")) {
          rows.push(splitRow(lines[i]));
          i++;
        }
        let html = "<table><thead><tr>";
        head.forEach(function (c, k) {
          html += "<th" + (aligns[k] ? ' style="text-align:' + aligns[k] + '"' : "") +
                  ">" + mdInlineRaw(c.trim()) + "</th>";
        });
        html += "</tr></thead><tbody>";
        rows.forEach(function (r) {
          html += "<tr>";
          for (let k = 0; k < head.length; k++) {
            html += "<td" + (aligns[k] ? ' style="text-align:' + aligns[k] + '"' : "") +
                    ">" + mdInlineRaw((r[k] || "").trim()) + "</td>";
          }
          html += "</tr>";
        });
        html += "</tbody></table>";
        out.push(html);
        continue;
      }

      // ── 引用 ──
      if (/^>\s?/.test(trimmed)) {
        const buf = [];
        while (i < lines.length && /^\s*>/.test(lines[i])) {
          buf.push(lines[i].replace(/^\s*>\s?/, ""));
          i++;
        }
        out.push("<blockquote>" + renderBody(buf.join("\n")) + "</blockquote>");
        continue;
      }

      // ── 列表 ──
      if (/^\s*([-*+]|\d+[.)])\s+/.test(line)) {
        const listHtml = renderList(lines, function () { return i; }, function (n) { i = n; });
        if (listHtml) { out.push(listHtml); continue; }
      }

      // ── 段落 ──
      const buf = [trimmed];
      i++;
      while (i < lines.length) {
        const t = lines[i].trim();
        if (!t) break;
        if (/^(#{1,6})\s/.test(t)) break;
        if (/^(```+|~~~+)/.test(t)) break;
        if (/^(-{3,}|\*{3,}|_{3,})$/.test(t)) break;
        if (/^>\s?/.test(t)) break;
        if (/^\s*([-*+]|\d+[.)])\s+/.test(lines[i])) break;
        buf.push(t);
        i++;
      }
      out.push("<p>" + buf.map(function (l) { return mdInlineRaw(l); }).join("<br>") + "</p>");
    }

    return out.join("\n");
  }

  /** 切分表格行 */
  function splitRow(line) {
    let s = line.trim();
    if (s.startsWith("|")) s = s.slice(1);
    if (s.endsWith("|")) s = s.slice(0, -1);
    return s.split("|");
  }

  /**
   * 渲染列表（支持嵌套与任务列表）。
   * getIdx/setIdx 用于回写主循环的游标。
   */
  function renderList(lines, getIdx, setIdx) {
    let i = getIdx();
    const first = lines[i].match(/^(\s*)([-*+]|\d+[.)])\s+(.*)$/);
    if (!first) return null;
    const baseIndent = first[1].length;
    const ordered = /\d/.test(first[2]);
    const items = [];

    while (i < lines.length) {
      const m = lines[i].match(/^(\s*)([-*+]|\d+[.)])\s+(.*)$/);
      if (!m) break;
      const indent = m[1].length;
      if (indent < baseIndent) break;
      if (indent > baseIndent) break; // 嵌套交给下一轮递归
      let content = m[3];
      let task = null;
      const tm = content.match(/^\[([ xX])\]\s+(.*)$/);
      if (tm) { task = tm[1].toLowerCase() === "x"; content = tm[2]; }
      i++;

      // 收集该项的续行（缩进更深的普通文本 / 子列表）
      const sub = [];
      while (i < lines.length) {
        const raw = lines[i];
        if (!raw.trim()) break;
        const nm = raw.match(/^(\s*)([-*+]|\d+[.)])\s+/);
        if (nm && nm[1].length > baseIndent) { sub.push(raw); i++; continue; }
        if (nm) break;
        if (raw.match(/^\s{2,}/)) { sub.push(raw.trim()); i++; continue; }
        break;
      }

      let inner = mdInlineRaw(content);
      if (sub.length) {
        const subHtml = renderBody(sub.map(function (l) { return l.replace(/^\s{2}/, "  "); }).join("\n"));
        inner += subHtml;
      }
      items.push({ task: task, html: inner });
    }

    setIdx(i);
    if (!items.length) return null;

    const tag = ordered ? "ol" : "ul";
    let html = "<" + tag + ">";
    items.forEach(function (it) {
      if (it.task === null) {
        html += "<li>" + it.html + "</li>";
      } else {
        html += '<li><input type="checkbox" class="md-check" disabled' +
                (it.task ? " checked" : "") + ">" + it.html + "</li>";
      }
    });
    html += "</" + tag + ">";
    return html;
  }

  /** 渲染整篇文档 */
  function render(text) {
    return renderBody(text);
  }

  return { render: render, renderBody: renderBody, inline: mdInlineRaw, esc: mdEsc };
})();
