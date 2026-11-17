import argparse
import subprocess
import sys
from pathlib import Path


def run_step(cmd: list, step_name: str):
    print("\n=======================================================")
    print(f"▶️  Đang chạy: {step_name}")
    print("=======================================================")
    res = subprocess.run(cmd)
    if res.returncode != 0:
        print(f"❌ Bước '{step_name}' thất bại với mã lỗi {res.returncode}!")
        sys.exit(res.returncode)


def main():
    parser = argparse.ArgumentParser(
        description="Pipeline V2.0: (Tùy chọn) Cắt video -> Trích xuất slide duy nhất (10 fps + OCR lọc trùng >= 90%)"
    )
    parser.add_argument("-i", "--input", help="Đường dẫn video gốc", default=None)
    parser.add_argument("-s", "--start", help="Thời gian bắt đầu (ví dụ: 00:00:00)", default="00:00:00")
    parser.add_argument("-e", "--end", help="Thời gian kết thúc (bỏ trống nếu xử lý toàn bộ video)", default=None)
    parser.add_argument("-o", "--output-dir", help="Thư mục lưu ảnh slide duy nhất (mặc định: slides)", default="slides")
    parser.add_argument("--fps", type=float, default=10.0, help="Tốc độ lấy mẫu frame/giây (mặc định: 10.0)")
    parser.add_argument("--similarity", type=float, default=0.90, help="Ngưỡng giống nhau về chữ (mặc định: 0.90)")

    args = parser.parse_args()
    scripts_dir = Path(__file__).resolve().parent

    cut_script = scripts_dir / "cut_video.py"
    extract_slides_script = scripts_dir / "extract_slides.py"

    target_video = args.input

    # Bước 1 (Tùy chọn): Cắt video nếu có mốc thời gian kết thúc -e
    if args.end:
        cut_video_file = "video_cut.mp4"
        cut_cmd = [sys.executable, str(cut_script), "-s", args.start, "-e", args.end, "-o", cut_video_file]
        if target_video:
            cut_cmd.extend(["-i", target_video])
        run_step(cut_cmd, "Bước 1: Cắt video theo khoảng thời gian yêu cầu")
        target_video = cut_video_file

    # Bước 2: Trích xuất ảnh slide duy nhất (10 fps + OCR lọc trùng >= 90%)
    extract_cmd = [
        sys.executable, str(extract_slides_script),
        "-o", args.output_dir,
        "--fps", str(args.fps),
        "--similarity", str(args.similarity),
    ]
    if target_video:
        extract_cmd.extend(["-i", target_video])

    run_step(extract_cmd, "Bước 2: Trích xuất ảnh slide duy nhất (10 fps + OCR >= 90%)")

    print("\n🎉 Pipeline V2.0 đã chuẩn bị xong các ảnh slide duy nhất!")
    print(f"📍 Ảnh slide được lưu tại thư mục: ./{args.output_dir}/")


if __name__ == "__main__":
    main()
