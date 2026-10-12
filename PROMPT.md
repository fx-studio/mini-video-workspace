# Prompt: dựng một xưởng video mini

Repo này **chính là** thứ prompt dưới dựng ra. Muốn tự dựng lại từ đầu (để xem agent làm thế nào, hoặc để có bản của riêng mình),
mở **một thư mục trống** trong agent viết code (Claude Code, Antigravity, Codex…), dán nguyên khối dưới vào.

Lần đầu `playwright install chromium` tải vài trăm MB.

````text

Dựng cho tôi một workspace làm video dọc 9:16 (1080x1920, 30 fps) ngay trong thư mục này. Mục tiêu: tôi viết kịch bản, chạy một lệnh, ra file mp4 có giọng đọc tiếng Việt và hình chuyển động khớp lời.

Công nghệ, không thêm gì khác:
- Hình: một file HTML + CSS + JS thuần, không framework, không tải gì từ mạng lúc render.
- Giọng: edge-tts (Python), giọng vi-VN-HoaiMyNeural. Nó gọi dịch vụ đọc của Microsoft Edge nên cần mạng và đôi khi lỗi tạm thời: lỗi thì chờ vài giây rồi thử lại, tối đa 3 lần.
- Chụp hình: Playwright (Python) điều khiển Chromium.
- Ghép: ffmpeg + ffprobe.

Cấu trúc:
  CLAUDE.md          luật của workspace (viết kèm AGENTS.md cùng nội dung cho agent khác đọc)
  README.md          cài đặt + cách làm một video mới
  make.py            một lệnh: python make.py projects/<tên>   (thêm --check-seek để kiểm tất định)
  template/index.html  khung hình dùng chung
  projects/<tên>/script.json   kịch bản
  projects/<tên>/voice/        giọng + timing-manifest.json   (sinh ra)
  projects/<tên>/out/          video.mp4                       (sinh ra)

script.json:
  { "title": "...", "segments": [ { "id": "s1", "say": "câu đọc", "show": "CHỮ TRÊN MÀN" }, ... ] }

make.py chạy 4 bước theo thứ tự, mỗi bước in một dòng:
1. VOICE: mỗi segment một file mp3 bằng edge-tts, giải mã sang WAV rồi đo độ dài thật bằng ffprobe trên WAV (không ước lượng theo số chữ, không đo trên mp3 vì mp3 có đệm). Ghép các WAV, giữa hai segment chèn 250 ms im lặng, rồi mới encode voice-full.mp3. Ghi timing-manifest.json đơn giản nhất:
   { "total_ms": ..., "segments": [ { "id": "s1", "start_ms": ..., "end_ms": ..., "say": "...", "show": "..." } ] }
2. HTML: chép template, nhét timing-manifest vào làm một biến JS.
3. RENDER: trang HTML khai hàm window.seek(t) vẽ đúng khung hình tại giây t, là hàm thuần của t: không dùng CSS animation/transition, không requestAnimationFrame, không setTimeout, không Math.random, không Date. Mọi chuyển động tính từ t. Playwright mở trang, lặp t = 0, 1/30, 2/30… tới hết total_ms, gọi seek(t), chụp ảnh, đẩy thẳng vào ffmpeg qua stdin (image2pipe) ra mp4 câm (libx264). Chụp PNG; nếu chụp JPEG thì phải ép về dải màu TV (scale=in_range=pc:out_range=tv,format=yuv420p), vì ffprobe phải ra yuv420p chứ không phải yuvj420p. Trong 250 ms lặng giữa hai câu, cảnh cũ giữ nguyên tới start_ms của cảnh sau.
   Số khung hình = ceil(total_ms × 30 / 1000).
4. MUX: ghép mp4 câm + voice-full.mp3 thành out/video.mp4. Không dùng -shortest (nó cắt mất khung cuối); đệm im lặng cho tiếng (apad) tới đúng số khung hình / 30 giây, kèm -t cùng độ dài đó.

Hình: nền tối, mỗi segment một cảnh, chữ "show" to giữa khung, đập vào trong 0,3 giây đầu cảnh. Có thanh tiến độ mỏng ở trên. Phụ đề là chữ "say" đặt dưới chữ chính: câu đang đọc sáng, câu kế tiếp mờ. Mọi chữ nằm trong vùng y 250–1450 để không bị nút của Reels/TikTok che. Font phải đủ dấu tiếng Việt, dùng font có sẵn trên máy, không tải từ mạng.

Luật ghi vào CLAUDE.md:
- Mốc thời gian lấy từ timing-manifest.json, không gõ tay.
- seek(t) phải là hàm thuần của t. Sửa template xong thì chạy make.py --check-seek: seek vài mốc, mỗi mốc hai lần theo thứ tự khác nhau, so ảnh phải giống hệt.
- Không tự đăng video lên đâu cả.

Làm xong thì tự chạy thử: tạo projects/demo/script.json gồm 3 segment giới thiệu chính workspace này (tổng khoảng 15 giây), chạy make.py, rồi kiểm bằng ffprobe: đúng 1080x1920, 30 fps, pix_fmt yuv420p, có tiếng, số khung hình đếm thật (-count_frames) bằng ceil(total_ms × 30 / 1000), độ dài khớp total_ms (lệch dưới 0,1 s). Chạy cả make.py --check-seek, rồi thử phá seek một lần (thêm biến đếm vào seek) để chắc lệnh kiểm biết báo hỏng, xong trả template về như cũ. Báo tôi kết quả kiểm và đường dẫn file mp4. Lỗi ở bước nào thì sửa rồi chạy lại, đừng báo xong khi chưa có mp4.
````

## Vì sao viết như vậy

| Chỗ trong prompt | Lý do |
|---|---|
| Đo độ dài bằng ffprobe | Ước theo số chữ là nguồn lệch hình–tiếng hay gặp nhất |
| `seek(t)` thuần, cấm animation/timer | Chụp từng khung bằng Playwright chỉ đúng khi hình là hàm của t: chụp nhanh hay chậm cũng ra cùng một video |
| Pipe thẳng vào ffmpeg | Không ghi hàng trăm ảnh ra đĩa |
| Timing-manifest 4 trường | Ít nhất mà vẫn đủ để khớp cảnh với lời |
| Tự chạy thử + kiểm bằng ffprobe | Agent hay báo xong khi chưa có file. Bắt nó đưa bằng chứng |
| CLAUDE.md + AGENTS.md | Claude Code đọc CLAUDE.md, Antigravity/Codex đọc AGENTS.md |
| Đo trên WAV, không trên mp3 | mp3 có đệm của encoder, đo lệch vài chục ms mỗi câu, cộng dồn thành lệch hình–tiếng |
| Cấm `-shortest` | Cờ này cắt mất mấy khung cuối của video |
| Thử lại edge-tts | Dịch vụ hay lỗi tạm thời ("No audio was received"), chạy lại thì qua |
| Ép dải màu TV | Chụp JPEG mà không ép thì mp4 ra `yuvj420p`, có máy phát lên sẽ lệch màu |
