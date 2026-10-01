"""
清理抽构表 comment 里的重复段（迁移时用 ` / ` 追加，可能有重复或近重复）。

用法：
    python -m backend.scripts.dedupe_sheet_comment [--dry-run]
"""

from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent.parent
INPUT_DIR = REPO / "input"
SHEET_NAMES = ("main", "a", "b", "ci", "gh")


def norm_key(s: str) -> str:
    """粗略归一：去掉空白和常见标点，用于判断两段是否实质相同。"""
    drop = set(" \t　，。、；：？！“”‘’（）〈〉《》「」『』，,.;:?!\"'()<>[]{}·-—/")
    return "".join(c for c in s if c not in drop)


def dedupe(comment: str) -> str:
    if " / " not in comment:
        return comment
    parts = [p.strip() for p in comment.split(" / ")]
    kept: list[str] = []
    seen: list[str] = []
    for p in parts:
        if not p:
            continue
        k = norm_key(p)
        # 完全一样，或一段完整包含另一段 -> 视为重复
        if any(k == s or (len(k) > 12 and len(s) > 12 and (k in s or s in k)) for s in seen):
            # 保留更长的那一段
            for i, s in enumerate(seen):
                if k in s or s in k:
                    if len(k) > len(s):
                        kept[i] = p
                        seen[i] = k
                    break
            continue
        kept.append(p)
        seen.append(k)
    return " / ".join(kept)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    changed = 0
    saved = 0
    for name in SHEET_NAMES:
        path = INPUT_DIR / f"abstract_{name}.txt"
        if not path.exists():
            continue
        rows: list[str] = []
        with path.open("r", encoding="utf-8") as f:
            for line in f:
                if not line.strip():
                    continue
                parts = line.rstrip("\n").split("\t")
                parts += [""] * 4
                parts = parts[:4]
                old = parts[3]
                if old:
                    new = dedupe(old)
                    if new != old:
                        changed += 1
                        saved += len(old) - len(new)
                        parts[3] = new
                rows.append("\t".join(parts).rstrip("\t"))

        print(f"{name}: {len(rows)} 行")

        if not args.dry_run:
            shutil.copy(path, path.with_suffix(".txt.bak2"))
            with path.open("w", encoding="utf-8", newline="\n") as f:
                for r in rows:
                    f.write(r + "\n")

    print(f"\n去重行数: {changed}，省下 {saved} 字符")
    if args.dry_run:
        print("[dry-run] 没写文件")
    return 0


if __name__ == "__main__":
    sys.exit(main())
