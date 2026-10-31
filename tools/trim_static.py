#!/usr/bin/env python3
"""
Cut out the stretches where the picture is frozen for >= N seconds (keeping the
first M seconds of each freeze), then join everything in the order given on the
command line and write it back to the original path.

    python tools/trim_static.py A.mp4                 # trim A in place
    python tools/trim_static.py A.mp4 B.mp4 C.mp4     # trim each, join, write to A.mp4
    python tools/trim_static.py A.mp4 -o out.mp4      # explicit output
    python tools/trim_static.py A.mp4 --dry-run       # report the detected freezes only

Defaults: a freeze counts once it lasts >= 3 s (`--freeze`), and 0.5 s of it is
kept (`--keep`). The export re-encodes at the source bitrate / resolution / frame
rate / audio settings (the cut points are not keyframes, so a lossless stream copy
is impossible). Output goes to a temp file first and is then moved into place, so
a failed run never destroys the original.

Freezes are detected with ffmpeg's `freezedetect` filter; the result is cached per
(file, parameters) in the temp dir, so a 5-hour recording is only decoded once.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

#: cache format version for the detected freeze list
_CACHE_VERSION = 2


def find_tool(name: str) -> str:
    exe = shutil.which(name)
    if not exe:
        sys.exit(f"{name} not found; install ffmpeg and put it on PATH")
    return exe


FFMPEG = find_tool("ffmpeg")
FFPROBE = find_tool("ffprobe")


# ─── 基础 ──────────────────────────────────────────────────


def probe(path: Path) -> dict:
    """读取流信息：分辨率 / 帧率 / 码率 / 音频参数。"""
    out = subprocess.run(
        [FFPROBE, "-v", "error", "-print_format", "json",
         "-show_format", "-show_streams", str(path)],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
    )
    if out.returncode != 0:
        sys.exit(f"ffprobe failed: {path}\n{out.stderr}")
    data = json.loads(out.stdout or "{}")
    info = {"path": path, "duration": float(data.get("format", {}).get("duration") or 0),
            "bit_rate": int(data.get("format", {}).get("bit_rate") or 0),
            "video": None, "audio": None}
    for s in data.get("streams", []):
        if s.get("codec_type") == "video" and info["video"] is None:
            num, _, den = (s.get("avg_frame_rate") or "0/1").partition("/")
            try:
                fps = float(num) / float(den or 1)
            except (ValueError, ZeroDivisionError):
                fps = 0.0
            if not fps:
                num, _, den = (s.get("r_frame_rate") or "0/1").partition("/")
                fps = float(num) / float(den or 1) if den else 0.0
            info["video"] = {
                "codec": s.get("codec_name") or "h264",
                "width": int(s.get("width") or 0),
                "height": int(s.get("height") or 0),
                "fps": fps or 25.0,
                "pix_fmt": s.get("pix_fmt") or "yuv420p",
                "bit_rate": int(s.get("bit_rate") or 0),
                "start_time": float(s.get("start_time") or 0),
            }
        elif s.get("codec_type") == "audio" and info["audio"] is None:
            info["audio"] = {
                "codec": s.get("codec_name") or "aac",
                "sample_rate": int(s.get("sample_rate") or 44100),
                "channels": int(s.get("channels") or 2),
                "bit_rate": int(s.get("bit_rate") or 0),
            }
    return info


# ─── 静止检测 ──────────────────────────────────────────────

_FREEZE_START = re.compile(r"freeze_start:\s*([0-9.]+)")
_FREEZE_DUR = re.compile(r"freeze_duration:\s*([0-9.]+)")
_FREEZE_END = re.compile(r"freeze_end:\s*([0-9.]+)")


def _cache_path(path: Path, st: dict) -> Path:
    key = hashlib.sha1(json.dumps([str(path.resolve()), st["mtime"], st["size"], st["args"]],
                                  ensure_ascii=False).encode("utf-8")).hexdigest()[:16]
    return Path(tempfile.gettempdir()) / f"trim_static.{key}.json"


def detect_freezes(info: dict, min_seconds: float, noise: float,
                   use_cache: bool = True) -> list[tuple[float, float]]:
    """跑一遍 `freezedetect`，返回静止区间 `[(start, end), ...]`（秒）。

    只保留时长 ≥ `min_seconds` 的区间；一直静到片尾的也算。
    """
    path = info["path"]
    st = {"mtime": path.stat().st_mtime, "size": path.stat().st_size,
          "args": [round(min_seconds, 3), noise]}
    cache = _cache_path(path, st)
    if use_cache and cache.exists():
        try:
            data = json.loads(cache.read_text(encoding="utf-8"))
            if data.get("version") == _CACHE_VERSION:
                return [tuple(x) for x in data["freezes"]]
        except (OSError, ValueError, KeyError):
            pass

    cmd = [FFMPEG, "-hide_banner", "-nostdin", "-i", str(path),
           "-map", "0:v:0", "-an", "-sn", "-dn",
           "-vf", f"freezedetect=n={noise}:d={min_seconds}",
           "-f", "null", "-"]
    starts: list[float] = []
    spans: list[tuple[float, float]] = []
    proc = subprocess.Popen(cmd, stderr=subprocess.PIPE, stdout=subprocess.DEVNULL,
                            text=True, encoding="utf-8", errors="replace")
    assert proc.stderr is not None
    for line in proc.stderr:
        m = _FREEZE_START.search(line)
        if m:
            starts.append(float(m.group(1)))
            continue
        m = _FREEZE_END.search(line)
        if m:
            end = float(m.group(1))
            start = starts.pop(0) if starts else 0.0
            if end - start >= min_seconds - 1e-6:
                spans.append((start, end))
    proc.wait()
    if proc.returncode != 0:
        sys.exit(f"ffmpeg freeze detection failed: {path}")
    # 一直静止到结束、没等到 freeze_end 的那一段
    for start in starts:
        end = info["duration"]
        if end - start >= min_seconds - 1e-6:
            spans.append((start, end))

    spans = merge_spans(spans)
    try:
        cache.write_text(json.dumps({"version": _CACHE_VERSION, "freezes": spans},
                                    ensure_ascii=False), encoding="utf-8")
    except OSError:
        pass
    return spans


def merge_spans(spans: list[tuple[float, float]], gap: float = 0.05) -> list[tuple[float, float]]:
    """相邻 / 重叠的区间合并。"""
    out: list[list[float]] = []
    for s, e in sorted(spans):
        if out and s <= out[-1][1] + gap:
            out[-1][1] = max(out[-1][1], e)
        else:
            out.append([s, e])
    return [(round(s, 3), round(e, 3)) for s, e in out]


# ─── 切割方案 ──────────────────────────────────────────────


def keep_segments(duration: float, freezes: list[tuple[float, float]],
                  keep: float, min_piece: float = 0.2) -> list[tuple[float, float]]:
    """把整段视频切成若干「保留」区间：静止段只留开头 `keep` 秒。"""
    out: list[tuple[float, float]] = []
    cursor = 0.0
    for start, end in freezes:
        start = max(cursor, min(start, duration))
        # 静止之前的画面照留
        if start - cursor > min_piece:
            out.append((cursor, start))
        # 静止段只留开头 keep 秒，其余剪掉
        tail = min(end, start + keep)
        if tail - start > min_piece:
            out.append((start, tail))
        cursor = max(cursor, end)
    if duration - cursor > min_piece:
        out.append((cursor, duration))
    return [(round(s, 3), round(e, 3)) for s, e in out if e - s > 1e-3]


# ─── 渲染 ──────────────────────────────────────────────────


def _v_encoder(codec: str) -> str:
    return {"h264": "libx264", "hevc": "libx265"}.get(codec, "libx264")


def _fmt(t: float) -> str:
    return f"{t:.3f}".rstrip("0").rstrip(".") or "0"


#: 一条 select 表达式里最多放多少个区间（ffmpeg 的表达式解析器撑不住太多项）
CHUNK_SEGMENTS = 40


def _encoder_args(ref: dict, has_audio: bool) -> list[str]:
    """与源视频同码率 / 同分辨率 / 同帧率 / 同音频参数的编码参数。"""
    v = ref["video"]
    vbr = v["bit_rate"] or ref["bit_rate"] or 2_000_000
    args = [
        "-c:v", _v_encoder(v["codec"]),
        "-preset", "veryfast",
        "-b:v", str(vbr), "-maxrate", str(int(vbr * 2)), "-bufsize", str(int(vbr * 4)),
        "-pix_fmt", v["pix_fmt"], "-r", f"{v['fps']:g}",
    ]
    if v["codec"] == "h264":
        args += ["-profile:v", "high", "-level", "4.1"]
    if has_audio:
        a = ref["audio"]
        args += ["-c:a", "aac", "-b:a", str(max(a["bit_rate"], 96_000)),
                 "-ar", str(a["sample_rate"]), "-ac", str(a["channels"])]
    return args


def _run(argv: list[str], label: str, verbose: bool) -> None:
    """跑一条 ffmpeg 命令，失败时打印尾部日志。"""
    if verbose:
        print("  " + " ".join(argv), flush=True)
    proc = subprocess.Popen(argv, stderr=subprocess.PIPE, stdout=subprocess.DEVNULL,
                            text=True, encoding="utf-8", errors="replace")
    assert proc.stderr is not None
    tail: list[str] = []
    for line in proc.stderr:
        tail.append(line.rstrip())
        if len(tail) > 30:
            tail.pop(0)
        if verbose:
            print("   " + line.strip()[:120], flush=True)
    proc.wait()
    if proc.returncode != 0:
        print("\n".join(tail))
        sys.exit(f"ffmpeg failed ({label})")


def _encode_chunk(info: dict, segs: list[tuple[float, float]], out_path: Path,
                  has_audio: bool, verbose: bool) -> None:
    """把一个输入里的一段区间（≤ CHUNK_SEGMENTS 个）编成一个小文件。"""
    start = segs[0][0]
    span = segs[-1][1] - start
    # 区间右端取开区间：`between(a,b)` 两端都含，一个 0.5s 的段会多带一帧，
    # 几十段累积下来整条片子会变长、音画也会慢慢错开
    expr = "+".join(f"(gte(t,{_fmt(s - start)})*lt(t,{_fmt(e - start)}))" for s, e in segs)
    graph = [f"[0:v]select='{expr}',setpts=N/FRAME_RATE/TB,setsar=1[v]"]
    if has_audio:
        graph.append(f"[0:a]aselect='{expr}',asetpts=N/SR/TB[a]")

    argv = [FFMPEG, "-hide_banner", "-nostdin", "-y"]
    if start > 0:
        argv += ["-ss", _fmt(start)]
    argv += ["-t", _fmt(span), "-i", str(info["path"])]

    with tempfile.NamedTemporaryFile("w", suffix=".ffgraph", delete=False,
                                     encoding="utf-8", newline="\n") as fh:
        fh.write(";\n".join(graph))
        graph_file = fh.name
    try:
        argv += ["-/filter_complex", graph_file, "-map", "[v]"]
        if has_audio:
            argv += ["-map", "[a]"]
        argv += _encoder_args(info, has_audio)
        argv += ["-movflags", "+faststart", str(out_path)]
        _run(argv, out_path.name, verbose)
    finally:
        try:
            os.unlink(graph_file)
        except OSError:
            pass


def _same_params(inputs: list[tuple[dict, list[tuple[float, float]]]]) -> bool:
    """各输入的分辨率 / 帧率 / 编码是否一致（一致才能 copy 拼接）。"""
    keys = ("codec", "width", "height", "fps", "pix_fmt")
    first = inputs[0][0]["video"]
    return all(
        all(abs(float(a[k]) - float(first[k])) < 1e-6 if k == "fps" else a[k] == first[k]
            for k in keys)
        for a in (info["video"] for info, _ in inputs)
    )


def render(inputs: list[tuple[dict, list[tuple[float, float]]]], out_path: Path,
           verbose: bool = False) -> None:
    """按保留区间重新编码，再无损拼接成 out_path。

    分块的原因：一条 `select` 表达式里塞几百个 `between()` 会让 ffmpeg 的
    表达式解析器直接失败（Cannot allocate memory），所以每块只放 40 个区间，
    逐块编码后用 concat 直接 copy 拼起来（同编码参数，拼起来不掉画质）。
    """
    has_audio = all(info["audio"] for info, _ in inputs)
    ref = inputs[0][0]
    n_seg = sum(len(segs) for _, segs in inputs)
    print(f"  encoding {n_seg} segments -> {out_path}")
    started = time.time()

    work = Path(tempfile.mkdtemp(prefix="trim_static."))
    parts: list[Path] = []
    try:
        for job_no, (info, segs) in enumerate(inputs, 1):
            for i in range(0, len(segs), CHUNK_SEGMENTS):
                piece = segs[i:i + CHUNK_SEGMENTS]
                out = work / f"{job_no:02d}_{i // CHUNK_SEGMENTS:03d}.mp4"
                _encode_chunk(info, piece, out, has_audio, verbose)
                parts.append(out)
                kept = sum(e - s for s, e in piece)
                print(f"  chunk {len(parts)}: {len(piece)} segments / {kept:.0f}s"
                      f" (total {sum(p.stat().st_size for p in parts) / 1e6:.0f} MB)",
                      flush=True)

        if len(parts) == 1:
            os.replace(parts[0], out_path)
        else:
            listing = work / "concat.txt"
            listing.write_text("".join(f"file '{p.as_posix()}'\n" for p in parts),
                               encoding="utf-8")
            concat = [FFMPEG, "-hide_banner", "-nostdin", "-y", "-f", "concat",
                      "-safe", "0", "-i", str(listing)]
            if _same_params(inputs):
                concat += ["-c", "copy"]
            else:
                # 各段编码参数不一致时直接 copy 拼不了，只好再编一次
                print("  warning: inputs differ in size / frame rate, concat needs a re-encode")
                concat += _encoder_args(ref, has_audio)
            concat += ["-movflags", "+faststart", str(out_path)]
            _run(concat, "concat", verbose)
    finally:
        shutil.rmtree(work, ignore_errors=True)

    src = inputs[0][0]["duration"]
    total = sum(e - s for _, segs in inputs for s, e in segs)
    print(f"  done in {time.time() - started:.0f}s; "
          f"kept {total:.1f}s (first input was {src:.1f}s)")


# ─── 主流程 ────────────────────────────────────────────────


def human(t: float) -> str:
    t = int(round(t))
    return f"{t // 3600}:{t % 3600 // 60:02d}:{t % 60:02d}"


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(
        description="cut frozen stretches (>= N seconds), join the inputs in order, "
                    "write back to the original path")
    ap.add_argument("paths", nargs="+", help="video files, processed and joined in this order")
    ap.add_argument("-o", "--out",
                    help="output path (default: overwrite the first input; see --backup)")
    ap.add_argument("--freeze", type=float, default=3.0,
                    help="a freeze must last this long to be cut (seconds, default 3)")
    ap.add_argument("--keep", type=float, default=0.5,
                    help="how much of each freeze to keep (seconds, default 0.5)")
    ap.add_argument("--noise", type=float, default=0.003,
                    help="noise tolerance of the freeze test (default 0.003; "
                         "try 0.005 on noisy sources)")
    ap.add_argument("--backup", action="store_true", help="keep a .bak copy before overwriting")
    ap.add_argument("--dry-run", action="store_true", help="only report what would be cut")
    ap.add_argument("--no-cache", action="store_true", help="ignore the detection cache")
    ap.add_argument("--verbose", action="store_true",
                    help="print the full ffmpeg command and its progress")
    args = ap.parse_args(argv)

    paths = [Path(p).expanduser() for p in args.paths]
    for p in paths:
        if not p.is_file():
            sys.exit(f"no such file: {p}")

    out_path = Path(args.out).expanduser() if args.out else paths[0]

    jobs: list[tuple[dict, list[tuple[float, float]]]] = []
    grand_old = 0.0
    grand_new = 0.0
    for p in paths:
        info = probe(p)
        if not info["video"]:
            sys.exit(f"no video stream: {p}")
        freezes = detect_freezes(info, args.freeze, args.noise, use_cache=not args.no_cache)
        segs = keep_segments(info["duration"], freezes, args.keep)
        old = info["duration"]
        new = sum(e - s for s, e in segs)
        grand_old += old
        grand_new += new
        print(f"{p.name}  {human(old)} -> {human(new)}  "
              f"({len(freezes)} freezes, {human(old - new)} cut, {len(segs)} segments left)")
        for s, e in freezes[:10]:
            print(f"    frozen {human(s)} - {human(e)}  {e - s:.1f}s")
        if len(freezes) > 10:
            print(f"    ... and {len(freezes) - 10} more")
        jobs.append((info, segs))

    print(f"total {human(grand_old)} -> {human(grand_new)}")
    if args.dry_run:
        return

    out_path.parent.mkdir(parents=True, exist_ok=True)
    tmp = out_path.with_name(out_path.stem + ".trimtmp" + (out_path.suffix or ".mp4"))
    if tmp.exists():
        tmp.unlink()
    try:
        render(jobs, tmp, verbose=args.verbose)
        if args.backup and out_path.exists() and args.out is None:
            bak = out_path.with_name(out_path.stem + ".bak" + out_path.suffix)
            if not bak.exists():
                out_path.replace(bak)
                print(f"  original backed up as {bak.name}")
        os.replace(tmp, out_path)
    finally:
        if tmp.exists():
            tmp.unlink()
    size = out_path.stat().st_size / 1024 / 1024
    print(f"written {out_path}  ({size:.1f} MB)")


if __name__ == "__main__":
    main()
