/* ═══ 中西混排（只作用于渲染出来的文字）══════════════════════
   1) 汉字与西文/数字相邻时，自动留半个 en 空（0.25em），由 .tw-lat 的
      左右 margin 实现——不插入任何字符，复制出去仍是原文；
   2) 标点挤压：除 。！？ 与破折号 ——、省略号 …… 之外，标点一律压成
      半角（字身框 1em → 0.5em），字形整体居中进新的半角框：
        margin-left  = 0.25 - 字面中心
        margin-right = 字面中心 - 0.75
      字面中心取自方正书宋/仿宋/小标宋的实际 ink box（三者几乎一致）。
   只处理文本节点：input / textarea 的值、代码块、等宽区域与甲骨文字形不动。 */
(function () {
  "use strict";

  const HAN = /[\u3007\u3400-\u4DBF\u4E00-\u9FFF\uF900-\uFAFF\u{20000}-\u{2FA1F}]/u;
  const LAT = /[0-9A-Za-z\u00C0-\u00D6\u00D8-\u00F6\u00F8-\u024F\u0370-\u03FF\u0400-\u04FF]/;
  const HAN_LATIN_GAP = ".25em";

  /* 标点在 1em 字身框中的水平中心（实测） */
  const CENTER = {
    "、": 0.25, "，": 0.25, "：": 0.25, "；": 0.25, "”": 0.25, "’": 0.25, "．": 0.125,
    "（": 0.597, "）": 0.403,
    "〈": 0.625, "〉": 0.375,
    "《": 0.622, "》": 0.378,
    "「": 0.645, "」": 0.355,
    "『": 0.59, "』": 0.41,
    "【": 0.578, "】": 0.422,
    "〖": 0.578, "〗": 0.422,
    "〔": 0.606, "〕": 0.394,
    "“": 0.75, "‘": 0.75,
    "·": 0.5, "～": 0.5, "／": 0.5, "％": 0.5, "＃": 0.494, "＊": 0.5, "－": 0.496, "＿": 0.5
  };

  const SKIP_TAGS = ["SCRIPT", "STYLE", "TEXTAREA", "INPUT", "SELECT", "OPTION",
                     "CODE", "PRE", "KBD", "SAMP"];
  const SKIP_SELECTOR = ".tw-pk, .tw-lat, .ob-glyph, .we-glyph, .nf-con, .ids-val, [contenteditable]";

  const num = v => String(Math.round(v * 1000) / 1000);

  function esc(ch) {
    return ch === "&" ? "&amp;" : ch === "<" ? "&lt;" : ch === ">" ? "&gt;" : ch;
  }

  /** 把一段纯文本转成带间隙 / 挤压的 HTML；无需改动时返回 null */
  function transform(text) {
    const chars = Array.from(text);
    let html = "";
    let changed = false;

    for (let i = 0; i < chars.length; i++) {
      const ch = chars[i];

      if (HAN.test(ch)) { html += ch; continue; }

      if (LAT.test(ch)) {
        let j = i;
        while (j < chars.length && LAT.test(chars[j])) j++;
        const prev = i > 0 ? chars[i - 1] : "";
        const next = j < chars.length ? chars[j] : "";
        const gapLeft = HAN.test(prev), gapRight = HAN.test(next);
        const run = chars.slice(i, j).join("");
        if (gapLeft || gapRight) {
          html += '<span class="tw-lat"' +
            (gapLeft ? ' style="margin-left:' + HAN_LATIN_GAP + '"' : "") +
            (gapRight ? ' style="margin-right:' + HAN_LATIN_GAP + '"' : "") +
            ">" + run + "</span>";
          changed = true;
        } else {
          html += run;
        }
        i = j - 1;
        continue;
      }

      const c = CENTER[ch];
      if (c === undefined) { html += esc(ch); continue; }
      html += '<span class="tw-pk" style="margin-left:' + num(0.25 - c) +
        "em;margin-right:" + num(c - 0.75) + 'em">' + esc(ch) + "</span>";
      changed = true;
    }

    return changed ? html : null;
  }

  function apply(node) {
    const parent = node.parentNode;
    if (!parent || parent.nodeType !== 1) return;
    if (SKIP_TAGS.indexOf(parent.tagName) >= 0) return;
    if (parent.namespaceURI !== "http://www.w3.org/1999/xhtml") return;
    if (parent.closest(SKIP_SELECTOR)) return;

    const html = transform(node.nodeValue);
    if (!html) return;

    const tpl = document.createElement("template");
    tpl.innerHTML = html;
    parent.replaceChild(tpl.content, node);
  }

  function walk(root) {
    const walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT);
    const nodes = [];
    let n;
    while ((n = walker.nextNode())) nodes.push(n);
    for (const node of nodes) apply(node);
  }

  const observer = new MutationObserver(function (records) {
    for (const rec of records) {
      for (const node of rec.addedNodes) {
        if (node.nodeType === Node.TEXT_NODE) apply(node);
        else if (node.nodeType === Node.ELEMENT_NODE) walk(node);
      }
    }
  });

  function start() {
    walk(document.body);
    observer.observe(document.body, { childList: true, subtree: true });
  }

  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", start);
  else start();
})();
