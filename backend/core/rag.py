"""
RAG 파이프라인 모듈 (Pinecone 검색 + GPT-4o 대안 문구 생성).

2주차 구현 예정. 현재는 출력 포맷 및 함수 시그니처만 정의.

커버리지 부족 케이스:
    Pinecone 유사도 score가 SIMILARITY_THRESHOLD 미만이면
    대안 문구 생성 없이 경고 메시지를 반환한다.
"""

from typing import TypedDict

# 유사도 임계값 — 이 값 미만이면 표준계약서 커버리지 부족으로 판단
SIMILARITY_THRESHOLD = 0.75

_COVERAGE_WARNING = "공정거래위원회 표준계약서가 커버하지 못하는 범위의 계약입니다."


class RagResult(TypedDict):
    clause_index: int          # 원본 순서 복원용
    article_number: str | None # "제5조" 형태, 없으면 None
    alternative: str | None    # 대안 문구. 커버리지 부족 시 None
    warning: str | None        # 커버리지 부족 경고. 정상 생성 시 None


def generate_alternative(classified_clause: dict) -> RagResult:
    """
    단일 조항에 대해 Pinecone 검색 후 GPT-4o로 대안 문구를 생성한다.

    유사도 score가 SIMILARITY_THRESHOLD 미만이면 대안 문구 없이 warning을 반환한다.
    alternative와 warning은 항상 한쪽만 값을 가진다.

    Args:
        classified_clause: classifier.classify_clause()의 반환값.
            {"clause_index", "article_number", "text", "risk_level", "reason", "highlight"}

    Returns:
        커버리지 충분:  {"alternative": "...", "warning": None, ...}
        커버리지 부족:  {"alternative": None, "warning": "공정거래위원회 ...", ...}

    TODO (2주차):
        - Pinecone 유사도 검색: 상위 k개 결과 + score 반환
        - max(scores) < SIMILARITY_THRESHOLD → alternative=None, warning=_COVERAGE_WARNING 반환
        - max(scores) >= SIMILARITY_THRESHOLD → 검색 결과를 컨텍스트로 GPT-4o 호출
        - source_url을 응답 메타데이터에 포함
        - 응답 파싱 → alternative 문자열 추출
    """
    raise NotImplementedError("2주차 구현 예정")


def generate_alternatives(classified_clauses: list[dict]) -> list[RagResult]:
    """
    분류된 조항 리스트 전체에 대해 대안 문구를 일괄 생성한다.

    High 리스크 조항에 대해서만 RAG를 실행하고,
    Mid / Low 조항은 alternative=None, warning=None 으로 패스스루한다.

    Args:
        classified_clauses: classifier.classify_clauses()의 반환값.

    Returns:
        RagResult 리스트. 순서는 clause_index 기준 오름차순 유지.

    TODO (2주차):
        - risk_level == "High" 인 조항만 generate_alternative() 호출
        - Mid / Low는 {"alternative": None, "warning": None} 패스스루
        - API 레이트 리밋 대응 (asyncio.gather + semaphore)
        - 동일 문서에서 여러 조항 검색 시 dedup 처리
    """
    raise NotImplementedError("2주차 구현 예정")
