"""
F1 정확도 측정 스크립트.

backend/data/ground_truth.json의 각 조항을 classify_clause()로 분류하고
Precision / Recall / F1을 계산한다.

실행:
    cd backend
    python scripts/measure_f1.py
    python scripts/measure_f1.py --input data/ground_truth.json

출력:
    콘솔: Precision / Recall / F1 / 오분류 케이스 수
    파일: backend/data/misclassified.json
"""

import argparse
import json
import sys
import time
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core.classifier import classify_clause  # noqa: E402

# ── 설정 ─────────────────────────────────────────────────────────────────────

DATA_DIR = Path(__file__).resolve().parents[1] / "data"
DEFAULT_INPUT   = DATA_DIR / "ground_truth.json"
MISCLASSIFIED_PATH = DATA_DIR / "misclassified.json"

POSITIVE_LABEL = "High"
RATE_LIMIT_DELAY = 0.5  # GPT 레이트 리밋 방지 (초)


# ── 분류 ─────────────────────────────────────────────────────────────────────

def classify_sample(sample: dict) -> str:
    """ground_truth 항목 하나를 분류하고 예측 레이블(High / Other) 반환."""
    clause = {
        "clause_index": 0,
        "article_number": None,
        "text": sample["clause_text"],
    }
    result = classify_clause(clause, category=None)
    return result["risk_level"]


# ── 지표 계산 ──────────────────────────────────────────────────────────────────

def compute_metrics(y_true: list[str], y_pred: list[str]) -> dict:
    """
    High를 양성 클래스로 Precision / Recall / F1 계산.

    Precision = TP / (TP + FP)  — 예측 High 중 실제 High 비율
    Recall    = TP / (TP + FN)  — 실제 High 중 예측 High 비율
    F1        = 2 * P * R / (P + R)
    """
    tp = sum(1 for t, p in zip(y_true, y_pred) if t == POSITIVE_LABEL and p == POSITIVE_LABEL)
    fp = sum(1 for t, p in zip(y_true, y_pred) if t != POSITIVE_LABEL and p == POSITIVE_LABEL)
    fn = sum(1 for t, p in zip(y_true, y_pred) if t == POSITIVE_LABEL and p != POSITIVE_LABEL)
    tn = sum(1 for t, p in zip(y_true, y_pred) if t != POSITIVE_LABEL and p != POSITIVE_LABEL)

    precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
    recall    = tp / (tp + fn) if (tp + fn) > 0 else 0.0
    f1        = (
        2 * precision * recall / (precision + recall)
        if (precision + recall) > 0
        else 0.0
    )

    return {
        "precision": precision,
        "recall": recall,
        "f1": f1,
        "tp": tp, "fp": fp, "fn": fn, "tn": tn,
    }


# ── 진입점 ───────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(description="LegaLenz F1 정확도 측정")
    parser.add_argument(
        "--input", type=Path, default=DEFAULT_INPUT,
        help=f"Ground Truth JSON 경로 (기본: {DEFAULT_INPUT})",
    )
    args = parser.parse_args()

    if not args.input.exists():
        print(f"[오류] Ground Truth 파일 없음: {args.input}")
        print("먼저 실행: python scripts/collect_ground_truth.py")
        sys.exit(1)

    samples: list[dict] = json.loads(args.input.read_text(encoding="utf-8"))
    if not samples:
        print("[오류] Ground Truth 파일이 비어 있음")
        sys.exit(1)

    high_count  = sum(1 for s in samples if s["label"] == POSITIVE_LABEL)
    other_count = len(samples) - high_count

    print("=" * 60)
    print(f"총 샘플 수: {len(samples)}")
    print(f"High 샘플: {high_count} / Other 샘플: {other_count}")
    print("=" * 60)
    print()

    y_true: list[str] = []
    y_pred: list[str] = []
    misclassified: list[dict] = []
    errors = 0

    for i, sample in enumerate(samples, 1):
        prefix = f"[{i:>3}/{len(samples)}]"

        try:
            pred = classify_sample(sample)
        except Exception as e:
            print(f"{prefix} [오류] {e}")
            errors += 1
            continue

        true_label = sample["label"]
        y_true.append(true_label)
        y_pred.append(pred)

        correct = pred == true_label
        marker = "✓" if correct else "✗"
        preview = sample["clause_text"][:55].replace("\n", " ")
        print(f"{prefix} {marker}  정답={true_label:<5}  예측={pred:<5}  {preview}...")

        if not correct:
            misclassified.append({
                "clause_text": sample["clause_text"],
                "true_label": true_label,
                "predicted_label": pred,
                "source": sample.get("source", ""),
            })

        if i < len(samples):
            time.sleep(RATE_LIMIT_DELAY)

    if not y_true:
        print("\n[오류] 분류된 샘플 없음")
        sys.exit(1)

    metrics = compute_metrics(y_true, y_pred)

    print()
    print("=" * 60)
    print(f"총 샘플 수: {len(y_true)}")
    print(f"High 샘플: {sum(1 for t in y_true if t == POSITIVE_LABEL)} / "
          f"Other 샘플: {sum(1 for t in y_true if t != POSITIVE_LABEL)}")
    if errors:
        print(f"분류 오류 (건너뜀): {errors}건")
    print()
    print(f"Precision: {metrics['precision']:.2f}")
    print(f"Recall:    {metrics['recall']:.2f}")
    print(f"F1 Score:  {metrics['f1']:.2f}")
    print()
    print(f"(TP={metrics['tp']}, FP={metrics['fp']}, FN={metrics['fn']}, TN={metrics['tn']})")
    print()

    if misclassified:
        MISCLASSIFIED_PATH.write_text(
            json.dumps(misclassified, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        print(f"오분류 케이스: {len(misclassified)}건 → {MISCLASSIFIED_PATH} 저장")
    else:
        print("오분류 케이스: 0건")

    print("=" * 60)


if __name__ == "__main__":
    main()
