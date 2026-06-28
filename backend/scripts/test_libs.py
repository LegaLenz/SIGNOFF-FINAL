"""
PDFMiner / Unstructured 동작 확인 스크립트.

사용법:
    python scripts/test_libs.py <pdf_path>
"""

import sys
from pathlib import Path


def test_pdfminer(pdf_path: str) -> None:
    from pdfminer.high_level import extract_text

    print("=" * 60)
    print("[PDFMiner] 텍스트 추출")
    print("=" * 60)
    text = extract_text(pdf_path)
    print(text[:1000])
    print(f"\n총 글자 수: {len(text)}")


def test_unstructured(pdf_path: str) -> None:
    from unstructured.partition.pdf import partition_pdf

    print("\n" + "=" * 60)
    print("[Unstructured] 엘리먼트 파싱")
    print("=" * 60)
    elements = partition_pdf(pdf_path)
    for el in elements[:20]:
        print(f"[{type(el).__name__}] {str(el)[:120]}")
    print(f"\n총 엘리먼트 수: {len(elements)}")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("사용법: python scripts/test_libs.py <pdf_path>")
        sys.exit(1)

    path = sys.argv[1]
    if not Path(path).exists():
        print(f"파일을 찾을 수 없습니다: {path}")
        sys.exit(1)

    test_pdfminer(path)
    test_unstructured(path)
