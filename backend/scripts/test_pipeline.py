"""
전체 파이프라인 동작 확인 스크립트.
extractor → parser 순서로 실행하고 결과를 출력한다.

사용법:
    # PDF 테스트
    python scripts/test_pipeline.py --pdf path/to/contract.pdf

    # 이미지 테스트
    python scripts/test_pipeline.py --image path/to/contract.jpg

    # 둘 다 한 번에
    python scripts/test_pipeline.py --pdf a.pdf --image b.jpg
"""

import argparse
import json
import sys
from pathlib import Path

# backend/ 디렉터리를 경로에 추가
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core.extractor import extract_text
from core.parser import parse_clauses


def _divider(title: str) -> None:
    print(f"\n{'=' * 60}")
    print(f"  {title}")
    print("=" * 60)


def run_pipeline(file_path: Path) -> None:
    _divider(f"파일: {file_path.name}")

    data = file_path.read_bytes()
    suffix = file_path.suffix.lower()
    content_type = "application/pdf" if suffix == ".pdf" else f"image/{suffix.lstrip('.')}"

    # ── 1단계: 텍스트 추출 ──────────────────────────────
    print("\n[1] 텍스트 추출 중...")
    try:
        text = extract_text(file_path.name, data, content_type)
    except Exception as e:
        print(f"  오류: {e}")
        return

    print(f"  추출 완료 — {len(text)}자")
    print("\n  [원문 미리보기 — 첫 300자]")
    print("  " + text[:300].replace("\n", "\n  "))

    # ── 2단계: 조항 파싱 ────────────────────────────────
    print("\n[2] 조항 파싱 중...")
    try:
        clauses = parse_clauses(text)
    except Exception as e:
        print(f"  오류: {e}")
        return

    print(f"  파싱 완료 — {len(clauses)}개 조항\n")

    for c in clauses:
        preview = c["text"][:120].replace("\n", " ")
        print(f"  [{c['clause_index']:>3}] {preview}")

    # ── JSON 전체 덤프 (디버그용) ────────────────────────
    print("\n[3] JSON 전체 출력")
    print(json.dumps(clauses, ensure_ascii=False, indent=2))


def main() -> None:
    parser = argparse.ArgumentParser(description="LegaLenz 파이프라인 테스트")
    parser.add_argument("--pdf", type=Path, help="테스트할 PDF 파일 경로")
    parser.add_argument("--image", type=Path, help="테스트할 이미지 파일 경로")
    args = parser.parse_args()

    if not args.pdf and not args.image:
        parser.print_help()
        sys.exit(1)

    for path in filter(None, [args.pdf, args.image]):
        if not path.exists():
            print(f"파일 없음: {path}")
            continue
        run_pipeline(path)


if __name__ == "__main__":
    main()
