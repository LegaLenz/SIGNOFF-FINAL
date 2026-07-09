"""
전체 파이프라인 E2E 테스트 스크립트.

실행 전 uvicorn을 먼저 띄워야 합니다:
    cd backend && uvicorn main:app --reload

사용법:
    python scripts/test_e2e.py
    python scripts/test_e2e.py --pdf data/standard_contracts/example1.pdf
    python scripts/test_e2e.py --pdf data/standard_contracts/example1.pdf --base-url http://localhost:8000
"""

import argparse
import sys
from pathlib import Path

import requests

BASE_URL = "http://localhost:8000"
DEFAULT_PDF = Path(__file__).resolve().parents[1] / "data" / "standard_contracts" / "example1.pdf"


# ── 단계별 테스트 ─────────────────────────────────────────────────────────────

def test_health(base_url: str) -> None:
    print("=" * 60)
    print("[0] GET /health")
    print("=" * 60)
    resp = requests.get(f"{base_url}/health")
    if resp.status_code != 200:
        print(f"  실패: {resp.status_code} {resp.text}")
        sys.exit(1)
    print(f"  응답: {resp.json()}")
    print()


def test_analyze(pdf_path: Path, base_url: str) -> dict:
    print("=" * 60)
    print("[1] POST /analyze")
    print("=" * 60)
    with pdf_path.open("rb") as f:
        resp = requests.post(
            f"{base_url}/analyze",
            files={"file": (pdf_path.name, f, "application/pdf")},
        )
    if resp.status_code != 200:
        print(f"  실패: {resp.status_code} {resp.text}")
        sys.exit(1)

    data = resp.json()
    print(f"  파일명       : {data['filename']}")
    print(f"  계약서 종류  : {data['document_category']}")
    print(f"  조항 수      : {data['clause_count']}")
    print(f"  예상 소요시간: {data['estimated_seconds']}초")
    print()

    for c in data["clauses"]:
        marker = "[High]" if c["highlight"] else f"[{c['risk_level']}] "
        article = c.get("article_number") or "전문"
        print(f"  {marker} {article}: {c['text'][:60].replace(chr(10), ' ')}...")

    return data


def test_alternative(clause: dict, document_category: str, base_url: str) -> None:
    print()
    print("=" * 60)
    print("[2] POST /clauses/alternative")
    print("=" * 60)
    article = clause.get("article_number") or f"index={clause['clause_index']}"
    print(f"  대상 조항  : {article}")
    print(f"  위험도     : {clause['risk_level']}")
    print(f"  판단 근거  : {clause['reason']}")
    print()

    payload = {
        "clause_index": clause["clause_index"],
        "article_number": clause.get("article_number"),
        "text": clause["text"],
        "document_category": document_category,
        "risk_level": clause["risk_level"],
        "reason": clause["reason"],
    }
    resp = requests.post(f"{base_url}/clauses/alternative", json=payload)
    if resp.status_code != 200:
        print(f"  실패: {resp.status_code} {resp.text}")
        return

    result = resp.json()
    alternative = result["alternative"] or "(대안 없음 — 표준계약서 근거 불충분)"
    print(f"  대안 문구:\n{_indent(alternative)}")
    print(f"  출처 URL : {result['source_url'] or '없음'}")


# ── 유틸 ─────────────────────────────────────────────────────────────────────

def _indent(text: str, prefix: str = "    ") -> str:
    return "\n".join(prefix + line for line in text.splitlines())


# ── 진입점 ───────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(description="LegaLenz 백엔드 E2E 테스트")
    parser.add_argument("--pdf", type=Path, default=DEFAULT_PDF)
    parser.add_argument("--base-url", default=BASE_URL)
    args = parser.parse_args()

    if not args.pdf.exists():
        print(f"오류: PDF 파일이 없습니다 — {args.pdf}")
        sys.exit(1)

    test_health(args.base_url)
    result = test_analyze(args.pdf, args.base_url)

    high_clauses = [c for c in result["clauses"] if c["highlight"]]
    if not high_clauses:
        print("\n  High 리스크 조항 없음 — /clauses/alternative 테스트 생략")
        return

    test_alternative(high_clauses[0], result["document_category"], args.base_url)


if __name__ == "__main__":
    main()
