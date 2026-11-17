# Danh Mục & Hướng Dẫn Sử Dụng Các Tool (TOOL.md)

Thư mục `scripts/` chứa bộ công cụ chuyên dụng được viết sẵn để Agent hoặc người dùng có thể gọi trực tiếp thông qua dòng lệnh.

---

## 1. Bảng Tổng Quan Các Tool

| Tên Script | Chức năng chính | Đầu vào chính | Đầu ra |
| :--- | :--- | :--- | :--- |
| **`cut_video.py`** | Cắt video theo mốc thời gian không giảm chất lượng (`-c copy`) | File video, mốc start/end | `video_cut.mp4` |
| **`extract_slides.py`** | **(V2.0)** Lấy mẫu 10 fps (0.1s/frame), lọc frame tĩnh & OCR khử trùng lặp $\ge 90\%$ | File video | Thư mục `slides/` (`slide_001.jpg`, `slides_index.json`) |
| **`split_chunks.py`** | *(V1.0)* Chia video thành các đoạn vi mô $\le 5$s | File video cắt | Thư mục `chunks/` (`chunk_001.mp4`,...) |
| **`extract_questions.py`** | *(V1.0)* Khung sườn quét slide trong từng chunk | Thư mục `chunks/` | File `extracted_questions.json` |
| **`generate_word.py`** | Khử trùng lặp và xuất file Word chuẩn format (đáp án đúng màu đỏ) | File JSON câu hỏi | File Word `tong_hop_cau_hoi.docx` |
| **`pipeline.py`** | Chạy liên hoàn quy trình cắt & chia chunk | Video, mốc start/end | Chạy hoàn tất các bước chuẩn bị |

---

## 2. Hướng Dẫn Chi Tiết Từng Tool

### 🛠️ Tool 1: `cut_video.py` (Cắt Video Nhanh - Lossless)
* **Mô tả:** Sử dụng FFmpeg stream copy (`-c copy`) để cắt trích đoạn video trong tích tắc mà không nén lại dữ liệu, bảo toàn 100% độ sắc nét của chữ trên slide.
* **Cú pháp:**
  ```bash
  py scripts/cut_video.py -s [bắt_đầu] -e [kết_thúc] [-i input_video] [-o output_video]
  ```
* **Các tham số:**
  * `-s, --start`: Thời gian bắt đầu (mặc định: `00:00:00`).
  * `-e, --end`: Thời gian kết thúc (**Bắt buộc**). Hỗ trợ các định dạng: `1p14`, `1m14s`, `74s`, `00:01:14`.
  * `-i, --input`: Đường dẫn video gốc (nếu không truyền, tool tự quét lấy video có sẵn trong thư mục).
  * `-o, --output`: Đường dẫn video sau khi cắt (mặc định: `[tên_video]_cut.mp4`).
* **Ví dụ:**
  ```bash
  py scripts/cut_video.py -s 00:00:00 -e 1p14 -i DBI_P2.mp4
  ```

---

### 🛠️ Tool 2: `extract_slides.py` *(V2.0 - Khuyên dùng)* (Trích Xuất Slide Duy Nhất 10 fps + OCR)
* **Mô tả:** Lấy mẫu video ở **10 fps (0.1s/frame)**, lọc các frame đứng yên bằng sai khác pixel, sau đó chạy OCR cục bộ (`rapidocr` / `tesseract` / `winocr`) so sánh độ tương đồng văn bản (`>= 90%`) để gộp trùng và mặc định giữ frame cuối cùng của mỗi câu hỏi (bắt trọn đáp án vừa hiện).
* **Cú pháp:**
  ```bash
  py scripts/extract_slides.py [-i input_video] [-o thư_mục_slides] [--fps 10.0] [--similarity 0.90]
  ```
* **Các tham số chính:**
  * `-i, --input`: Đường dẫn video đầu vào (tự tìm nếu bỏ trống).
  * `-o, --output-dir`: Thư mục lưu ảnh slide duy nhất (mặc định: `slides`).
  * `--fps`: Tốc độ lấy mẫu frame/giây (mặc định: `10.0` = 0.1s/frame).
  * `--similarity`: Ngưỡng giống nhau về chữ để gộp trùng (mặc định: `0.90`).
  * `--pixel-diff`: Ngưỡng sai khác pixel lọc frame tĩnh (mặc định: `1.5`).
  * `--ocr-backend`: `auto` | `rapidocr` | `tesseract` | `winocr` (mặc định: `auto`).
  * `--keep-first`: Giữ frame đầu tiên thay vì frame cuối cùng trong mỗi nhóm câu hỏi.
* **Đầu ra:** Thư mục `slides/` chứa `slide_001.jpg`, `slide_002.jpg`,... và file `slides/slides_index.json`.

---

### 🛠️ Tool 2b (Legacy V1.0): `split_chunks.py` (Chia Nhỏ Video $\le 5$s)
* **Mô tả:** Ép keyframe cố định và cắt video thành các chunk nhỏ (tối đa 5 giây). Đây là bước mấu chốt giúp AI phân tích từng đoạn ngắn (1–5 câu hỏi), ngăn chặn hiện tượng quá tải bộ nhớ và hallucination.
* **Cú pháp:**
  ```bash
  py scripts/split_chunks.py -i [input_video] [-d độ_dài_chunk] [-o thư_mục_xuất]
  ```
* **Các tham số:**
  * `-i, --input`: Đường dẫn video cần chia nhỏ (**Bắt buộc**).
  * `-d, --duration`: Độ dài tối đa mỗi chunk tính bằng giây (mặc định: `5`).
  * `-o, --output-dir`: Thư mục lưu các file chunk (mặc định: `chunks`).
* **Tự động tạo thêm:**
  * `chunks/concat_list.txt`: Danh sách file theo đúng thứ tự thời gian.
  * `chunks/ghep_lai_video.bat`: Script 1-click để ghép nối lại toàn bộ chunk thành video ban đầu bất cứ lúc nào.
* **Ví dụ:**
  ```bash
  py scripts/split_chunks.py -i DBI_P2_cut.mp4 -d 5 -o chunks
  ```

---

### 🛠️ Tool 3: `extract_questions.py` (Trích Xuất Câu Hỏi)
* **Mô tả:** Quét các khung hình trong từng chunk, phát hiện slide chuyển đổi, tách câu hỏi, các lựa chọn A/B/C/D và ghi chú đáp án đúng.
* **Cú pháp:**
  ```bash
  py scripts/extract_questions.py [-c thư_mục_chunks] [-o file_json]
  ```
* **Các tham số:**
  * `-c, --chunks-dir`: Thư mục chứa các file chunk (mặc định: `chunks`).
  * `-o, --output`: Đường dẫn file JSON kết quả (mặc định: `extracted_questions.json`).

---

### 🛠️ Tool 4: `generate_word.py` (Xuất File Word Chuẩn Format)
* **Mô tả:** Đọc dữ liệu câu hỏi từ file JSON, tự động khử sạch các câu hỏi trùng lặp (do giao ranh giới 5s giữa các chunk hoặc do slide bài giảng lặp lại) và định dạng xuất ra file Word `.docx` hoàn chỉnh.
* **Quy chuẩn định dạng:**
  * `Câu [số]: [câu hỏi]`
  * `[nội dung kèm theo / thông tin slide nếu có]`
  * Mỗi phương án đáp án nằm trên **một dòng riêng**.
  * **Đáp án đúng:** Chữ màu đỏ (`#FF0000`) và in đậm.
* **Cú pháp:**
  ```bash
  py scripts/generate_word.py -i [file_json] [-o file_word]
  ```
* **Các tham số:**
  * `-i, --input`: File JSON chứa danh sách câu hỏi (**Bắt buộc**).
  * `-o, --output`: Đường dẫn file Word cần xuất (mặc định: `tong_hop_cau_hoi.docx`).
* **Định dạng JSON đầu vào (`extracted_questions.json`):**
  ```json
  [
    {
      "question": "Nội dung câu hỏi...",
      "extra": "Ghi chú phụ nếu có",
      "image": "_cropped_imgs/slide_005_crop.jpg",
      "slides": [5],
      "options": [["A", "..."], ["B", "..."], ["C", "..."], ["D", "..."]],
      "correct": ["B"]
    }
  ]
  ```
* **Ví dụ:**
  ```bash
  py scripts/generate_word.py -i extracted_questions.json -o de_thi_chuan.docx
  ```

---

### 🚀 Tool 5: `pipeline.py` (Chạy Toàn Bộ Quy Trình Chuẩn Bị V2.0)
* **Mô tả:** Tích hợp liên hoàn: (Tùy chọn) Cắt video nếu có `-e` $\rightarrow$ Chạy `extract_slides.py` (10 fps + OCR lọc trùng $\ge 90\%$) tạo thư mục `slides/`.
* **Cú pháp:**
  ```bash
  py scripts/pipeline.py [-s bắt_đầu] [-e kết_thúc] [-i video] [-o slides]
  ```
* **Ví dụ:**
  ```bash
  py scripts/pipeline.py -i DBI_P2.mp4 -o slides
  py scripts/pipeline.py -s 00:00:00 -e 1p14 -i DBI_P2.mp4
  ```
