import argparse
import difflib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from shutil import which

import numpy as np
from PIL import Image

try:
    from rapidfuzz import fuzz
    HAS_RAPIDFUZZ = True
except ImportError:
    HAS_RAPIDFUZZ = False


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
    """Tự động tìm file video trong thư mục nếu không chỉ định."""
    video_exts = {".mp4", ".mkv", ".avi", ".mov", ".flv", ".wmv", ".webm", ".m4v"}
    candidates = [
        f for f in sorted(search_dir.iterdir())
        if f.is_file() and f.suffix.lower() in video_exts
    ]
    # Ưu tiên file *_cut nếu có, nếu không lấy file đầu tiên
    for f in candidates:
        if f.stem.endswith("_cut"):
            return f
    return candidates[0] if candidates else None


def normalize_text(text: str) -> str:
    """Chuẩn hóa văn bản OCR để so sánh độ tương đồng chính xác hơn."""
    if not text:
        return ""
    text = text.lower()
    text = re.sub(r"\s+", " ", text).strip()
    return text


def text_similarity(t1: str, t2: str) -> float:
    """Tính độ tương đồng giữa 2 chuỗi văn bản (0.0 -> 1.0)."""
    n1 = normalize_text(t1)
    n2 = normalize_text(t2)
    if not n1 and not n2:
        return 1.0
    if not n1 or not n2:
        return 0.0
    if HAS_RAPIDFUZZ:
        return fuzz.ratio(n1, n2) / 100.0
    return difflib.SequenceMatcher(None, n1, n2).ratio()


def sample_frames_ffmpeg(video_path: Path, temp_dir: Path, fps: float = 10.0) -> list[Path]:
    """Dùng FFmpeg trích xuất frame ở tốc độ fps (mặc định 10 fps = 0.1s/frame)."""
    ffmpeg_exe = get_ffmpeg_path()
    if not ffmpeg_exe:
        print("❌ [LỖI] Không tìm thấy FFmpeg! Vui lòng cài ffmpeg hoặc imageio-ffmpeg.")
        sys.exit(1)

    temp_dir.mkdir(parents=True, exist_ok=True)
    out_pattern = str(temp_dir / "frame_%06d.jpg")

    print(f"🎞️  Đang trích xuất frame ở tốc độ {fps} fps (1 frame / {1/fps:.2f}s)...")
    cmd = [
        ffmpeg_exe, "-y",
        "-i", str(video_path),
        "-vf", f"fps={fps}",
        "-q:v", "2",
        out_pattern
    ]
    res = subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True, errors="ignore")
    if res.returncode != 0:
        print(f"❌ [LỖI FFmpeg]: {res.stderr[-400:]}")
        sys.exit(1)

    frames = sorted(temp_dir.glob("frame_*.jpg"))
    print(f"📸 Tổng số frame đã lấy mẫu: {len(frames)}")
    return frames


def frame_signature(img_path: Path, size: tuple[int, int] = (128, 72)) -> np.ndarray:
    """Tạo vector chữ ký ảnh xám thu nhỏ để so sánh sai khác pixel siêu nhanh."""
    with Image.open(img_path) as im:
        gray = im.convert("L").resize(size, Image.Resampling.BILINEAR)
        return np.asarray(gray, dtype=np.float32)


def prefilter_visual_segments(frames: list[Path], pixel_diff_threshold: float = 1.5, keep_first: bool = False) -> list[tuple[int, Path]]:
    """
    Tầng lọc 1 (Siêu nhanh): Gom các frame liên tiếp giống hệt nhau về mặt hình ảnh.
    Trả về danh sách (frame_index_1based, frame_path) đại diện cho từng đoạn ổn định.
    """
    if not frames:
        return []

    candidates = []
    seg_start_idx = 0
    seg_end_idx = 0
    prev_sig = frame_signature(frames[0])

    for i in range(1, len(frames)):
        curr_sig = frame_signature(frames[i])
        diff = float(np.mean(np.abs(curr_sig - prev_sig)))
        if diff <= pixel_diff_threshold:
            seg_end_idx = i
        else:
            chosen_idx = seg_start_idx if keep_first else seg_end_idx
            candidates.append((chosen_idx + 1, frames[chosen_idx]))
            seg_start_idx = i
            seg_end_idx = i
            prev_sig = curr_sig

    # Đóng đoạn cuối cùng
    chosen_idx = seg_start_idx if keep_first else seg_end_idx
    candidates.append((chosen_idx + 1, frames[chosen_idx]))

    print(f"⚡ Tầng lọc hình ảnh: {len(frames)} frame -> còn {len(candidates)} frame ứng viên có biến đổi.")
    return candidates


def detect_ocr_backend(preferred: str = "auto") -> str:
    """Tự động chọn OCR backend khả dụng trên máy."""
    if preferred != "auto":
        return preferred

    try:
        import rapidocr_onnxruntime  # noqa: F401
        return "rapidocr"
    except ImportError:
        pass

    try:
        import pytesseract  # noqa: F401
        if which("tesseract"):
            return "tesseract"
    except ImportError:
        pass

    if sys.platform == "win32":
        return "winocr"

    print("❌ Không tìm thấy thư viện OCR nào (rapidocr-onnxruntime / pytesseract / Windows OCR).")
    sys.exit(1)


def run_ocr_batch_rapidocr(image_paths: list[Path]) -> dict[str, str]:
    from rapidocr_onnxruntime import RapidOCR
    engine = RapidOCR()
    results = {}
    for p in image_paths:
        res, _ = engine(str(p))
        if res:
            results[str(p)] = "\n".join(item[1] for item in res if item and len(item) > 1)
        else:
            results[str(p)] = ""
    return results


def run_ocr_batch_tesseract(image_paths: list[Path]) -> dict[str, str]:
    import pytesseract
    results = {}
    for p in image_paths:
        with Image.open(p) as im:
            try:
                text = pytesseract.image_to_string(im, lang="vie+eng")
            except Exception:
                text = pytesseract.image_to_string(im)
            results[str(p)] = text or ""
    return results


def run_ocr_batch_winocr(image_paths: list[Path]) -> dict[str, str]:
    """Chạy Windows Built-in OCR (Windows.Media.Ocr) theo lô trong 1 tiến trình PowerShell."""
    with tempfile.TemporaryDirectory() as tmp:
        tmp_dir = Path(tmp)
        list_file = tmp_dir / "images.txt"
        out_file = tmp_dir / "ocr_results.json"
        ps_file = tmp_dir / "run_ocr.ps1"

        list_file.write_text("\n".join(str(p.resolve()) for p in image_paths), encoding="utf-8")

        ps_script = r"""
param([string]$ListPath, [string]$OutPath)
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
Add-Type -AssemblyName System.Runtime.WindowsRuntime
[Windows.Media.Ocr.OcrEngine, Windows.Foundation, ContentType=WindowsRuntime] | Out-Null
[Windows.Graphics.Imaging.BitmapDecoder, Windows.Foundation, ContentType=WindowsRuntime] | Out-Null
[Windows.Storage.StorageFile, Windows.Foundation, ContentType=WindowsRuntime] | Out-Null

$asTaskGeneric = ([System.WindowsRuntimeSystemExtensions].GetMethods() | Where-Object {
    $_.Name -eq 'AsTask' -and $_.GetParameters().Count -eq 1 -and $_.GetParameters()[0].ParameterType.Name -eq 'IAsyncOperation`1'
})[0]

function Await($WinRtTask, $ResultType) {
    $asTask = $asTaskGeneric.MakeGenericMethod($ResultType)
    $netTask = $asTask.Invoke($null, @($WinRtTask))
    $netTask.Wait(-1) | Out-Null
    return $netTask.Result
}

$langs = [Windows.Media.Ocr.OcrEngine]::AvailableRecognizerLanguages
$viLang = $langs | Where-Object { $_.LanguageTag -like 'vi*' } | Select-Object -First 1
$enLang = $langs | Where-Object { $_.LanguageTag -like 'en*' } | Select-Object -First 1
if ($viLang) {
    $engine = [Windows.Media.Ocr.OcrEngine]::TryCreateFromLanguage($viLang)
} elseif ($enLang) {
    $engine = [Windows.Media.Ocr.OcrEngine]::TryCreateFromLanguage($enLang)
} else {
    $engine = [Windows.Media.Ocr.OcrEngine]::TryCreateFromUserProfileLanguages()
}

$results = @{}
$paths = Get-Content -Path $ListPath -Encoding UTF8
foreach ($imgPath in $paths) {
    if ([string]::IsNullOrWhiteSpace($imgPath)) { continue }
    try {
        $file = Await ([Windows.Storage.StorageFile]::GetFileFromPathAsync($imgPath)) ([Windows.Storage.StorageFile])
        $stream = Await ($file.OpenAsync([Windows.Storage.FileAccessMode]::Read)) ([Windows.Storage.Streams.IRandomAccessStream])
        $decoder = Await ([Windows.Graphics.Imaging.BitmapDecoder]::CreateAsync($stream)) ([Windows.Graphics.Imaging.BitmapDecoder])
        $bitmap = Await ($decoder.GetSoftwareBitmapAsync()) ([Windows.Graphics.Imaging.SoftwareBitmap])
        $ocrRes = Await ($engine.RecognizeAsync($bitmap)) ([Windows.Media.Ocr.OcrResult])
        $results[$imgPath] = $ocrRes.Text
        $stream.Dispose()
    } catch {
        $results[$imgPath] = ""
    }
}

$json = $results | ConvertTo-Json -Depth 3
[System.IO.File]::WriteAllText($OutPath, $json, [System.Text.UTF8Encoding]::new($false))
"""
        ps_file.write_text(ps_script, encoding="utf-8")

        cmd = [
            "powershell", "-NoProfile", "-ExecutionPolicy", "Bypass",
            "-File", str(ps_file),
            "-ListPath", str(list_file),
            "-OutPath", str(out_file)
        ]
        res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, errors="ignore")
        if res.returncode != 0 or not out_file.exists():
            print(f"❌ [LỖI Windows OCR]: {res.stderr[-400:]}")
            sys.exit(1)

        raw = json.loads(out_file.read_text(encoding="utf-8"))
        # Map lại theo str(p) ban đầu
        resolved_map = {str(p.resolve()): str(p) for p in image_paths}
        return {resolved_map.get(k, k): (v or "") for k, v in raw.items()}


def run_ocr(image_paths: list[Path], backend: str) -> dict[str, str]:
    """Chạy OCR trên danh sách ảnh ứng viên."""
    print(f"🔤 Đang chạy OCR ({backend}) trên {len(image_paths)} frame ứng viên...")
    if backend == "rapidocr":
        return run_ocr_batch_rapidocr(image_paths)
    if backend == "tesseract":
        return run_ocr_batch_tesseract(image_paths)
    if backend == "winocr":
        return run_ocr_batch_winocr(image_paths)
    raise ValueError(f"OCR backend không hợp lệ: {backend}")


def is_blank_frame(img_path: Path, std_threshold: float = 3.0) -> bool:
    """Kiểm tra frame có phải màn hình trống hoàn toàn (đen/trắng đồng nhất) không."""
    with Image.open(img_path) as im:
        gray = np.asarray(im.convert("L"), dtype=np.float32)
        return float(np.std(gray)) < std_threshold


def deduplicate_by_text(
    candidates: list[tuple[int, Path]],
    ocr_texts: dict[str, str],
    similarity_threshold: float = 0.90,
    keep_first: bool = False,
) -> list[dict]:
    """
    Tầng lọc 2 (So sánh chữ T1 vs T2):
    - Chỉ bỏ qua frame trống hoàn toàn (màn hình đen/trắng đồng nhất).
    - Nếu frame có nội dung hình ảnh nhưng OCR không đọc được chữ (ví dụ câu hỏi ảnh/toán ngắn),
      vẫn giữ lại để không làm mất câu hỏi.
    - Nếu độ giống nhau giữa T_curr và T_group >= similarity_threshold (90%):
      coi là cùng một câu hỏi -> gộp lại và giữ frame cuối cùng (mặc định) để bắt trọn đáp án.
    """
    groups = []
    for frame_idx, frame_path in candidates:
        text = ocr_texts.get(str(frame_path), "").strip()
        if not text and is_blank_frame(frame_path):
            continue

        if not groups:
            groups.append({
                "frame_idx": frame_idx,
                "frame_path": frame_path,
                "text": text,
            })
            continue

        prev_group = groups[-1]
        # Nếu một trong hai không đọc được OCR nhưng khác biệt hình ảnh -> giữ tách riêng
        if not text or not prev_group["text"]:
            groups.append({
                "frame_idx": frame_idx,
                "frame_path": frame_path,
                "text": text,
            })
            continue

        sim = text_similarity(prev_group["text"], text)
        if sim >= similarity_threshold:
            # Cùng một câu hỏi: mặc định giữ frame sau cùng (để lấy cả trạng thái đã tô đáp án)
            if not keep_first:
                prev_group["frame_idx"] = frame_idx
                prev_group["frame_path"] = frame_path
            if len(normalize_text(text)) >= len(normalize_text(prev_group["text"])):
                prev_group["text"] = text
        else:
            groups.append({
                "frame_idx": frame_idx,
                "frame_path": frame_path,
                "text": text,
            })

    return groups


def export_slides(groups: list[dict], output_dir: Path, fps: float) -> list[dict]:
    """Xuất các ảnh slide duy nhất ra thư mục output_dir và tạo file index."""
    output_dir.mkdir(parents=True, exist_ok=True)
    for old in output_dir.glob("slide_*.jpg"):
        try:
            old.unlink()
        except OSError:
            pass

    index_data = []
    for idx, grp in enumerate(groups, 1):
        dest = output_dir / f"slide_{idx:03d}.jpg"
        shutil.copy2(grp["frame_path"], dest)
        timestamp_sec = round((grp["frame_idx"] - 1) / fps, 2)
        index_data.append({
            "slide_number": idx,
            "file": dest.name,
            "timestamp_sec": timestamp_sec,
            "frame_index": grp["frame_idx"],
            "ocr_preview": grp["text"][:200]
        })

    index_file = output_dir / "slides_index.json"
    index_file.write_text(json.dumps(index_data, ensure_ascii=False, indent=2), encoding="utf-8")
    return index_data


def main():
    parser = argparse.ArgumentParser(
        description="Tool V2.0: Trích xuất các ảnh slide câu hỏi duy nhất từ video (10 fps + OCR lọc trùng >= 90%)"
    )
    parser.add_argument("-i", "--input", help="Đường dẫn file video đầu vào (tự tìm nếu bỏ trống)", default=None)
    parser.add_argument("-o", "--output-dir", help="Thư mục lưu ảnh slide duy nhất (mặc định: slides)", default="slides")
    parser.add_argument("--fps", type=float, default=10.0, help="Tốc độ lấy mẫu frame/giây (mặc định: 10.0 = 0.1s/frame)")
    parser.add_argument("--similarity", type=float, default=0.90, help="Ngưỡng giống nhau về chữ để gộp trùng (mặc định: 0.90)")
    parser.add_argument("--pixel-diff", type=float, default=1.5, help="Ngưỡng sai khác pixel để lọc frame tĩnh (mặc định: 1.5)")
    parser.add_argument("--ocr-backend", choices=["auto", "rapidocr", "tesseract", "winocr"], default="auto", help="OCR engine (mặc định: auto)")
    parser.add_argument("--keep-first", action="store_true", help="Giữ frame đầu tiên thay vì frame cuối cùng trong mỗi nhóm câu hỏi")
    parser.add_argument("--keep-temp", action="store_true", help="Giữ lại thư mục frame tạm để debug")

    args = parser.parse_args()
    cwd = Path.cwd()

    if args.input:
        video_path = Path(args.input)
    else:
        video_path = find_target_video(cwd)
        if not video_path:
            print("❌ Không tìm thấy video nào trong thư mục hiện tại!")
            sys.exit(1)

    if not video_path.exists():
        print(f"❌ File video '{video_path}' không tồn tại!")
        sys.exit(1)

    output_dir = Path(args.output_dir)
    temp_dir = cwd / "_tmp_frames"
    if temp_dir.exists():
        shutil.rmtree(temp_dir, ignore_errors=True)

    try:
        frames = sample_frames_ffmpeg(video_path, temp_dir, fps=args.fps)
        if not frames:
            print("❌ Không trích xuất được frame nào từ video!")
            sys.exit(1)

        candidates = prefilter_visual_segments(
            frames,
            pixel_diff_threshold=args.pixel_diff,
            keep_first=args.keep_first,
        )

        backend = detect_ocr_backend(args.ocr_backend)
        candidate_paths = [p for _, p in candidates]
        ocr_texts = run_ocr(candidate_paths, backend=backend)

        groups = deduplicate_by_text(
            candidates,
            ocr_texts,
            similarity_threshold=args.similarity,
            keep_first=args.keep_first,
        )

        index_data = export_slides(groups, output_dir, fps=args.fps)
        print(f"✅ Hoàn tất! Đã lọc ra {len(index_data)} ảnh slide câu hỏi duy nhất tại: {output_dir}/")
    finally:
        if not args.keep_temp and temp_dir.exists():
            shutil.rmtree(temp_dir, ignore_errors=True)


if __name__ == "__main__":
    main()
