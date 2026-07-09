"""
조항 단위 파싱 모듈 (실시간 사용자 계약서용).

텍스트 추출 → 조항 분리 순으로 처리.
분리 로직(캐스케이드 포함)은 clause_utils.split_clauses()로 공유.

결과 포맷:
  [{"clause_index": int, "article_number": str | None, "text": str}, ...]
"""

from core.clause_utils import clean_text, split_clauses


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
    return split_clauses(clean_text(text))
