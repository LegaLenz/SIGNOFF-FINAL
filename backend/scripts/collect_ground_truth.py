"""
Ground Truth 데이터 수집 스크립트.

양성 샘플(High): 공정위 의결서·재결서에서 불공정약관으로 시정명령된 조항
음성 샘플(Other): backend/data/standard_contracts/ 내 표준계약서 정상 조항

실행:
    cd backend
    python scripts/collect_ground_truth.py                  # 양성 25 + 음성 25
    python scripts/collect_ground_truth.py --max-high 30 --max-other 30
    python scripts/collect_ground_truth.py --other-only     # FTC 사이트 없이 음성만

출력: backend/data/ground_truth.json
형식: [{"clause_text": str, "label": "High"|"Other", "source": str}, ...]

High 샘플 조정 포인트:
    - DECISIONS_DIR: collect_decisions.py 로 수집한 PDF 경로
    - parse_clauses(): 조항 분리 정규식
"""

import argparse
import json
import re
import sys
from pathlib import Path

from pdfminer.high_level import extract_text as pdfminer_extract

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core.parser import parse_clauses

# ── 설정 ─────────────────────────────────────────────────────────────────────

DATA_DIR               = Path(__file__).resolve().parents[1] / "data"
OUTPUT_PATH            = DATA_DIR / "ground_truth.json"
DECISIONS_DIR          = DATA_DIR / "decisions"
STANDARD_CONTRACTS_DIR = DATA_DIR / "standard_contracts"


# ── 유틸 ─────────────────────────────────────────────────────────────────────

def _is_garbled(text: str) -> bool:
    """한글 문자 비율이 10% 미만이면 인코딩 깨짐으로 판단."""
    non_space = [c for c in text if not c.isspace()]
    if not non_space:
        return True
    korean = sum(1 for c in non_space if "가" <= c <= "힣")
    return korean / len(non_space) < 0.10


# 약관규제법 조문 등 실제 불공정 조항이 아닌 텍스트 제외 패턴
_EXCLUDE_PATTERNS = [
    "제6조(일반원칙)",
    "제7조(면책조항의 금지)",
    "제17조(불공정약관조항의 사용금지)",
    "시정권고를 받은 날로부터",
    "시정조치에 따라",
]


# ── 양성 샘플 수집 (로컬 PDF) ────────────────────────────────────────────────

def collect_high_samples(max_count: int) -> list[dict]:
    """data/decisions/ 의 PDF에서 High(불공정) 샘플 수집."""
    print(f"\n[1] 양성 샘플 수집 (목표: {max_count}개)")
    print(f"    경로: {DECISIONS_DIR}")

    pdf_files = sorted(DECISIONS_DIR.glob("*.pdf"))
    if not pdf_files:
        print(f"  [오류] PDF 없음: {DECISIONS_DIR}")
        print("  먼저 실행: python scripts/collect_decisions.py")
        return []

    print(f"  PDF {len(pdf_files)}개 발견")
    samples: list[dict] = []

    for pdf_path in pdf_files:
        if len(samples) >= max_count:
            break

        print(f"  {pdf_path.name} ...", end=" ")

        try:
            text = pdfminer_extract(str(pdf_path))
        except Exception as e:
            print(f"텍스트 추출 실패: {e}")
            continue

        if not text or len(text.strip()) < 100:
            print("텍스트 없음 — 건너뜀")
            continue

        if _is_garbled(text):
            print("[경고] 인코딩 깨짐 — 건너뜀")
            continue

        clauses = parse_clauses(text)
        added = 0
        for clause in clauses:
            if len(samples) >= max_count:
                break
            clause_text = clause["text"].strip()
            if len(clause_text) < 15:
                continue
            if any(pat in clause_text for pat in _EXCLUDE_PATTERNS):
                continue
            samples.append({
                "clause_text": clause_text,
                "label":       "High",
                "source":      pdf_path.name,
            })
            added += 1

        print(f"{added}개 추출 (누계: {len(samples)}개)")

    print(f"\n  High 샘플 수집 완료: {len(samples)}개")
    if len(samples) < max_count:
        print(f"  ⚠ 목표({max_count}개)에 미달 — decisions/ 폴더에 PDF를 추가하세요")

    return samples


# ── 음성 샘플 수집 (표준계약서) ────────────────────────────────────────────────

def collect_other_samples(max_count: int) -> list[dict]:
    """표준계약서 TXT에서 Other(정상) 샘플 수집."""
    print(f"\n[2] 음성 샘플 수집 (목표: {max_count}개)")
    print(f"    경로: {STANDARD_CONTRACTS_DIR}")

    samples: list[dict] = []
    txt_files = list(STANDARD_CONTRACTS_DIR.rglob("*.txt"))

    if not txt_files:
        print(f"  [오류] TXT 없음: {STANDARD_CONTRACTS_DIR}")
        return []

    print(f"  TXT {len(txt_files)}개 발견")

    for txt_path in txt_files:
        if len(samples) >= max_count:
            break

        print(f"  {txt_path.name} ...", end=" ")

        try:
            raw_text = txt_path.read_text(encoding="utf-8")
            clauses = parse_clauses(raw_text)
        except Exception as e:
            print(f"파싱 실패: {e}")
            continue

        added = 0
        for clause in clauses:
            if len(samples) >= max_count:
                break
            text = clause["text"].strip()
            if len(text) < 15:
                continue
            samples.append({
                "clause_text": text,
                "label": "Other",
                "source": txt_path.name,
            })
            added += 1

        print(f"{added}개 추출 (누계: {len(samples)}개)")

    print(f"\n  Other 샘플 수집 완료: {len(samples)}개")
    return samples


# ── 진입점 ───────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(description="Ground Truth 데이터 수집")
    parser.add_argument("--max-high", type=int, default=25, help="High 샘플 최대 수 (기본: 25)")
    parser.add_argument("--max-other", type=int, default=25, help="Other 샘플 최대 수 (기본: 25)")
    parser.add_argument("--other-only", action="store_true", help="Other 샘플만 수집 (FTC 사이트 접근 없이)")
    args = parser.parse_args()

    DATA_DIR.mkdir(parents=True, exist_ok=True)

    all_samples: list[dict] = []

    if not args.other_only:
        all_samples.extend(collect_high_samples(args.max_high))

    all_samples.extend(collect_other_samples(args.max_other))

    if not all_samples:
        print("\n[오류] 수집된 샘플 없음")
        sys.exit(1)

    OUTPUT_PATH.write_text(
        json.dumps(all_samples, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    high_count  = sum(1 for s in all_samples if s["label"] == "High")
    other_count = len(all_samples) - high_count

    print(f"\n{'='*60}")
    print(f"수집 완료: 총 {len(all_samples)}개")
    print(f"  High  : {high_count}개")
    print(f"  Other : {other_count}개")
    print(f"저장 위치: {OUTPUT_PATH}")
    print("="*60)


if __name__ == "__main__":
    main()
