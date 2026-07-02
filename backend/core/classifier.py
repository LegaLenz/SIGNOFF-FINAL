"""
조항 리스크 분류 모듈 (LangChain Agent + GPT-4o-mini).

2주차 구현 예정. 현재는 출력 포맷 및 함수 시그니처만 정의.
"""

from typing import Literal, TypedDict


RiskLevel = Literal["High", "Mid", "Low"]


class ClassifiedClause(TypedDict):
    clause_index: int          # 원본 순서 복원용 (RAG 검색 결과는 유사도 순)
    article_number: str | None # "제5조" 형태, 없으면 None
    text: str                  # 조항 원문
    risk_level: RiskLevel      # High / Mid / Low
    reason: str                # 분류 근거 설명


def classify_clause(clause: dict) -> ClassifiedClause:
    """
    단일 조항을 High / Mid / Low 로 분류한다.

    Args:
        clause: parser.parse_clauses()가 반환한 단일 항목.
                {"clause_index": int, "article_number": str | None, "text": str}

    Returns:
        ClassifiedClause — 입력 필드에 risk_level, reason 추가.

    TODO (2주차):
        - LangChain ChatOpenAI(model="gpt-4o-mini") 초기화
        - 분류 프롬프트 설계 (High/Mid/Low 기준 명시)
        - LLMChain 또는 RunnableSequence로 호출
        - 응답 파싱 → risk_level, reason 추출
    """
    raise NotImplementedError("2주차 구현 예정")


def classify_clauses(clauses: list[dict]) -> list[ClassifiedClause]:
    """
    조항 리스트 전체를 일괄 분류한다.

    Args:
        clauses: parser.parse_clauses()의 반환값.

    Returns:
        ClassifiedClause 리스트. 순서는 clause_index 기준 오름차순 유지.

    TODO (2주차):
        - classify_clause()를 순차 또는 비동기 병렬 호출
        - API 레이트 리밋 대응 (tenacity 재시도 또는 asyncio.gather + semaphore)
        - 분류 실패 조항 처리 방침 결정 (스킵 vs 에러 전파)
    """
    raise NotImplementedError("2주차 구현 예정")
