"""
조항 단위 파싱 모듈 (실시간 사용자 계약서용).

텍스트 추출 → 조항 분리 → article_number 부여 순으로 처리.
<<<<<<< HEAD
분리 로직은 clause_utils에서 공유.

전략:
  1. "제N조" 패턴 (한국 계약서 최우선)
  2. "N." 번호 패턴
  3. Unstructured partition_text
  4. 최후 수단: 전체를 단일 조항으로
=======
분리 로직(캐스케이드 포함)은 clause_utils.split_clauses()로 공유.
>>>>>>> origin/dev

결과 포맷:
  [{"clause_index": int, "article_number": str | None, "text": str}, ...]
"""

<<<<<<< HEAD
from core.clause_utils import (
    ARTICLE_RE,
    NUMBERED_RE,
    clean_text,
    split_by_pattern,
    split_by_unstructured,
)
=======
from core.clause_utils import clean_text, split_clauses
>>>>>>> origin/dev


def parse_clauses(text: str) -> list[dict]:
    """
    계약서 텍스트를 조항 단위 딕셔너리 리스트로 분리한다.

    Args:
        text: extractor.extract_text()가 반환한 원시 문자열.

    Returns:
        [{"clause_index": int, "article_number": str | None, "text": str}, ...]
        - article_number: "제5조" 형태, 인식 실패 시 None
        - clause_index: 0-based 순번 (RAG 검색 결과의 원본 순서 복원용)
    """
    cleaned = clean_text(text)
<<<<<<< HEAD

    # 1순위: 제N조
    result = split_by_pattern(cleaned, ARTICLE_RE)
    if len(result) >= 2:
        return result

    # 2순위: 번호(N.)
    result = split_by_pattern(cleaned, NUMBERED_RE)
    if len(result) >= 2:
        return result

    # 3순위: Unstructured
    try:
        result = split_by_unstructured(cleaned)
        if result:
            return result
    except Exception:
        pass

    # 최후 수단: 전체를 단일 조항으로
    return [{"clause_index": 0, "article_number": None, "text": cleaned}]
=======
    return split_clauses(cleaned)
>>>>>>> origin/dev
