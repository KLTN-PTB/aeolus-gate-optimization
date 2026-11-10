"""
Merge all markdown (.md) files in remediation_evidence into a single markdown file,
preserving the exact verbatim content of every file.
"""
import pathlib
import sys

def main():
    base_dir = pathlib.Path("remediation_evidence").resolve()
    if not base_dir.exists():
        print(f"Error: Directory {base_dir} does not exist.")
        sys.exit(1)

    out_file = base_dir / "ALL_REMEDIATION_EVIDENCE.md"

    # Find all .md files except the target output file itself
    md_files = sorted([
        p for p in base_dir.rglob("*.md")
        if p.is_file() and p.resolve() != out_file.resolve()
    ])

    print(f"Total markdown files found: {len(md_files)}")

    with open(out_file, "w", encoding="utf-8") as out_f:
        out_f.write("# TỔNG HỢP TOÀN BỘ HỒ SƠ BẰNG CHỨNG REMEDIATION VÀ KHÓA LUẬN (G0 - G9)\n")
        out_f.write("## DỰ ÁN: AEOLUS GATE OPTIMIZATION\n\n")
        out_f.write("> **GHI CHÚ QUAN TRỌNG:** Tài liệu này được gộp tự động từ toàn bộ 95 tệp báo cáo Markdown (.md) trong thư mục `remediation_evidence`.\n")
        out_f.write("> Toàn bộ nội dung gốc của từng tệp được giữ nguyên vẹn 100%, không bị xóa bỏ, rút gọn hay thay đổi bất kỳ ký tự nào.\n\n")
        out_f.write("---\n\n")
        out_f.write("## DANH MỤC 95 TỆP BÁO CÁO ĐƯỢC GỘP\n\n")

        for idx, f in enumerate(md_files, 1):
            rel = f.relative_to(base_dir).as_posix()
            anchor = f"file-{rel.replace('/', '-').replace('_', '-').replace('.', '-').lower()}"
            out_f.write(f"{idx:02d}. [`{rel}`](#{anchor})\n")

        out_f.write("\n---\n\n")

        for idx, f in enumerate(md_files, 1):
            rel = f.relative_to(base_dir).as_posix()
            anchor = f"file-{rel.replace('/', '-').replace('_', '-').replace('.', '-').lower()}"
            content = f.read_text(encoding="utf-8")

            out_f.write(f'<a id="{anchor}"></a>\n\n')
            out_f.write("# ==============================================================================\n")
            out_f.write(f"# [{idx:02d}/95] TỆP NGUỒN: remediation_evidence/{rel}\n")
            out_f.write("# ==============================================================================\n\n")
            out_f.write(content)
            if not content.endswith("\n"):
                out_f.write("\n")
            out_f.write("\n\n")

    print(f"Successfully generated: {out_file}")
    print(f"Total size: {out_file.stat().st_size} bytes")

if __name__ == "__main__":
    main()
