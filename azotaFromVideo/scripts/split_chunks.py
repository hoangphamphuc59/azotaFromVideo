import os
import sys
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

def split_into_chunks(input_video: Path, output_dir: Path, max_duration: int = 5) -> bool:
    ffmpeg_exe = get_ffmpeg_path()
    if not ffmpeg_exe:
        print("[LỖI] Không tìm thấy FFmpeg!")
        return False

    output_dir.mkdir(parents=True, exist_ok=True)

    # Dọn dẹp các chunk cũ nếu có
    for f in output_dir.glob("chunk_*.mp4"):
        try:
            f.unlink()
        except Exception:
            pass

    print(f"🎬 [Tool Chia Chunk] Đang chia nhỏ video: {input_video.name}")
    print(f"⏱️  Độ dài tối đa mỗi chunk: {max_duration}s")
    print(f"📂 Thư mục xuất: {output_dir.name}/")

    output_pattern = str(output_dir / "chunk_%03d.mp4")

    # Ép keyframe cố định và cắt segment
    cmd = [
        ffmpeg_exe, "-y",
        "-i", str(input_video),
        "-c:v", "libx264",
        "-crf", "17",
        "-preset", "fast",
        "-force_key_frames", f"expr:gte(t,n_forced*{max_duration})",
        "-c:a", "aac",
        "-b:a", "128k",
        "-f", "segment",
        "-segment_time", str(max_duration),
        "-segment_start_number", "1",
        "-reset_timestamps", "1",
        output_pattern
    ]

    try:
        subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
    except subprocess.CalledProcessError as e:
        print(f"[LỖI Chia Chunk]: {e}")
        return False

    chunks = sorted(output_dir.glob("chunk_*.mp4"))
    print(f"✅ Đã tạo thành công {len(chunks)} chunk video!")

    # Tạo file danh sách ghép nối
    concat_txt = output_dir / "concat_list.txt"
    with open(concat_txt, "w", encoding="utf-8") as f:
        for c in chunks:
            f.write(f"file '{c.name}'\n")

    # Tạo batch script để người dùng click đúp là ghép nối lại
    merge_bat = output_dir / "ghep_lai_video.bat"
    bat_code = f"""@echo off
chcp 65001 >nul
echo Đang ghép nối toàn bộ các chunk lại thành video gốc...
"{ffmpeg_exe}" -y -f concat -safe 0 -i concat_list.txt -c copy ..\\video_da_ghep.mp4
echo.
echo ✅ Ghép hoàn tất! File đã được lưu tại: video_da_ghep.mp4
echo.
pause
"""
    with open(merge_bat, "w", encoding="utf-8") as f:
        f.write(bat_code)

    return True

def main():
    parser = argparse.ArgumentParser(description="Tool chia video thành các đoạn vi mô <= 5s (đảm bảo AI không quá tải)")
    parser.add_argument("-i", "--input", help="Đường dẫn video cần chia chunk", required=True)
    parser.add_argument("-d", "--duration", help="Độ dài tối đa mỗi chunk (giây, mặc định: 5)", type=int, default=5)
    parser.add_argument("-o", "--output-dir", help="Thư mục lưu các chunk (mặc định: chunks)", default="chunks")

    args = parser.parse_args()
    in_path = Path(args.input)
    if not in_path.exists():
        print(f"❌ File '{in_path}' không tồn tại!")
        sys.exit(1)

    out_dir = Path(args.output_dir)
    success = split_into_chunks(in_path, out_dir, args.duration)
    if not success:
        sys.exit(1)

if __name__ == "__main__":
    main()
