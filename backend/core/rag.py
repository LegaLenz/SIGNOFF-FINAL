"""
RAG 파이프라인 (backend/core/rag.py)

하이라이트 클릭(mode="alternative")과 자유 텍스트 채팅(mode="chat") 두 경로가
동일한 검색·dedup·임계값 로직을 공유하고, 응답 생성 프롬프트만 분기한다.

흐름:
    query_text 임베딩
        → Pinecone 검색 (top_k=TOP_K, category 있으면 contract_type 필터,
            + article_number != "" 필터 항상 적용)
        → 신뢰도 임계값 체크 (최고 유사도 < CONFIDENCE_THRESHOLD → "근거 불충분")
        → dedup (같은 file_name 중 최고 유사도 1개만, 최대 MAX_SOURCES개)
        → GPT-4o 프롬프트 구성 (mode별로 다른 템플릿) → 응답 생성
        → {"text": str, "sources": [{contract_type, article_number, source_url}, ...]}

공개 API:
    RAGServiceError                                                — 도메인 예외
    search(query_text, category, top_k) -> list[dict]             — Pinecone 검색
    retrieve_evidence(query_text, category) -> list[dict]         — 검색+dedup+임계값
    answer_query(query_text, mode, category, context) -> dict     — 진입점 (생성 포함)
"""

import logging

from dotenv import load_dotenv
from openai import OpenAI
from pinecone import Pinecone

load_dotenv()

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

# ── 설정 ────────────────────────────────────────────────────────────────────

EMBEDDING_MODEL = "text-embedding-3-small"
GENERATION_MODEL = "gpt-4o"
PINECONE_INDEX_NAME = "legalenz-index"

TOP_K = 5
MAX_SOURCES = 3

# ⚠️ 튜닝 대상 — 4주차 정확도 측정(F1) 후 조정 예정.
# search()가 매 호출마다 실제 유사도 점수를 로그로 남기니,
# 4주차엔 그 로그 분포를 보고 정할 것 (감으로 정하지 말 것).
CONFIDENCE_THRESHOLD = 0.72  # 4주차 F1 측정 후 재조정 예정 (0.5는 너무 낮아 무관한 결과 통과)

NO_EVIDENCE_RESPONSE = {
    "text": "관련 표준계약서 근거를 찾지 못했습니다. 이 조항은 표준계약서와 직접 비교하기 어려운 특수 조항일 수 있습니다.",
    "sources": [],
}


# ── 예외 ────────────────────────────────────────────────────────────────────

class RAGServiceError(Exception):
    """
    외부 API(OpenAI, Pinecone) 호출 실패를 감싸는 도메인 예외.
    routes.py는 이 예외 하나만 잡아서 HTTP 502로 변환한다.
    """
    pass


# ── 클라이언트 초기화 ─────────────────────────────────────────────────────────

openai_client = OpenAI()
pc = Pinecone()
index = pc.index(PINECONE_INDEX_NAME)


# ── 임베딩 ──────────────────────────────────────────────────────────────────

def embed_query(text: str) -> list[float]:
    """단일 쿼리 텍스트를 text-embedding-3-small로 임베딩."""
    try:
        response = openai_client.embeddings.create(model=EMBEDDING_MODEL, input=[text])
    except Exception as e:
        raise RAGServiceError(f"쿼리 임베딩 실패: {e}") from e
    return response.data[0].embedding


# ── 검색 ────────────────────────────────────────────────────────────────────

def search(query_text: str, category: str | None = None, top_k: int = TOP_K) -> list[dict]:
    """
    Pinecone에서 query_text와 유사한 FTC 표준계약서 조항을 검색한다.

    Args:
        query_text: 검색 쿼리 (사용자 조항 원문 또는 자유 텍스트 질문)
        category: categories.py의 카테고리 키 (예: "subcontract").
                  None이면 전체 대상 (카테고리 필터 없음).
        top_k: 가져올 후보 개수 (dedup 이전)

    Returns:
        [{"score": float, "contract_type": str, "file_name": str,
          "article_number": str, "source_url": str, "text": str}, ...] — 유사도 내림차순

    Raises:
        RAGServiceError: Pinecone 검색 자체가 실패한 경우

    Note:
        article_number != "" 필터는 "agency" 카테고리에만 적용된다.
        agency 계약서는 전문(前文) 청크가 많아 top_k를 독점하는 문제가 있어
        조 번호가 있는 청크만 대상으로 삼는다. 다른 카테고리는 article_number
        채움률이 97%+이므로 별도 필터 없이도 문제없다.
    """
    query_embedding = embed_query(query_text)

    filter_conditions: dict = {}
    if category is not None:
        try:
            from categories import CATEGORIES
            if category in CATEGORIES:
                filter_conditions["contract_type"] = {"$eq": CATEGORIES[category]["label"]}
        except ImportError:
            pass

    # agency는 전문 청크가 top_k를 독점하므로 조 번호 있는 청크만 검색
    if category == "agency":
        filter_conditions["article_number"] = {"$ne": ""}

    try:
        response = index.query(
            vector=query_embedding,
            top_k=top_k,
            include_metadata=True,
            filter=filter_conditions,
        )
    except Exception as e:
        raise RAGServiceError(f"Pinecone 검색 실패: {e}") from e

    results = [
        {
            "score": match.score,
            "contract_type": match.metadata.get("contract_type", ""),
            "file_name": match.metadata.get("file_name", ""),
            "article_number": match.metadata.get("article_number", ""),
            "source_url": match.metadata.get("source_url", ""),
            "text": match.metadata.get("text", ""),
        }
        for match in response.matches
    ]

    top3 = results[:3]
    for i, r in enumerate(top3):
        logger.info(
            "[RAG] #%d  score=%.4f  threshold=%.2f  %s  %s",
            i + 1,
            r["score"],
            CONFIDENCE_THRESHOLD,
            r["contract_type"],
            r["article_number"],
        )

    return results


# ── dedup ────────────────────────────────────────────────────────────────────

def dedup(results: list[dict], max_sources: int = MAX_SOURCES) -> list[dict]:
    """같은 file_name에서 유사도 최고 1개만 남기고, 최대 max_sources개 반환."""
    best_per_file: dict[str, dict] = {}
    for r in results:
        fn = r["file_name"]
        if fn not in best_per_file or r["score"] > best_per_file[fn]["score"]:
            best_per_file[fn] = r
    return sorted(best_per_file.values(), key=lambda r: -r["score"])[:max_sources]


# ── 근거 검색 (생성 없이) ─────────────────────────────────────────────────────

def retrieve_evidence(query_text: str, category: str | None = None) -> list[dict]:
    """
    검색 + dedup + 신뢰도 임계값 체크까지 수행하고 근거 조항 리스트만 반환한다.
    GPT 생성은 하지 않는다.

    classifier.py가 위험도 분류 시 참고 자료로 쓸 때와
    answer_query()가 대안 문구 생성 전 단계로 재사용할 때 공유하는 진입점.

    Returns:
        dedup된 근거 리스트 (최대 MAX_SOURCES개). 신뢰도 임계값 미달이면 빈 리스트.
    """
    results = search(query_text, category=category)

    # 1. search() 전체 score 목록
    logger.info("[RAG-DEBUG] search 결과 scores: %s", [round(r["score"], 4) for r in results])

    # 2. CONFIDENCE_THRESHOLD 비교값
    top_score = results[0]["score"] if results else None
    logger.info(
        "[RAG-DEBUG] 임계값 비교: top_score=%s, threshold=%s, 통과=%s",
        round(top_score, 4) if top_score is not None else None,
        CONFIDENCE_THRESHOLD,
        bool(results and top_score >= CONFIDENCE_THRESHOLD),
    )

    if not results or top_score < CONFIDENCE_THRESHOLD:
        return []

    # 3. dedup() 직전
    logger.info(
        "[RAG-DEBUG] dedup 전: %s",
        [{"score": round(r["score"], 4), "file_name": r["file_name"], "article_number": r["article_number"]} for r in results],
    )

    deduped = dedup(results)

    # 4. dedup() 직후
    logger.info(
        "[RAG-DEBUG] dedup 후: %s",
        [{"score": round(r["score"], 4), "file_name": r["file_name"], "article_number": r["article_number"]} for r in deduped],
    )

    return deduped


# ── 응답 생성 ─────────────────────────────────────────────────────────────────

def _build_messages(
    query_text: str,
    sources: list[dict],
    mode: str,
    context: dict | None,
) -> list[dict]:
    evidence_block = "\n\n".join(
        f"[{s['contract_type']} {s['article_number']}]\n{s['text']}"
        for s in sources
    )

    if mode == "alternative":
        user_article_number = (context or {}).get("article_number") or "해당 조항"
        risk_level = (context or {}).get("risk_level", "")
        reason = (context or {}).get("reason", "")
        system_prompt = (
            "당신은 계약서 조항의 위험을 분석하고 공정거래위원회 표준계약서를 근거로 "
            "대안 문구를 제안하는 법률 보조 AI입니다. 아래 표준계약서 조항들을 근거로 삼아, "
            "사용자 조항을 어떻게 수정하면 좋을지 구체적인 대안 문구를 제시하세요. "
            "답변에서 사용자 조항을 지칭할 때는 반드시 주어진 조 번호로 명시하세요. "
            "근거가 부족하면 억지로 답변을 만들지 말고 근거가 부족하다고 답하세요."
        )
        user_prompt = (
            f"[분석 대상 조항: {user_article_number}]\n{query_text}\n\n"
            f"[분류 결과] 위험도: {risk_level}, 사유: {reason}\n\n"
            f"[참고할 FTC 표준계약서 조항]\n{evidence_block}"
        )
    else:
        system_prompt = (
            "당신은 계약서 관련 질문에 공정거래위원회 표준계약서를 근거로 답변하는 "
            "법률 보조 AI입니다. 아래 표준계약서 조항을 참고해 질문에 답하세요. "
            "근거가 부족하면 솔직히 답하세요."
        )
        user_prompt = (
            f"[질문]\n{query_text}\n\n"
            f"[참고할 FTC 표준계약서 조항]\n{evidence_block}"
        )

    return [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]


def generate_response(
    query_text: str,
    sources: list[dict],
    mode: str,
    context: dict | None = None,
) -> dict:
    """dedup된 검색 결과를 근거로 GPT-4o 응답을 생성한다."""
    messages = _build_messages(query_text, sources, mode, context)
    try:
        response = openai_client.chat.completions.create(
            model=GENERATION_MODEL,
            messages=messages,
        )
    except Exception as e:
        raise RAGServiceError(f"대안 문구 생성 실패: {e}") from e

    return {
        "text": response.choices[0].message.content,
        "sources": [
            {
                "contract_type": s["contract_type"],
                "article_number": s["article_number"],
                "source_url": s["source_url"],
            }
            for s in sources
        ],
    }


# ── 진입점 ───────────────────────────────────────────────────────────────────

def answer_query(
    query_text: str,
    mode: str = "chat",
    category: str | None = None,
    context: dict | None = None,
) -> dict:
    """
    RAG 파이프라인 진입점.

    Args:
        query_text: 검색·생성에 쓸 텍스트.
        mode: "alternative" (하이라이트 클릭) | "chat" (자유 텍스트)
        category: categories.py 카테고리 키. None이면 전체 검색.
        context: mode="alternative"일 때 분류 결과.
                 {"article_number": str, "risk_level": str, "reason": str}

    Returns:
        {"text": str, "sources": [{"contract_type", "article_number", "source_url"}, ...]}
    """
    logger.info("[RAG-DEBUG] answer_query query_text: %r", query_text)
    sources = retrieve_evidence(query_text, category=category)

    # 5. retrieve_evidence() 반환값
    logger.info(
        "[RAG-DEBUG] sources 수신: %s",
        [{"score": round(s["score"], 4), "contract_type": s["contract_type"], "article_number": s["article_number"]} for s in sources],
    )

    if not sources:
        return NO_EVIDENCE_RESPONSE.copy()
    return generate_response(query_text, sources, mode, context)
