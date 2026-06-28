"""
조항 단위 파싱 모듈.

Unstructured로 추출된 원시 텍스트를 받아
'제1조', '① ...', '(1) ...' 같은 조항 경계를 감지하고
구조화된 딕셔너리 리스트로 반환한다.
"""

import re
from typing import NamedTuple


class Clause(NamedTuple):
    index: int
    title: str   # 예: "제3조"  — 없으면 빈 문자열
    text: str


# 조항 시작 패턴: 제N조, ①②③, (1)(2)(3)
_CLAUSE_PATTERN = re.compile(
    r"(?:^|\n)"                          # 줄 시작
    r"(?:제\s*\d+\s*조|[①-⑳]|\(\d+\))"  # 조항 번호
    r"[\s\S]*?(?=(?:제\s*\d+\s*조|[①-⑳]|\(\d+\))|\Z)",
    re.MULTILINE,
)


def clean_text(raw: str) -> str:
    """
    텍스트 전처리: 불필요한 공백·헤더·페이지 번호 제거.

    Args:
        raw: PDFMiner 또는 EasyOCR에서 추출한 원시 문자열.

    Returns:
        정규화된 문자열.
    """
    text = re.sub(r"\f", "\n", raw)            # 폼피드 → 줄바꿈
    text = re.sub(r"[ \t]+", " ", text)        # 연속 공백 정리
    text = re.sub(r"\n{3,}", "\n\n", text)     # 과도한 빈 줄 제거
    return text.strip()


def detect_clause_boundaries(text: str) -> list[tuple[int, int]]:
    """
    조항 경계(시작·끝 인덱스) 목록을 반환한다.

    Args:
        text: clean_text()를 거친 계약서 문자열.

    Returns:
        (start, end) 튜플 리스트. end는 다음 조항 시작 직전.
    """
    boundaries: list[tuple[int, int]] = []
    for m in _CLAUSE_PATTERN.finditer(text):
        boundaries.append((m.start(), m.end()))
    return boundaries


def parse_clauses(text: str) -> list[Clause]:
    """
    계약서 전문(全文)을 조항 단위 Clause 리스트로 분리한다.

    Args:
        text: 추출된 계약서 원시 텍스트 (clean_text 미적용이어도 됨).

    Returns:
        Clause(index, title, text) 리스트.
        index는 0-based.

    Example:
        clauses = parse_clauses(raw_text)
        for c in clauses:
            print(c.index, c.title, c.text[:80])
    """
    cleaned = clean_text(text)
    boundaries = detect_clause_boundaries(cleaned)

    if not boundaries:
        # 조항 경계를 찾지 못하면 전체를 단일 조항으로 반환
        return [Clause(index=0, title="", text=cleaned)]

    clauses: list[Clause] = []
    for i, (start, end) in enumerate(boundaries):
        chunk = cleaned[start:end].strip()
        title_match = re.match(r"(제\s*\d+\s*조|[①-⑳]|\(\d+\))", chunk)
        title = title_match.group(0) if title_match else ""
        clauses.append(Clause(index=i, title=title, text=chunk))

    return clauses
