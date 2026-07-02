"""
조항 분리 공통 유틸리티.

parser.py (실시간 계약서)와 index_contracts.py (표준계약서 인덱싱) 양쪽에서
동일한 분리 단위(조 단위)를 유지하기 위해 공통 모듈로 분리.

공개 API:
    ARTICLE_RE          — "제N조" 정규식
    NUMBERED_RE         — "N." 정규식
    clean_text()        — 원시 텍스트 전처리
    extract_article_number() — "제N조" 추출 → str | None
    split_by_pattern()  — 정규식 경계 기반 분리
    split_by_unstructured() — Unstructured Title 기반 분리
"""

import re

# ── 조항 경계 패턴 ──────────────────────────────────────────────────────────

# "제N조" / "제N조의N" (줄 시작)
ARTICLE_RE = re.compile(r"(?m)^(제\s*\d+\s*조(?:의\s*\d+)?)")

# "N." (1~99, 줄 시작, 점 뒤 공백 필수)
NUMBERED_RE = re.compile(r"(?m)^(\d{1,2}\.)\s")


# ── 헬퍼 ────────────────────────────────────────────────────────────────────

def clean_text(raw: str) -> str:
    """원시 텍스트 전처리: 폼피드·연속 공백·과도한 빈 줄 제거."""
    text = re.sub(r"\f", "\n", raw)
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def extract_article_number(text: str) -> str | None:
    """
    조항 텍스트 앞부분에서 "제N조" 표기를 추출한다.

    Args:
        text: 단일 조항 문자열.

    Returns:
        "제5조" 형태의 정규화된 문자열, 없으면 None.
    """
    m = ARTICLE_RE.match(text.lstrip())
    if not m:
        return None
    # "제 3 조의 2" → "제3조의2" 로 공백 제거
    return re.sub(r"\s+", "", m.group(0))


# ── 분리 함수 ────────────────────────────────────────────────────────────────

def split_by_pattern(text: str, pattern: re.Pattern) -> list[dict]:
    """
    정규식 패턴 매치 위치를 경계로 삼아 텍스트를 조항 단위로 분리한다.

    Returns:
        [{"clause_index": int, "article_number": str | None, "text": str}, ...]
    """
    positions = [m.start() for m in pattern.finditer(text)]
    if not positions:
        return []

    clauses: list[dict] = []

    # 첫 경계 이전 전문(前文)
    if positions[0] > 0:
        preamble = text[: positions[0]].strip()
        if preamble:
            clauses.append({
                "clause_index": 0,
                "article_number": None,
                "text": preamble,
            })

    for i, start in enumerate(positions):
        end = positions[i + 1] if i + 1 < len(positions) else len(text)
        chunk = text[start:end].strip()
        if chunk:
            clauses.append({
                "clause_index": len(clauses),
                "article_number": extract_article_number(chunk),
                "text": chunk,
            })

    return clauses


def split_by_unstructured(text: str) -> list[dict]:
    """
    Unstructured partition_text로 엘리먼트를 얻은 뒤,
    Title 타입 엘리먼트 중 조항 패턴과 일치하는 것을 경계로 그룹핑한다.

    Returns:
        [{"clause_index": int, "article_number": str | None, "text": str}, ...]
    """
    from unstructured.partition.text import partition_text

    elements = partition_text(text=text)
    clauses: list[dict] = []
    current: list[str] = []

    for el in elements:
        el_text = str(el).strip()
        if not el_text:
            continue

        is_boundary = type(el).__name__ == "Title" and (
            ARTICLE_RE.match(el_text) or NUMBERED_RE.match(el_text)
        )

        if is_boundary and current:
            chunk = "\n".join(current)
            clauses.append({
                "clause_index": len(clauses),
                "article_number": extract_article_number(chunk),
                "text": chunk,
            })
            current = [el_text]
        else:
            current.append(el_text)

    if current:
        chunk = "\n".join(current)
        clauses.append({
            "clause_index": len(clauses),
            "article_number": extract_article_number(chunk),
            "text": chunk,
        })

    return clauses
