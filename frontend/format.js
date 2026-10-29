/**
 * 抽构 / 参考抽构 输入框的即时格式化
 *
 *   * 全角括号 `（）［］` → 半角（等长替换，光标不动）
 *   * 输入停顿后用 `/api/shape/validate` 的 `normalized` 回写：
 *     `⿰木木` → `⿰[木][木]`、`=下` → `=[下]`、`⿱九乙（ᄅ）` → `⿱[九][乙(ᄅ)]`
 *     回写时按「有效字符」（不算 `[ ]` 和空白）的个数保住光标
 *   * 输入法拼写中（composition）不动输入框，拼完再格式化
 *
 * 用法：
 *   SHAPEFMT.bind(input, { onFormatted: fn })   显式绑定
 *   标注/甲骨文视图的 `new-con` / `edit-ref-2` 之类会自动绑定（focusin 时）
 */
(function () {
  const FULLWIDTH = { "（": "(", "）": ")", "［": "[", "］": "]" };
  const ID_RE = /^(new|edit)-(con|ref)(-\d+)?$/;
  const DEBOUNCE = 260;

  /** 全角括号 → 半角；返回是否改动过 */
  function normalizeChars(el) {
    const before = el.value;
    let after = before;
    Object.keys(FULLWIDTH).forEach(function (k) {
      after = after.split(k).join(FULLWIDTH[k]);
    });
    if (after === before) return false;
    const pos = el.selectionStart;
    el.value = after;
    el.setSelectionRange(pos, pos);   // 等长替换，光标位置不变
    return true;
  }

  /** 用规范写法回写；返回是否改动过 */
  function applyFormatted(el, formatted) {
    if (!formatted || el.value === formatted) return false;
    const pos = el.selectionStart;
    const before = el.value.slice(0, pos).replace(/[\s\[\]]/g, "").length;
    let i = 0, seen = 0;
    while (i < formatted.length && seen < before) {
      if (!/[\s\[\]]/.test(formatted[i])) seen++;
      i++;
    }
    el.value = formatted;
    el.setSelectionRange(i, i);
    return true;
  }

  /** 问后端要规范写法并回写；返回是否改动过 */
  async function formatNow(el) {
    const expr = (el.value || "").trim();
    if (!expr) return false;
    const token = (el._fmtToken = (el._fmtToken || 0) + 1);
    let res;
    try {
      const r = await fetch("/api/shape/validate", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ expr: expr }),
      });
      if (!r.ok) return false;
      res = await r.json();
    } catch (e) {
      return false;
    }
    if (token !== el._fmtToken) return false;      // 期间又输入了，结果作废
    if ((el.value || "").trim() !== expr) return false;
    return applyFormatted(el, res && res.ok ? res.normalized : "");
  }

  function schedule(el) {
    clearTimeout(el._fmtTimer);
    el._fmtTimer = setTimeout(async function () {
      const changed = await formatNow(el);
      if (changed && typeof el._fmtDone === "function") el._fmtDone(el);
    }, DEBOUNCE);
  }

  function bind(el, opts) {
    opts = opts || {};
    if (!el || el._fmtBound) return;
    el._fmtBound = true;
    el._fmtDone = opts.onFormatted || null;

    el.addEventListener("input", function () {
      if (el._composing) return;                   // 输入法拼写中不动
      normalizeChars(el);
      schedule(el);
    });
    el.addEventListener("compositionstart", function () { el._composing = true; });
    el.addEventListener("compositionend", function () {
      el._composing = false;
      normalizeChars(el);
      schedule(el);
    });
    el.addEventListener("blur", function () {
      if (el._composing) return;
      clearTimeout(el._fmtTimer);
      formatNow(el).then(function (changed) {
        if (changed && typeof el._fmtDone === "function") el._fmtDone(el);
      });
    });
  }

  // 标注 / 甲骨文视图的抽构、参考抽构输入框：聚焦时自动绑定
  document.addEventListener("focusin", function (ev) {
    const el = ev.target;
    if (el && el.tagName === "INPUT" && ID_RE.test(el.id || "")) bind(el, {});
  });

  window.SHAPEFMT = { bind: bind, normalizeChars: normalizeChars, applyFormatted: applyFormatted, formatNow: formatNow };
})();
