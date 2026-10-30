/**
 * 图片粘贴 / 拖放
 *
 * 在没有富文本编辑器的前提下，把剪贴板里的图片变成 Markdown：
 *
 *   1. 粘贴 / 拖入图片 → 立刻在光标处插入 `![图片](data:image/…){w=420}`
 *      （编辑区看到的是 md，预览区立刻就能看到图）
 *   2. 同时把图片 POST 到 `/api/images` 存成文件，成功后把那一长串
 *      base64 换成 `/api/images/xxx.png`，正文就不会被 base64 撑爆。
 *      后端不可用（比如老版本没这个接口）时保留 data URI，照样能看。
 *   3. `{w=N}` 是显示宽度（px）。预览里拖动图片右下角的小方块即可改，
 *      改动会写回札记正文（见 writer.js 的 applyImageWidth）。
 *
 * 只要页面上任意 <textarea> 都生效（写作区的札记、标注区的注释框都行）。
 */
(function () {
  const MAX_EDGE = 1600;              // 一边超过这么多像素就先等比缩小
  const DEFAULT_W = 420;              // 比这更宽的图，默认按 420px 显示
  const MAX_BYTES = 12 * 1024 * 1024; // 单张图上限（按 base64 长度粗估）

  function isTextarea(el) {
    return !!el && el.tagName === "TEXTAREA" && !el.readOnly && !el.disabled;
  }

  /** 从 DataTransfer 里挑出图片文件 */
  function imageFilesFrom(dt) {
    const out = [];
    if (!dt) return out;
    if (dt.items && dt.items.length) {
      for (let i = 0; i < dt.items.length; i++) {
        const it = dt.items[i];
        if (it && it.kind === "file" && /^image\//i.test(it.type || "")) {
          const f = it.getAsFile();
          if (f) out.push(f);
        }
      }
    }
    if (!out.length && dt.files && dt.files.length) {
      for (let i = 0; i < dt.files.length; i++) {
        const f = dt.files[i];
        if (f && /^image\//i.test(f.type || "")) out.push(f);
      }
    }
    return out;
  }

  function hasFiles(dt) {
    if (!dt) return false;
    if (dt.items && dt.items.length) return true;
    if (dt.files && dt.files.length) return true;
    if (dt.types) {
      for (let i = 0; i < dt.types.length; i++) {
        if (dt.types[i] === "Files") return true;
      }
    }
    return false;
  }

  function readAsDataURL(file) {
    return new Promise(function (resolve, reject) {
      const fr = new FileReader();
      fr.onload = function () { resolve(String(fr.result || "")); };
      fr.onerror = reject;
      fr.readAsDataURL(file);
    });
  }

  function loadImage(src) {
    return new Promise(function (resolve, reject) {
      const im = new Image();
      im.onload = function () { resolve(im); };
      im.onerror = reject;
      im.src = src;
    });
  }

  /** 读出图片，过大的先等比缩到 MAX_EDGE；返回 { dataURL, w, h } */
  async function prepare(file) {
    let dataURL;
    try { dataURL = await readAsDataURL(file); }
    catch (e) { return null; }

    let im;
    try { im = await loadImage(dataURL); }
    catch (e) { return { dataURL: dataURL, w: 0, h: 0 }; }

    const w0 = im.naturalWidth || im.width || 0;
    const h0 = im.naturalHeight || im.height || 0;
    if (!w0 || !h0) return { dataURL: dataURL, w: 0, h: 0 };
    if (Math.max(w0, h0) <= MAX_EDGE) return { dataURL: dataURL, w: w0, h: h0 };

    const scale = MAX_EDGE / Math.max(w0, h0);
    const w = Math.max(1, Math.round(w0 * scale));
    const h = Math.max(1, Math.round(h0 * scale));
    try {
      const cv = document.createElement("canvas");
      cv.width = w;
      cv.height = h;
      cv.getContext("2d").drawImage(im, 0, 0, w, h);
      const isPng = /^data:image\/png/i.test(dataURL);
      const out = isPng ? cv.toDataURL("image/png") : cv.toDataURL("image/jpeg", 0.92);
      return { dataURL: out, w: w, h: h };
    } catch (e) {
      return { dataURL: dataURL, w: w0, h: h0 };
    }
  }

  /** 上传到后端；失败返回 null（调用方保留 data URI） */
  async function upload(dataURL) {
    if (!dataURL || dataURL.length > MAX_BYTES * 1.4) return null;
    try {
      const r = await fetch("/api/images", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ data: dataURL }),
      });
      if (!r.ok) return null;
      const d = await r.json();
      return (d && d.url) || null;
    } catch (e) {
      return null;
    }
  }

  // ─── 文本框操作 ────────────────────────────────────────

  function insertAtCursor(ta, text) {
    const start = ta.selectionStart == null ? ta.value.length : ta.selectionStart;
    const end = ta.selectionEnd == null ? ta.value.length : ta.selectionEnd;
    const v = ta.value;
    ta.value = v.slice(0, start) + text + v.slice(end);
    const pos = start + text.length;
    try { ta.setSelectionRange(pos, pos); } catch (e) { /* ignore */ }
    ta.dispatchEvent(new Event("input", { bubbles: true }));
  }

  /** 把正文里的 from 换成 to，光标尽量保持在原处 */
  function replaceOnce(ta, from, to) {
    if (!ta || !from) return false;
    const idx = ta.value.indexOf(from);
    if (idx < 0) return false;
    const caret = ta.selectionStart == null ? ta.value.length : ta.selectionStart;
    ta.value = ta.value.slice(0, idx) + to + ta.value.slice(idx + from.length);
    const delta = to.length - from.length;
    let pos = caret;
    if (caret > idx) pos = Math.max(idx, Math.min(ta.value.length, caret + delta));
    try { ta.setSelectionRange(pos, pos); } catch (e) { /* ignore */ }
    ta.dispatchEvent(new Event("input", { bubbles: true }));
    return true;
  }

  // ─── 主流程 ────────────────────────────────────────────

  let busy = 0;

  async function handleFiles(ta, files) {
    if (!ta || !files || !files.length) return;
    for (let i = 0; i < files.length; i++) {
      busy++;
      try {
        const prep = await prepare(files[i]);
        if (!prep) continue;
        const width = prep.w > DEFAULT_W ? DEFAULT_W : 0;
        const suffix = width ? "{w=" + width + "}" : "";
        const md = "![图片](" + prep.dataURL + ")" + suffix;
        insertAtCursor(ta, md);

        const url = await upload(prep.dataURL);
        if (url) replaceOnce(ta, md, "![图片](" + url + ")" + suffix);
      } finally {
        busy--;
      }
    }
  }

  document.addEventListener("paste", function (ev) {
    const ta = ev.target;
    if (!isTextarea(ta)) return;
    const files = imageFilesFrom(ev.clipboardData);
    if (!files.length) return;                 // 普通文本粘贴照旧
    ev.preventDefault();
    handleFiles(ta, files);
  });

  document.addEventListener("dragover", function (ev) {
    if (!isTextarea(ev.target)) return;
    if (!hasFiles(ev.dataTransfer)) return;
    ev.preventDefault();
    try { ev.dataTransfer.dropEffect = "copy"; } catch (e) { /* ignore */ }
  });

  document.addEventListener("drop", function (ev) {
    const ta = ev.target;
    if (!isTextarea(ta)) return;
    const files = imageFilesFrom(ev.dataTransfer);
    if (!files.length) return;
    ev.preventDefault();
    handleFiles(ta, files);
  });

  window.IMGPASTE = {
    handleFiles: handleFiles,
    isBusy: function () { return busy > 0; },
  };
})();
