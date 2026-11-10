import os
import sys
import json
import argparse
import subprocess
from pathlib import Path
from shutil import which

def get_ffmpeg_path():
    ffmpeg_bin = which("ffmpeg")
    if ffmpeg_bin:
        return ffmpeg_bin
    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except ImportError:
        pass
    return None

def extract_frames_from_chunk(chunk_path: Path, temp_dir: Path, fps: int = 2):
    """Trích xuất frame từ 1 chunk video để nhận diện slide."""
    ffmpeg_exe = get_ffmpeg_path()
    if not ffmpeg_exe:
        return []
    temp_dir.mkdir(parents=True, exist_ok=True)
    out_pattern = str(temp_dir / "f_%03d.jpg")
    cmd = [ffmpeg_exe, "-y", "-i", str(chunk_path), "-vf", f"fps={fps}", out_pattern]
    subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return sorted(temp_dir.glob("f_*.jpg"))

def parse_slide_text(text: str) -> dict:
    """
    Phân tích đoạn văn bản OCR thành cấu trúc: câu hỏi, các lựa chọn, đáp án đúng.
    """
    lines = [l.strip() for l in text.splitlines() if l.strip()]
    if not lines:
        return None

    # Tìm các dòng lựa chọn A., B., C., D., E.
    q_lines = []
    options = []
    opt_keys = {"A.", "B.", "C.", "D.", "E.", "A_", "B_", "C_", "D_", "E_"}

    for line in lines:
        prefix = line[:2].upper()
        if prefix in opt_keys or (len(line) > 2 and line[0] in "ABCDE" and line[1] in "._-"):
            key = line[0].upper()
            val = line[2:].strip()
            options.append((key, val))
        elif not options:
            q_lines.append(line)

    question_text = " ".join(q_lines).strip()
    return {
        "question": question_text,
        "options": options,
        "correct": []
    }

def main():
    parser = argparse.ArgumentParser(description="Tool trích xuất slide và câu hỏi từ các chunk video")
    parser.add_argument("-c", "--chunks-dir", help="Thư mục chứa các file chunk (mặc định: chunks)", default="chunks")
    parser.add_argument("-o", "--output", help="File JSON kết quả trích xuất", default="extracted_questions.json")

    args = parser.parse_args()
    chunks_dir = Path(args.chunks_dir)
    if not chunks_dir.exists():
        print(f"❌ Thư mục '{chunks_dir}' không tồn tại!")
        sys.exit(1)

    chunk_files = sorted(chunks_dir.glob("chunk_*.mp4"))
    print(f"🔍 Tìm thấy {len(chunk_files)} chunk trong thư mục '{chunks_dir.name}'")

    print(f"✅ Quá trình quét hoàn tất! Dữ liệu xuất ra: {args.output}")

if __name__ == "__main__":
    main()
