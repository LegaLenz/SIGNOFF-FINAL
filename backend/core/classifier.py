"""
조항 리스크 분류 + 계약서 카테고리 분류 모듈 (LangChain + GPT-4o).
"""

import time
from typing import Literal, TypedDict

from dotenv import load_dotenv
from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI
from pydantic import BaseModel, Field

load_dotenv(override=True)

_MODEL = "gpt-4o"
_RATE_LIMIT_DELAY = 0.5  # 레이트 리밋 방지 딜레이 (초)

RiskLevel = Literal["High", "Mid", "Low"]


class ClassifiedClause(TypedDict):
    clause_index: int          # 원본 순서 복원용 (RAG 검색 결과는 유사도 순)
    article_number: str | None # "제5조" 형태, 없으면 None
    text: str                  # 조항 원문
    risk_level: RiskLevel      # High / Mid / Low
    reason: str                # 분류 근거 설명 (한국어)
    highlight: bool            # risk_level == "High"일 때만 True (UI 빨간 하이라이트)


# ── LLM 구조화 출력 스키마 ────────────────────────────────────────────────────

class _ClassificationOutput(BaseModel):
    risk_level: Literal["High", "Mid", "Low"] = Field(
        description="조항 리스크 등급: High(고위험) / Mid(중위험) / Low(저위험)"
    )
    reason: str = Field(
        description="리스크 등급 판단 근거. 한국어로, 왜 해당 등급인지 구체적으로 서술."
    )


class _CategoryOutput(BaseModel):
    category: str = Field(
        description="계약서 종류. 예: 프리랜서 용역계약서, 표준 근로계약서, 소프트웨어 개발 계약서, 부동산 임대차계약서 등"
    )


# ── 프롬프트 ─────────────────────────────────────────────────────────────────

_CLAUSE_PROMPT = ChatPromptTemplate.from_messages([
    ("system", """당신은 한국 계약서 리스크 분석 전문가입니다.
계약서 조항을 읽고 아래 기준에 따라 리스크 등급을 분류하세요.

[High — 을에게 일방적으로 불리한 조항]
· 과도한 손해배상 또는 위약금
· 갑의 일방적 계약 변경·해지권
· 을의 이의제기·해지권 박탈
· 책임 면제 또는 무한 책임

[Mid — 표현이 모호하거나 해석 여지가 있는 조항]
· "합리적인 기간 내에", "갑의 판단에 따라" 등 불명확한 표현
· 분쟁 시 해석이 엇갈릴 수 있는 조항

[Low — 표준적이고 일반적인 조항]
· 계약 목적 및 정의 조항
· 표준 지급 조건
· 일반적인 권리·의무 조항

{rag_context}"""),
    ("human", """다음 계약서 조항을 분류해주세요.

조항 번호: {article_number}
조항 내용:
{text}"""),
])

_CATEGORY_PROMPT = ChatPromptTemplate.from_messages([
    ("system", """당신은 한국 계약서 분류 전문가입니다.
계약서 전문을 읽고 계약서 종류를 한국어로 짧게 답하세요.
예: 프리랜서 용역계약서, 표준 근로계약서, 소프트웨어 개발 계약서, 부동산 임대차계약서"""),
    ("human", """다음 계약서의 종류를 분류해주세요.

{text}"""),
])


# ── Chain (모듈 최초 사용 시 1회 초기화) ─────────────────────────────────────

_clause_chain = None
_category_chain = None


def _get_clause_chain():
    global _clause_chain
    if _clause_chain is None:
        llm = ChatOpenAI(model=_MODEL, temperature=0)
        _clause_chain = _CLAUSE_PROMPT | llm.with_structured_output(_ClassificationOutput)
    return _clause_chain


def _get_category_chain():
    global _category_chain
    if _category_chain is None:
        llm = ChatOpenAI(model=_MODEL, temperature=0)
        _category_chain = _CATEGORY_PROMPT | llm.with_structured_output(_CategoryOutput)
    return _category_chain


# ── 공개 API ─────────────────────────────────────────────────────────────────

def classify_document_category(text: str) -> str:
    """
    계약서 전문을 읽고 계약서 종류를 반환한다.

    Args:
        text: 계약서 전체 텍스트 (extractor.extract_text() 반환값).

    Returns:
        계약서 종류 문자열. 예: "프리랜서 용역계약서"
    """
    result: _CategoryOutput = _get_category_chain().invoke({"text": text[:3000]})
    return result.category


def classify_clause(clause: dict) -> ClassifiedClause:
    """
    단일 조항을 High / Mid / Low 로 분류한다.

    Args:
        clause: parser.parse_clauses()가 반환한 단일 항목.
                {"clause_index": int, "article_number": str | None, "text": str}

    Returns:
        ClassifiedClause — 입력 필드에 risk_level, reason, highlight 추가.
    """
    # TODO (3주차): rag.search(clause["text"], category=...) 로 유사 FTC 표준계약서 조항 검색 후
    #   검색 결과 텍스트를 rag_context에 주입해 분류 프롬프트 근거로 활용.
    #   여기서는 검색(search)만 — 대안 문구 생성(answer_query)은 /clauses/alternative 에서 호출.
    #   현재는 rag.py 미구현으로 GPT-4o 자체 판단으로만 동작.
    rag_context = ""

    result: _ClassificationOutput = _get_clause_chain().invoke({
        "article_number": clause.get("article_number") or "없음",
        "text": clause["text"],
        "rag_context": rag_context,
    })

    return ClassifiedClause(
        clause_index=clause["clause_index"],
        article_number=clause.get("article_number"),
        text=clause["text"],
        risk_level=result.risk_level,
        reason=result.reason,
        highlight=result.risk_level == "High",
    )


def classify_clauses(clauses: list[dict]) -> list[ClassifiedClause]:
    """
    조항 리스트 전체를 순차 분류한다.

    API 레이트 리밋 방지를 위해 각 호출 사이 0.5초 딜레이.
    순서는 clause_index 기준 오름차순 유지.

    Args:
        clauses: parser.parse_clauses()의 반환값.

    Returns:
        ClassifiedClause 리스트.
    """
    results: list[ClassifiedClause] = []
    for i, clause in enumerate(clauses):
        results.append(classify_clause(clause))
        if i < len(clauses) - 1:
            time.sleep(_RATE_LIMIT_DELAY)
    return results
