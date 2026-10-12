---
name: tao-video
description: Biến một ý tưởng, chủ đề, đoạn ghi chú hay bài viết thành video dọc 9:16 có giọng đọc tiếng Việt trong workspace này — viết projects/<tên>/script.json, chạy make.py, kiểm mp4 bằng ffprobe, xem lại khung hình, báo kết quả. Dùng khi người dùng bảo "làm video", "tạo reel", "dựng video về…", đưa một nội dung và muốn ra mp4, hoặc muốn sửa kịch bản của một video đã có rồi dựng lại.
---

# tao-video

Workspace này đã có máy làm video (`make.py`). Phần của bạn là **phán đoán**: viết kịch bản đúng nhịp, chạy, rồi
**kiểm bằng máy và bằng mắt** trước khi báo xong. Đọc `CLAUDE.md` (luật của workspace) trước.

## 1. Kịch bản: `projects/<tên>/script.json`

`<tên>` viết thường, không dấu, nối bằng gạch ngang (`ai-doc-video`). Đã có thư mục cùng tên thì hỏi trước khi ghi đè,
vì `make.py` xoá sạch `voice/` và `out/` của project đó.

```json
{ "title": "NHÃN NHỎ TRÊN ĐẦU", "segments": [ { "id": "s1", "say": "câu đọc", "show": "CHỮ TO" } ] }
```

- **Độ dài:** reel 15–45 giây. Giọng `vi-VN-HoaiMyNeural` đọc khoảng **2,5–3,3 từ/giây**, trung bình ~3 (đo trên các lần
  chạy thật), cộng 0,25 s lặng giữa hai câu. Ước: tổng số từ ÷ 3 + 0,25 × (số segment − 1), sai số chừng ±10%.
- **Segment:** mỗi segment một cảnh, một ý, một câu 8–18 từ. Ngắn hơn thì cảnh lướt qua không kịp đọc, dài hơn thì chữ phụ đề
  xuống ba dòng. 3–8 segment cho một reel.
- **Câu đầu là hook:** câu hỏi hoặc một điều ngược đời người xem muốn biết câu trả lời. Câu cuối là lời kêu gọi (lưu lại,
  bình luận, xem tập sau).
- **`say` viết cho tai:** số và viết tắt viết ra chữ khi máy dễ đọc sai ("ba phẩy năm", "A P I"), bỏ ký hiệu không đọc
  được (`→`, `/`, `#`, emoji). Tên tiếng Anh giữ nguyên nếu phổ biến (YouTube, Python).
- **`show` viết cho mắt:** 1–3 từ IN HOA, là ý chính của câu, không chép lại `say`. Chữ rất to, dài quá sẽ xuống nhiều dòng.
- **`title`:** nhãn nhỏ trên đầu khung, giữ suốt video, template tự in hoa. Vài từ nói video về gì ("3 MẸO ĐẶT TÊN FILE").
- **Không bịa số liệu, tên sản phẩm, trích dẫn.** Nội dung người dùng đưa không có thì hỏi, hoặc nói chung chung.

Trình kịch bản (bảng `say` / `show` + ước thời lượng) cho người dùng xem trước khi dựng, trừ khi họ bảo cứ làm.

## 2. Dựng

```bash
.venv/bin/python make.py projects/<tên>
```

Chưa có `.venv` thì cài theo `README.md` (cần mạng, lần đầu tải Chromium vài trăm MB). Bốn dòng `1. VOICE` → `4. MUX`.

- `edge-tts lỗi ở s2 lần x/5`: dịch vụ chập chờn, `make.py` tự thử lại tối đa 5 lần (có lần cần tới lần thứ 3). Lỗi cả 5 lần thì
  chờ một lúc rồi chạy lại cả lệnh, đừng đổi giọng hay sửa code.
- Lỗi khác thì đọc thông báo, sửa đúng chỗ, chạy lại. **Không báo xong khi chưa có `out/video.mp4`.**

## 3. Kiểm bằng máy

```bash
ffprobe -v error -count_frames -select_streams v:0 \
  -show_entries stream=width,height,r_frame_rate,pix_fmt,nb_read_frames -of compact projects/<tên>/out/video.mp4
ffprobe -v error -select_streams a:0 -show_entries stream=codec_name -of compact projects/<tên>/out/video.mp4
ffprobe -v error -show_entries format=duration -of compact projects/<tên>/out/video.mp4
```

Phải ra: `1080` × `1920`, `30/1`, `yuv420p`, có stream audio, số frame = ceil(`total_ms` × 30 / 1000), và thời lượng lệch
`total_ms` dưới 0,1 s (`total_ms` nằm trong `projects/<tên>/voice/timing-manifest.json`).

## 4. Kiểm bằng mắt

Trích **một khung giữa mỗi cảnh** (mốc lấy từ manifest) ghép thành một ảnh, rồi **mở ảnh xem** nếu bạn đọc được ảnh:

```bash
P=projects/<tên>; .venv/bin/python -c "import json,sys;m=json.load(open(sys.argv[1]));print('+'.join(f'eq(n,{round((s[\"start_ms\"]+s[\"end_ms\"])*15/1000)})' for s in m['segments']))" $P/voice/timing-manifest.json > $P/out/sel.txt
N=$(grep -o 'eq(' $P/out/sel.txt | wc -l | tr -d ' ')
ffmpeg -v error -y -i $P/out/video.mp4 -vf "select='$(cat $P/out/sel.txt)',scale=360:-1,tile=${N}x1" -vsync 0 -frames:v 1 $P/out/xem.jpg
```

Mỗi ô là một cảnh, đủ mọi cảnh dù video dài bao nhiêu.

Tìm: chữ `show` xuống quá hai dòng, phụ đề tràn ba dòng, dấu tiếng Việt bị mất hay thành ô vuông, cảnh trống.
Sai ở kịch bản thì sửa `script.json` (rút `show`, tách câu) rồi dựng lại.

## 5. Báo

Đường dẫn mp4, thời lượng, số cảnh, kết quả hai bước kiểm, và chỗ nào bạn đã tự sửa. **Không đăng video lên đâu cả.**

## Sửa giao diện (khi người dùng yêu cầu)

Sửa `template/index.html`, giữ `seek(t)` là hàm thuần của t (luật 2 của `CLAUDE.md`). Sửa xong:

```bash
.venv/bin/python make.py projects/<tên> --check-seek
```

Phải ra `CHECK-SEEK: OK` rồi mới dựng lại. Template dùng chung cho mọi project: sửa nó là đổi hình của mọi video dựng sau.
