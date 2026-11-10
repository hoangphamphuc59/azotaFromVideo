import os
import sys
import argparse
import subprocess
from pathlib import Path
from shutil import which

def get_ffmpeg_path():
    """Tìm binary ffmpeg trên hệ thống hoặc qua thư viện imageio_ffmpeg."""
    ffmpeg_bin = which("ffmpeg")
    if ffmpeg_bin:
        return ffmpeg_bin
    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except ImportError:
        pass
    return None

def find_target_video(search_dir: Path):
    """Tự động tìm file video đầu tiên trong thư mục nếu không chỉ định."""
    video_exts = {".mp4", ".mkv", ".avi", ".mov", ".flv", ".wmv", ".webm", ".m4v"}
    for f in search_dir.iterdir():
        if f.is_file() and f.suffix.lower() in video_exts and not f.stem.endswith("_cut"):
            return f
    return None

def format_time(time_str: str) -> str:
    """
    Chuyển đổi các định dạng thời gian tự nhiên về HH:MM:SS:
    - '1p14', '1p14s', '1m14s' -> '00:01:14'
    - '74' hoặc '74s' -> '00:01:14'
    - '01:14' -> '00:01:14'
    """
    if not time_str:
        return "00:00:00"
    t = time_str.strip().lower().replace("s", "")
    for sep in ['p', 'm']:
        if sep in t:
            parts = t.split(sep)
            m = int(parts[0]) if parts[0] else 0
            s = int(parts[1]) if len(parts) > 1 and parts[1] else 0
            h = m // 60
            m = m % 60
            return f"{h:02d}:{m:02d}:{s:02d}"

    if t.isdigit():
        sec = int(t)
        h = sec // 3600
        m = (sec % 3600) // 60
        s = sec % 60
        return f"{h:02d}:{m:02d}:{s:02d}"

    colons = t.count(':')
    if colons == 1:
        return f"00:{t}"
    return t

def cut_video(input_path: Path, output_path: Path, start_time: str, end_time: str) -> bool:
    ffmpeg_exe = get_ffmpeg_path()
    if not ffmpeg_exe:
        print("[LỖI] Không tìm thấy FFmpeg trên máy. Vui lòng cài đặt ffmpeg hoặc imageio-ffmpeg.")
        return False

    start_fmt = format_time(start_time)
    end_fmt = format_time(end_time)

    print(f"🎬 [Tool Cắt Video] Đang xử lý: {input_path.name}")
    print(f"⏱️  Khoảng thời gian: {start_fmt} -> {end_fmt}")
    print(f"📁 File xuất ra: {output_path.name}")

    cmd = [
        ffmpeg_exe, "-y",
        "-ss", start_fmt,
        "-to", end_fmt,
        "-i", str(input_path),
        "-c", "copy",
        str(output_path)
    ]

    try:
        res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, errors="ignore")
        if res.returncode == 0:
            sz_mb = output_path.stat().st_size / (1024 * 1024)
            print(f"✅ Cắt video thành công! Kích thước: {sz_mb:.2f} MB")
            return True
        else:
            print("[LỖI FFmpeg]:", res.stderr[-400:])
            return False
    except Exception as e:
        print(f"[LỖI Ngoại lệ]: {e}")
        return False

def main():
    parser = argparse.ArgumentParser(description="Tool cắt video nhanh không giảm chất lượng (Lossless Stream Copy)")
    parser.add_argument("-i", "--input", help="Đường dẫn file video đầu vào (tự tìm nếu bỏ trống)", default=None)
    parser.add_argument("-s", "--start", help="Thời gian bắt đầu (mặc định: 00:00:00)", default="00:00:00")
    parser.add_argument("-e", "--end", help="Thời gian kết thúc (ví dụ: 1p14, 00:01:14)", required=True)
    parser.add_argument("-o", "--output", help="Đường dẫn file video đầu ra", default=None)

    args = parser.parse_args()
    cwd = Path.cwd()

    if args.input:
        in_path = Path(args.input)
    else:
        in_path = find_target_video(cwd)
        if not in_path:
            print("❌ Không tìm thấy video nào trong thư mục hiện tại!")
            sys.exit(1)

    if args.output:
        out_path = Path(args.output)
    else:
        out_path = in_path.parent / f"{in_path.stem}_cut{in_path.suffix}"

    success = cut_video(in_path, out_path, args.start, args.end)
    if not success:
        sys.exit(1)

if __name__ == "__main__":
    main()
