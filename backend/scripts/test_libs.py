"""
PDFMiner / Unstructured 동작 확인 스크립트.

사용법:
    python scripts/test_libs.py <pdf_path>
"""

import sys
from pathlib import Path


def test_pdfminer(pdf_path: str) -> str:
    from pdfminer.high_level import extract_text

    print("=" * 60)
    print("[PDFMiner] 텍스트 추출")
    print("=" * 60)
    text = extract_text(pdf_path)
    print(text[:1000])
    print(f"\n총 글자 수: {len(text)}")
    return text


def test_unstructured(text: str) -> None:
    from unstructured.partition.text import partition_text

    print("\n" + "=" * 60)
    print("[Unstructured] partition_text 엘리먼트 파싱")
    print("=" * 60)
    elements = partition_text(text=text)
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

    extracted_text = test_pdfminer(path)
    test_unstructured(extracted_text)
