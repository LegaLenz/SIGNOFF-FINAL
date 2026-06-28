"""
공정거래위원회 표준계약서 전처리 파이프라인.

data/standard_contracts/ 안의 PDF들을 읽어
조항 단위로 분리한 뒤 JSON으로 저장한다.

출력 위치: data/standard_contracts/processed/
출력 형식: [{"contract_name": str, "clause_index": int, "text": str}, ...]

사용법:
    python scripts/preprocess_contracts.py
    python scripts/preprocess_contracts.py --input data/standard_contracts --output data/processed
"""

import argparse
import json
import sys
from pathlib import Path

from pdfminer.high_level import extract_text

# 프로젝트 루트를 sys.path에 추가 (backend/ 기준 실행 시)
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from core.parser import parse_clauses


def extract_pdf_text(pdf_path: Path) -> str:
    return extract_text(str(pdf_path))


def process_pdf(pdf_path: Path) -> list[dict]:
    raw = extract_pdf_text(pdf_path)
    clauses = parse_clauses(raw)
    return [
        {
            "contract_name": pdf_path.stem,
            "clause_index": c.index,
            "text": c.text,
        }
        for c in clauses
        if c.text.strip()  # 빈 조항 제외
    ]


def run(input_dir: Path, output_dir: Path) -> None:
    pdfs = list(input_dir.glob("*.pdf"))
    if not pdfs:
        print(f"PDF 파일이 없습니다: {input_dir}")
        return

    output_dir.mkdir(parents=True, exist_ok=True)
    total = 0

    for pdf_path in pdfs:
        print(f"처리 중: {pdf_path.name}")
        try:
            records = process_pdf(pdf_path)
        except Exception as e:
            print(f"  오류 — {e}")
            continue

        out_path = output_dir / f"{pdf_path.stem}.json"
        out_path.write_text(json.dumps(records, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"  저장: {out_path}  ({len(records)}개 조항)")
        total += len(records)

    print(f"\n완료: {len(pdfs)}개 PDF → {total}개 조항")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="표준계약서 전처리")
    parser.add_argument(
        "--input",
        type=Path,
        default=Path(__file__).resolve().parents[1] / "data" / "standard_contracts",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path(__file__).resolve().parents[1] / "data" / "standard_contracts" / "processed",
    )
    args = parser.parse_args()
    run(args.input, args.output)
