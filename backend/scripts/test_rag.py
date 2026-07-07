"""
rag.py 실행 테스트 스크립트 — 6개 카테고리 전체 sanity check.

classifier.py / routes.py 없이 rag.py 함수들을 직접 호출해서 실제 OpenAI/Pinecone
API가 제대로 붙는지, 그리고 각 카테고리에서 검색이 명백히 오작동하지 않는지 확인한다.
실제 API를 호출하므로 소액 비용이 발생한다.

주의: Ground Truth(사람이 라벨링한 정답)가 없는 상태라 이건 4주차 정식 F1 측정이
아니라, "명백한 오작동이 있는가"만 보는 정성적 sanity check다.

실행:
    cd backend
    python scripts/test_rag.py            # 전체 카테고리
    python scripts/test_rag.py subcontract # 카테고리 하나만
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

# ── 카테고리별 테스트 케이스 ──────────────────────────────────────────────
# subcontract(화학업종)는 2단계 제거 버그 수정을 검증했던 회귀 테스트 케이스라
# 그대로 유지. 나머지 5개는 카테고리 성격에 맞춰 새로 작성.

TEST_CASES = {
    "subcontract": {
        "document_text": """
화학업종 표준하도급 기본계약서

원사업자와 수급사업자는 다음과 같이 하도급 기본계약을 체결한다.

제1조(목적)
이 계약은 원사업자가 수급사업자에게 화학제품의 제조를 위탁함에 있어 필요한 사항을 정함을 목적으로 한다.

제12조(유해화학물질 취급)
을은 유해화학물질의 보관, 운반 및 취급과 관련하여 관계 법령이 정하는 안전기준을
준수하여야 하며, 이를 위반하여 발생하는 안전사고 및 환경오염에 대하여 그 종류와
범위를 불문하고 무제한으로 책임을 진다.
""",
        "clause_text": (
            "을은 유해화학물질의 보관, 운반 및 취급과 관련하여 관계 법령이 정하는 안전기준을 "
            "준수하여야 하며, 이를 위반하여 발생하는 안전사고 및 환경오염에 대하여 그 종류와 "
            "범위를 불문하고 무제한으로 책임을 진다."
        ),
        "context": {
            "article_number": "제12조",
            "risk_level": "High",
            "reason": "유해화학물질 관련 안전사고·환경오염 책임 범위와 금액에 제한이 없어 수급사업자에게 과도한 책임을 지운다.",
        },
        "chat_question": "유해화학물질 취급 조항에 책임 범위를 제한하는 게 일반적인가요?",
    },
    "standard_terms": {
        "document_text": """
회원 서비스 표준약관

제1조(목적)
이 약관은 회사와 회원 간 서비스 이용에 관한 사항을 정함을 목적으로 한다.

제9조(계약해지 및 환불)
회원이 서비스 이용 중 임의로 계약을 해지하는 경우, 회사는 이미 납부한 이용료를
어떠한 경우에도 환불하지 아니한다.
""",
        "clause_text": (
            "회원이 서비스 이용 중 임의로 계약을 해지하는 경우, 회사는 이미 납부한 "
            "이용료를 어떠한 경우에도 환불하지 아니한다."
        ),
        "context": {
            "article_number": "제9조",
            "risk_level": "High",
            "reason": "회원의 임의 해지 시 환불을 전면 배제하여 소비자에게 일방적으로 불리하다.",
        },
        "chat_question": "회원 임의 해지 시 환불을 제한하는 조항이 일반적인가요?",
    },
    "franchise": {
        "document_text": """
가맹 기본계약서

제1조(목적)
이 계약은 가맹본부와 가맹점사업자 간의 가맹사업 운영에 관한 사항을 정함을 목적으로 한다.

제11조(영업지역 보장)
가맹본부는 가맹점사업자의 영업지역 내에 동일 업종의 직영점 또는 가맹점을
설치할 수 있으며, 이에 대해 가맹점사업자는 어떠한 이의도 제기할 수 없다.
""",
        "clause_text": (
            "가맹본부는 가맹점사업자의 영업지역 내에 동일 업종의 직영점 또는 가맹점을 "
            "설치할 수 있으며, 이에 대해 가맹점사업자는 어떠한 이의도 제기할 수 없다."
        ),
        "context": {
            "article_number": "제11조",
            "risk_level": "High",
            "reason": "영업지역 보장이 없어 가맹점사업자의 상권을 가맹본부가 임의로 침해할 수 있다.",
        },
        "chat_question": "가맹계약에서 영업지역을 보장하지 않는 조항이 일반적인가요?",
    },
    "distribution": {
        "document_text": """
유통거래 기본계약서

제1조(목적)
이 계약은 공급자와 유통업자 간 상품 유통거래에 관한 사항을 정함을 목적으로 한다.

제8조(반품)
유통업자는 판매하지 못한 재고 상품에 대하여 어떠한 사유로도 공급자에게
반품할 수 없으며, 그 손실은 전부 유통업자가 부담한다.
""",
        "clause_text": (
            "유통업자는 판매하지 못한 재고 상품에 대하여 어떠한 사유로도 공급자에게 "
            "반품할 수 없으며, 그 손실은 전부 유통업자가 부담한다."
        ),
        "context": {
            "article_number": "제8조",
            "risk_level": "High",
            "reason": "미판매 재고 반품을 전면 금지하여 재고 부담을 유통업자에게 일방적으로 전가한다.",
        },
        "chat_question": "미판매 재고 반품을 전면 금지하는 조항이 일반적인가요?",
    },
    "agency": {
        "document_text": """
대리점거래 기본계약서

제1조(목적)
이 계약은 공급업자와 대리점 간 대리점거래에 관한 사항을 정함을 목적으로 한다.

제7조(최소판매목표)
대리점은 매월 공급업자가 정하는 최소판매목표를 반드시 달성하여야 하며,
이를 달성하지 못할 경우 계약을 즉시 해지당할 수 있다.
""",
        "clause_text": (
            "대리점은 매월 공급업자가 정하는 최소판매목표를 반드시 달성하여야 하며, "
            "이를 달성하지 못할 경우 계약을 즉시 해지당할 수 있다."
        ),
        "context": {
            "article_number": "제7조",
            "risk_level": "High",
            "reason": "최소판매목표 미달성 시 유예 없이 즉시 해지할 수 있어 대리점에 과도하게 불리하다.",
        },
        "chat_question": "최소판매목표 미달성 시 즉시 계약해지가 가능한 조항이 일반적인가요?",
    },
    "nda": {
        "document_text": """
비밀유지 기본계약서

제1조(목적)
이 계약은 갑과 을 간 상호 비밀정보 제공 및 보호에 관한 사항을 정함을 목적으로 한다.

제4조(비밀유지의무 기간)
을의 비밀유지의무는 계약 종료 후에도 기간의 제한 없이 영구히 존속한다.
""",
        "clause_text": (
            "을의 비밀유지의무는 계약 종료 후에도 기간의 제한 없이 영구히 존속한다."
        ),
        "context": {
            "article_number": "제4조",
            "risk_level": "Mid",
            "reason": "비밀유지의무 기간에 제한이 없어 계약 종료 후에도 무기한 구속된다.",
        },
        "chat_question": "비밀유지의무 기간을 영구로 정하는 조항이 일반적인가요?",
    },
}


def run(label, fn):
    """테스트 하나를 실행하고 결과/에러를 출력. 실패해도 다음 테스트는 계속 진행."""
    print(f"\n{'-' * 60}")
    print(f"[TEST] {label}")
    print("-" * 60)
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


def run_category(expected_category, case):
    """카테고리 하나에 대해 1단계~answer_query까지 전부 실행."""
    print(f"\n{'=' * 60}")
    print(f"### 카테고리: {expected_category} ###")
    print("=" * 60)

    results = {}
    category_holder = {}

    def _classify():
        actual = classify_document_category(case["document_text"])
        category_holder["value"] = actual
        match = "✅ 일치" if actual == expected_category else f"⚠️ 예상({expected_category})과 다름"
        print(f"  분류 일치 여부: {match}")
        return actual

    results["1단계: classify_document_category"] = run(
        f"[{expected_category}] 1단계 — classify_document_category()", _classify
    )

    results["search"] = run(
        f"[{expected_category}] search()",
        lambda: search(case["clause_text"], category=category_holder.get("value")),
    )

    results["retrieve_evidence"] = run(
        f"[{expected_category}] retrieve_evidence()",
        lambda: retrieve_evidence(case["clause_text"], category=category_holder.get("value")),
    )

    results["answer_query (alternative)"] = run(
        f"[{expected_category}] answer_query() — 하이라이트 클릭",
        lambda: answer_query(
            case["clause_text"],
            mode="alternative",
            category=category_holder.get("value"),
            context=case["context"],
        ),
    )

    results["answer_query (chat)"] = run(
        f"[{expected_category}] answer_query() — 자유 텍스트 채팅",
        lambda: answer_query(
            case["chat_question"], mode="chat", category=category_holder.get("value")
        ),
    )

    return results


def main():
    target = sys.argv[1] if len(sys.argv) > 1 else None

    if target is not None and target not in TEST_CASES:
        print(f"⚠️  알 수 없는 카테고리: {target}")
        print(f"   사용 가능: {', '.join(TEST_CASES.keys())}")
        return

    categories_to_run = {target: TEST_CASES[target]} if target else TEST_CASES

    all_results = {}
    for category, case in categories_to_run.items():
        all_results[category] = run_category(category, case)

    print(f"\n{'=' * 60}")
    print("=== 전체 요약 (카테고리별) ===")
    print("=" * 60)
    for category, results in all_results.items():
        print(f"\n[{category}]")
        for label, ok in results.items():
            print(f"  {'✅' if ok else '❌'} {label}")


if __name__ == "__main__":
    main()
