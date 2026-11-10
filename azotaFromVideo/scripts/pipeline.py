import os
import sys
import argparse
import subprocess
from pathlib import Path

def run_step(cmd: list, step_name: str):
    print(f"\n=======================================================")
    print(f"▶️  Đang chạy: {step_name}")
    print(f"=======================================================")
    res = subprocess.run(cmd)
    if res.returncode != 0:
        print(f"❌ Bước '{step_name}' thất bại với mã lỗi {res.returncode}!")
        sys.exit(res.returncode)

def main():
    parser = argparse.ArgumentParser(description="Pipeline tự động: Cắt video -> Chia chunk 5s -> Trích xuất câu hỏi -> Xuất file Word")
    parser.add_argument("-i", "--input", help="Đường dẫn video gốc", default=None)
    parser.add_argument("-s", "--start", help="Thời gian bắt đầu (ví dụ: 00:00:00)", default="00:00:00")
    parser.add_argument("-e", "--end", help="Thời gian kết thúc (ví dụ: 1p14, 00:01:14)", required=True)
    parser.add_argument("-o", "--output", help="File Word kết quả (mặc định: tong_hop_cau_hoi.docx)", default="tong_hop_cau_hoi.docx")

    args = parser.parse_args()
    scripts_dir = Path(__file__).resolve().parent

    cut_script = scripts_dir / "cut_video.py"
    split_script = scripts_dir / "split_chunks.py"
    word_script = scripts_dir / "generate_word.py"

    # Bước 1: Cắt video
    cut_video_file = "video_cut.mp4"
    cut_cmd = [sys.executable, str(cut_script), "-s", args.start, "-e", args.end, "-o", cut_video_file]
    if args.input:
        cut_cmd.extend(["-i", args.input])
    run_step(cut_cmd, "Bước 1: Cắt video chính xác theo thời gian yêu cầu")

    # Bước 2: Chia nhỏ thành các chunk <= 5s
    chunks_folder = "chunks"
    split_cmd = [sys.executable, str(split_script), "-i", cut_video_file, "-d", "5", "-o", chunks_folder]
    run_step(split_cmd, "Bước 2: Chia nhỏ video thành các chunk <= 5s (chống AI quá tải)")

    print("\n🎉 Pipeline đã chuẩn bị xong các chunk video hoàn chỉnh!")
    print(f"📍 Các chunk được lưu tại thư mục: ./{chunks_folder}/")

if __name__ == "__main__":
    main()
