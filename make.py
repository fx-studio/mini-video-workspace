#!/usr/bin/env python3
"""Một lệnh dựng video dọc 9:16 từ projects/<tên>/script.json.

    python make.py projects/<tên>               # VOICE → HTML → RENDER → MUX
    python make.py projects/<tên> --check-seek  # kiểm seek(t) tất định
"""
import argparse
import asyncio
import json
import math
import shutil
import subprocess
import sys
import time
import wave
from pathlib import Path

ROOT = Path(__file__).resolve().parent
TEMPLATE = ROOT / "template" / "index.html"
VOICE = "vi-VN-HoaiMyNeural"
W, H, FPS = 1080, 1920, 30
GAP_MS = 250
SR = 24000  # edge-tts trả 24 kHz mono
TRIES = 5   # edge-tts hay lỗi tạm thời ("No audio was received"); 3 lần từng suýt không đủ


def run(cmd):
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        sys.exit(f"Lỗi lệnh: {' '.join(map(str, cmd))}\n{r.stderr[-2000:]}")
    return r.stdout


def probe_duration(path):
    out = run(["ffprobe", "-v", "error", "-show_entries", "format=duration",
               "-of", "default=nw=1:nk=1", str(path)])
    return float(out.strip())


# ---------- 1. VOICE ----------
async def tts_once(text, out_mp3):
    import edge_tts
    await edge_tts.Communicate(text, VOICE).save(str(out_mp3))


def tts(text, out_mp3, sid=""):
    last = None
    for attempt in range(1, TRIES + 1):
        try:
            asyncio.run(tts_once(text, out_mp3))
            if out_mp3.exists() and out_mp3.stat().st_size > 0:
                return
            raise RuntimeError("edge-tts trả file rỗng")
        except Exception as e:  # lỗi mạng / dịch vụ tạm thời
            last = e
            print(f"   edge-tts lỗi ở {sid} lần {attempt}/{TRIES}: {e}")
            if attempt < TRIES:
                time.sleep(3 * attempt)
    sys.exit(f"edge-tts thất bại ở {sid} sau {TRIES} lần: {last}. Chờ một lúc rồi chạy lại.")


def step_voice(proj, script):
    vdir = proj / "voice"
    if vdir.exists():
        shutil.rmtree(vdir)
    (vdir / "seg").mkdir(parents=True)
    segments, wavs = [], []
    cursor = 0
    silence = vdir / "seg" / "_gap.wav"
    run(["ffmpeg", "-y", "-v", "error", "-f", "lavfi", "-i", f"anullsrc=r={SR}:cl=mono",
         "-t", f"{GAP_MS/1000:.3f}", "-c:a", "pcm_s16le", str(silence)])
    segs = script["segments"]
    for i, s in enumerate(segs):
        mp3 = vdir / "seg" / f"{s['id']}.mp3"
        wav = vdir / "seg" / f"{s['id']}.wav"
        tts(s["say"], mp3, s["id"])
        run(["ffmpeg", "-y", "-v", "error", "-i", str(mp3), "-ar", str(SR), "-ac", "1",
             "-c:a", "pcm_s16le", str(wav)])
        dur_ms = round(probe_duration(wav) * 1000)  # đo trên WAV, không trên mp3
        segments.append({"id": s["id"], "start_ms": cursor, "end_ms": cursor + dur_ms,
                         "say": s["say"], "show": s["show"]})
        wavs.append(wav)
        cursor += dur_ms
        if i < len(segs) - 1:
            wavs.append(silence)
            cursor += GAP_MS
    # Ghép WAV bằng thư viện chuẩn (cùng định dạng 24 kHz mono s16) → độ dài cộng đúng.
    full_wav = vdir / "voice-full.wav"
    with wave.open(str(full_wav), "wb") as out:
        out.setnchannels(1); out.setsampwidth(2); out.setframerate(SR)
        for w in wavs:
            with wave.open(str(w), "rb") as inp:
                out.writeframes(inp.readframes(inp.getnframes()))
    total_ms = round(probe_duration(full_wav) * 1000)
    run(["ffmpeg", "-y", "-v", "error", "-i", str(full_wav), "-c:a", "libmp3lame",
         "-b:a", "192k", str(vdir / "voice-full.mp3")])
    manifest = {"total_ms": total_ms, "segments": segments}
    (vdir / "timing-manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2),
                                               encoding="utf-8")
    return manifest


# ---------- 2. HTML ----------
def build_html(manifest, title, dest):
    html = TEMPLATE.read_text(encoding="utf-8")
    inject = ("window.MANIFEST = " + json.dumps(manifest, ensure_ascii=False) + ";\n"
              "window.TITLE = " + json.dumps(title, ensure_ascii=False) + ";")
    assert "/*__MANIFEST__*/" in html, "template thiếu chỗ /*__MANIFEST__*/"
    dest.write_text(html.replace("/*__MANIFEST__*/", inject), encoding="utf-8")


# ---------- 3. RENDER ----------
def open_page(pw, html_path):
    browser = pw.chromium.launch()
    page = browser.new_page(viewport={"width": W, "height": H}, device_scale_factor=1)
    # Chặn mọi request ra mạng: chỉ cho file://
    page.route("**/*", lambda r: r.continue_() if r.request.url.startswith("file:") else r.abort())
    page.goto(html_path.as_uri())
    page.evaluate("document.fonts.ready")
    return browser, page


def step_render(manifest, html_path, silent_mp4):
    from playwright.sync_api import sync_playwright
    n = math.ceil(manifest["total_ms"] * FPS / 1000)
    ff = subprocess.Popen(
        ["ffmpeg", "-y", "-v", "error", "-f", "image2pipe", "-framerate", str(FPS),
         "-c:v", "mjpeg", "-i", "-",
         # JPEG là dải màu đầy (yuvj420p); ép về yuv420p dải TV như chuẩn video
         "-vf", "scale=in_range=pc:out_range=tv,format=yuv420p", "-color_range", "tv",
         "-c:v", "libx264", "-preset", "medium", "-crf", "18",
         "-pix_fmt", "yuv420p", "-r", str(FPS), "-movflags", "+faststart", str(silent_mp4)],
        stdin=subprocess.PIPE)
    with sync_playwright() as pw:
        browser, page = open_page(pw, html_path)
        for f in range(n):
            page.evaluate(f"window.seek({f}/{FPS})")
            ff.stdin.write(page.screenshot(type="jpeg", quality=95))
        browser.close()
    ff.stdin.close()
    if ff.wait() != 0:
        sys.exit("ffmpeg lỗi khi encode hình")
    return n


# ---------- 4. MUX ----------
def step_mux(silent_mp4, voice_mp3, out_mp4, n_frames):
    vdur = n_frames / FPS
    run(["ffmpeg", "-y", "-v", "error", "-i", str(silent_mp4), "-i", str(voice_mp3),
         "-map", "0:v:0", "-map", "1:a:0", "-c:v", "copy",
         "-af", f"apad=whole_dur={vdur:.6f}", "-c:a", "aac", "-b:a", "192k",
         "-t", f"{vdur:.6f}", "-movflags", "+faststart", str(out_mp4)])


# ---------- --check-seek ----------
def check_seek(proj):
    from playwright.sync_api import sync_playwright
    mf = proj / "voice" / "timing-manifest.json"
    if mf.exists():
        manifest = json.loads(mf.read_text(encoding="utf-8"))
    else:  # chưa có voice thì dùng manifest giả, chỉ để kiểm template
        manifest = {"total_ms": 6000, "segments": [
            {"id": "a", "start_ms": 0, "end_ms": 2800, "say": "Câu thử một.", "show": "MỘT"},
            {"id": "b", "start_ms": 3050, "end_ms": 6000, "say": "Câu thử hai.", "show": "HAI"}]}
    tmp = proj / "out" / "_check.html"
    tmp.parent.mkdir(parents=True, exist_ok=True)
    build_html(manifest, "check-seek", tmp)
    total = manifest["total_ms"] / 1000
    marks = [0.0, 0.1, 0.25]
    for s in manifest["segments"]:
        a = s["start_ms"] / 1000
        marks += [a, a + 0.15, a + 0.3, (s["start_ms"] + s["end_ms"]) / 2000]
    marks += [total - 1 / FPS, total]
    marks = sorted(set(round(m, 4) for m in marks if 0 <= m <= total))
    with sync_playwright() as pw:
        browser, page = open_page(pw, tmp)
        shots = {}
        for t in marks:                      # lượt 1: tiến
            page.evaluate(f"window.seek({t})"); shots[t] = page.screenshot(type="png")
        bad = []
        for t in reversed(marks):            # lượt 2: lùi
            page.evaluate(f"window.seek({t})")
            if page.screenshot(type="png") != shots[t]:
                bad.append(t)
        # lượt 3: nhảy lung tung (thứ tự cố định, không ngẫu nhiên)
        for t in marks[1::2] + marks[0::2]:
            page.evaluate(f"window.seek({t})")
            if page.screenshot(type="png") != shots[t] and t not in bad:
                bad.append(t)
        browser.close()
    tmp.unlink()
    if bad:
        sys.exit(f"CHECK-SEEK: HỎNG — {len(bad)}/{len(marks)} mốc khác ảnh: {sorted(bad)}")
    print(f"CHECK-SEEK: OK — {len(marks)} mốc × 3 thứ tự, ảnh giống hệt từng byte")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("project")
    ap.add_argument("--check-seek", action="store_true")
    a = ap.parse_args()
    proj = Path(a.project).resolve()
    if a.check_seek:
        check_seek(proj); return
    script = json.loads((proj / "script.json").read_text(encoding="utf-8"))
    out = proj / "out"; out.mkdir(exist_ok=True)

    t0 = time.time()
    m = step_voice(proj, script)
    print(f"1. VOICE  : {len(m['segments'])} segment, total_ms={m['total_ms']} ({time.time()-t0:.1f}s)")
    t1 = time.time()
    html = out / "index.html"
    build_html(m, script.get("title", ""), html)
    print(f"2. HTML   : {html.relative_to(ROOT)} ({time.time()-t1:.1f}s)")
    t2 = time.time()
    silent = out / "silent.mp4"
    n = step_render(m, html, silent)
    print(f"3. RENDER : {n} khung → {silent.relative_to(ROOT)} ({time.time()-t2:.1f}s)")
    t3 = time.time()
    final = out / "video.mp4"
    step_mux(silent, proj / "voice" / "voice-full.mp3", final, n)
    print(f"4. MUX    : {final.relative_to(ROOT)} ({time.time()-t3:.1f}s) — tổng {time.time()-t0:.1f}s")


if __name__ == "__main__":
    main()
