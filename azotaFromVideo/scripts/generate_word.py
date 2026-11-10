import os
import sys
import json
import argparse
from pathlib import Path
from docx import Document
from docx.shared import Pt, RGBColor, Inches
from docx.enum.text import WD_ALIGN_PARAGRAPH

def export_to_word(questions: list, output_path: Path, title_text: str = "TỔNG HỢP CÂU HỎI TRẮC NGHIỆM"):
    """
    Xuất danh sách câu hỏi ra file Word chuẩn format:
    - Câu [số]: [câu hỏi]
    - [nội dung kèm theo / thông tin slide]
    - Mỗi đáp án một dòng riêng biệt.
    - Đáp án đúng được in chữ MÀU ĐỎ và IN ĐẬM.
    """
    doc = Document()

    # Tiêu đề tài liệu
    title = doc.add_paragraph()
    r_title = title.add_run(title_text)
    r_title.bold = True
    r_title.font.size = Pt(16)
    r_title.font.color.rgb = RGBColor(0, 51, 153)
    title.alignment = WD_ALIGN_PARAGRAPH.CENTER

    sub = doc.add_paragraph()
    r_sub = sub.add_run(f"Tổng số câu hỏi: {len(questions)} câu (Đã lọc sạch trùng lặp)")
    r_sub.italic = True
    r_sub.font.size = Pt(11)
    r_sub.font.color.rgb = RGBColor(100, 100, 100)
    sub.alignment = WD_ALIGN_PARAGRAPH.CENTER

    doc.add_paragraph() # Spacing

    for idx, q in enumerate(questions, 1):
        # 1. Dòng Câu hỏi
        p_q = doc.add_paragraph()
        p_q.paragraph_format.space_before = Pt(8)
        p_q.paragraph_format.space_after = Pt(2)

        r_num = p_q.add_run(f"Câu {idx}: ")
        r_num.bold = True
        r_num.font.size = Pt(12)

        r_text = p_q.add_run(q.get("question", "").strip())
        r_text.font.size = Pt(12)

        # 2. Dòng Nội dung kèm theo / Slide / Giải thích nếu có
        extra_info = []
        if q.get("slides"):
            slides_str = ", ".join(str(s) for s in q["slides"])
            extra_info.append(f"(Slide {slides_str})")
        if q.get("extra"):
            extra_info.append(q["extra"])

        if extra_info:
            p_extra = doc.add_paragraph()
            p_extra.paragraph_format.space_after = Pt(4)
            r_extra = p_extra.add_run(" - ".join(extra_info))
            r_extra.italic = True
            r_extra.font.size = Pt(10.5)
            r_extra.font.color.rgb = RGBColor(100, 100, 100)

        # 3. Các đáp án lựa chọn
        options = q.get("options", [])
        correct_list = [c.upper().strip() for c in q.get("correct", [])]

        for opt in options:
            if isinstance(opt, (list, tuple)) and len(opt) == 2:
                opt_key, opt_val = opt[0], opt[1]
                line_str = f"{opt_key}. {opt_val}"
            else:
                line_str = str(opt).strip()
                opt_key = line_str[:1].upper() if line_str else ""

            p_opt = doc.add_paragraph()
            p_opt.paragraph_format.space_after = Pt(2)
            p_opt.paragraph_format.left_indent = Inches(0.25)

            r_opt = p_opt.add_run(line_str)
            r_opt.font.size = Pt(11)

            # Đáp án đúng: Màu chữ đỏ + In đậm
            if opt_key in correct_list:
                r_opt.font.color.rgb = RGBColor(255, 0, 0)
                r_opt.bold = True
            else:
                r_opt.font.color.rgb = RGBColor(0, 0, 0)

        # Khoảng cách giữa các câu hỏi
        p_div = doc.add_paragraph()
        p_div.paragraph_format.space_after = Pt(6)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    doc.save(str(output_path))
    print(f"✅ Đã tạo file Word thành công tại: {output_path.resolve()}")
    return True

def deduplicate_questions(questions: list) -> list:
    """Loại bỏ câu hỏi trùng lặp dựa trên chuỗi câu hỏi chuẩn hóa."""
    seen = {}
    unique = []
    for q in questions:
        norm = " ".join(q.get("question", "").lower().split())
        if not norm:
            continue
        if norm not in seen:
            seen[norm] = len(unique)
            unique.append(q)
        else:
            # Gộp thông tin slide nếu có
            idx = seen[norm]
            existing_slides = set(unique[idx].get("slides", []))
            new_slides = set(q.get("slides", []))
            unique[idx]["slides"] = sorted(list(existing_slides.union(new_slides)))
    return unique

def main():
    parser = argparse.ArgumentParser(description="Tool xuất câu hỏi ra file Word chuẩn format trắc nghiệm (đáp án đúng màu đỏ)")
    parser.add_argument("-i", "--input", help="File JSON chứa danh sách câu hỏi", required=True)
    parser.add_argument("-o", "--output", help="Đường dẫn file Word đầu ra (.docx)", default="tong_hop_cau_hoi.docx")

    args = parser.parse_args()
    in_file = Path(args.input)
    if not in_file.exists():
        print(f"❌ File '{in_file}' không tồn tại!")
        sys.exit(1)

    with open(in_file, "r", encoding="utf-8") as f:
        data = json.load(f)

    if isinstance(data, dict) and "questions" in data:
        q_list = data["questions"]
    elif isinstance(data, list):
        q_list = data
    else:
        print("❌ Dữ liệu JSON không đúng định dạng danh sách câu hỏi!")
        sys.exit(1)

    # Lọc trùng lặp
    cleaned_list = deduplicate_questions(q_list)
    print(f"📋 Tổng số câu ban đầu: {len(q_list)} -> Sau lọc trùng: {len(cleaned_list)}")

    out_file = Path(args.output)
    export_to_word(cleaned_list, out_file)

if __name__ == "__main__":
    main()
