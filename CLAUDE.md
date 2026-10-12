# Luật của workspace video dọc 9:16

Workspace này làm video dọc 1080x1920, 30 fps: `script.json` → giọng edge-tts → HTML chụp từng khung → mp4.
Một lệnh: `.venv/bin/python make.py projects/<tên>` (Windows: `.venv\Scripts\python`). Gọi `python` trần sẽ không thấy thư viện đã cài.

## Luật cứng

1. **Mốc thời gian lấy từ `timing-manifest.json`, không gõ tay.** Mọi start/end của cảnh, phụ đề, thanh tiến độ
   đều đọc từ manifest do bước VOICE sinh ra (đo bằng ffprobe trên WAV). Không ước lượng theo số chữ, không đo trên mp3.
2. **`seek(t)` phải là hàm thuần của t.** Trong `template/index.html` cấm: CSS animation/transition,
   `requestAnimationFrame`, `setTimeout`/`setInterval`, `Math.random`, `Date`/`performance.now`, và mọi trạng thái
   tích luỹ giữa các lần gọi. Gọi `seek(t)` hai lần với cùng t phải ra cùng một ảnh, bất kể trước đó seek tới đâu.
3. **Sửa template xong thì chạy `.venv/bin/python make.py projects/<tên> --check-seek`.** Lệnh này seek vài mốc, mỗi mốc ba lượt
   theo thứ tự khác nhau (tiến, lùi, xen kẽ), so ảnh PNG từng byte. Phải ra `CHECK-SEEK: OK` mới được render.
4. **Không tự đăng video lên đâu cả** (YouTube, TikTok, Facebook, Drive…). Làm xong thì báo đường dẫn mp4, dừng.
5. **Không tải gì từ mạng lúc render.** Font dùng font có sẵn trên máy, đủ dấu tiếng Việt. Mạng chỉ dùng cho edge-tts.
6. **Mọi chữ nằm trong vùng y 250–1450** để không bị nút của Reels/TikTok che.
7. Video cuối phải kiểm bằng ffprobe: 1080x1920, 30 fps, có tiếng, độ dài lệch `total_ms` dưới 0,1 s.
   Không dùng `-shortest` khi mux.

## Skill

- `tao-video` (`.claude/skills/tao-video/SKILL.md`, bản chép cho Antigravity/Codex ở `.agents/skills/tao-video/`):
  ý tưởng → `script.json` → `make.py` → kiểm → báo. Người dùng bảo "làm video về…" thì dùng skill này.
  Sửa skill thì sửa cả hai bản cho giống nhau.

## Bố cục

- `make.py` — 4 bước VOICE → HTML → RENDER → MUX, mỗi bước in một dòng.
- `template/index.html` — khung hình dùng chung, khai `window.seek(t)`. Chỗ `/*__MANIFEST__*/` để make.py nhét manifest.
- `projects/<tên>/script.json` — kịch bản (nguồn sự thật). `voice/` và `out/` là sinh ra, chạy lại sẽ ghi đè, và không vào git.
- `PROMPT.md` — prompt đã dựng ra chính workspace này, để người khác tự dựng lại từ thư mục trống.
