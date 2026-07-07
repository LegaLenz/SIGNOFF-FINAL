"""
rag.py 실행 테스트 스크립트.

classifier.py / routes.py 없이 rag.py 함수들을 직접 호출해서 실제 OpenAI/Pinecone
API가 제대로 붙는지 확인한다. 실제 API를 호출하므로 소액 비용이 발생한다.

2단계(제목 유사도 기반 후보 추리기)는 실측 결과 카테고리 필터만 썼을 때보다
결과가 나빠지는 것으로 확인되어 rag.py에서 제거됨 — 이 테스트도 그에 맞춰
category 필터만 검증한다.

실행:
    cd backend
    python scripts/test_rag.py
"""

import os
import sys
import traceback

from dotenv import load_dotenv

load_dotenv()

sys.path.append(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

from core.rag import (  # noqa: E402
    classify_document_category,
    search,
    retrieve_evidence,
    answer_query,
    RAGServiceError,
)

# ── 테스트용 더미 데이터 ──────────────────────────────────────────────────
# 화학업종 특화 조항으로 구성.

DUMMY_DOCUMENT_TEXT = """
화학업종 표준하도급 기본계약서

원사업자와 수급사업자는 다음과 같이 하도급 기본계약을 체결한다.

제1조(목적)
이 계약은 원사업자가 수급사업자에게 화학제품의 제조를 위탁함에 있어 필요한 사항을 정함을 목적으로 한다.

제12조(유해화학물질 취급)
을은 유해화학물질의 보관, 운반 및 취급과 관련하여 관계 법령이 정하는 안전기준을
준수하여야 하며, 이를 위반하여 발생하는 안전사고 및 환경오염에 대하여 그 종류와
범위를 불문하고 무제한으로 책임을 진다.
"""

DUMMY_CLAUSE_TEXT = (
    "을은 유해화학물질의 보관, 운반 및 취급과 관련하여 관계 법령이 정하는 안전기준을 "
    "준수하여야 하며, 이를 위반하여 발생하는 안전사고 및 환경오염에 대하여 그 종류와 "
    "범위를 불문하고 무제한으로 책임을 진다."
)

DUMMY_CONTEXT = {
    "article_number": "제12조",
    "risk_level": "High",
    "reason": "유해화학물질 관련 안전사고·환경오염 책임 범위와 금액에 제한이 없어 수급사업자에게 과도한 책임을 지운다.",
}

DUMMY_CHAT_QUESTION = "유해화학물질 취급 조항에 책임 범위를 제한하는 게 일반적인가요?"


def run(label, fn):
    """테스트 하나를 실행하고 결과/에러를 출력. 실패해도 다음 테스트는 계속 진행."""
    print(f"\n{'=' * 60}")
    print(f"[TEST] {label}")
    print("=" * 60)
    try:
        result = fn()
        print(f"결과: {result}")
        return True
    except RAGServiceError as e:
        print(f"❌ RAGServiceError: {e}")
    except Exception as e:
        print(f"❌ 예상치 못한 예외: {type(e).__name__}: {e}")
        traceback.print_exc()
    return False


def main():
    results = {}
    category_holder = {}

    def _classify():
        category = classify_document_category(DUMMY_DOCUMENT_TEXT)
        category_holder["value"] = category
        return category

    results["1단계: classify_document_category"] = run(
        "1단계 — classify_document_category()",
        _classify,
    )

    results["검색: search"] = run(
        "search() (1단계 category 적용)",
        lambda: search(DUMMY_CLAUSE_TEXT, category=category_holder.get("value")),
    )

    results["retrieve_evidence"] = run(
        "retrieve_evidence() — 검색+dedup+임계값, 생성 없음",
        lambda: retrieve_evidence(DUMMY_CLAUSE_TEXT, category=category_holder.get("value")),
    )

    results["answer_query (mode=alternative)"] = run(
        "answer_query() — 하이라이트 클릭 시나리오",
        lambda: answer_query(
            DUMMY_CLAUSE_TEXT,
            mode="alternative",
            category=category_holder.get("value"),
            context=DUMMY_CONTEXT,
        ),
    )

    results["answer_query (mode=chat)"] = run(
        "answer_query() — 자유 텍스트 채팅 시나리오",
        lambda: answer_query(
            DUMMY_CHAT_QUESTION, mode="chat", category=category_holder.get("value")
        ),
    )

    print(f"\n{'=' * 60}")
    print("=== 요약 ===")
    for label, ok in results.items():
        print(f"  {'✅' if ok else '❌'} {label}")
    print("=" * 60)


if __name__ == "__main__":
    main()
