"""
RAG 파이프라인 (backend/core/rag.py)

하이라이트 클릭(mode="alternative")과 자유 텍스트 채팅(mode="chat") 두 경로가
동일한 검색·dedup·임계값 로직을 공유하고, 응답 생성 프롬프트만 분기한다.

흐름:
    query_text 임베딩
        → 1단계: 사용자 계약서 카테고리 분류 (/analyze 시점 1회, classify_document_category)
        → 2단계: Pinecone 검색 (top_k=TOP_K, category 있으면 contract_type 필터, 없으면 전체 검색)
        → 신뢰도 임계값 체크 (최고 유사도 < CONFIDENCE_THRESHOLD → "근거 불충분")
        → dedup (같은 file_name 중 최고 유사도 1개만, 최대 MAX_SOURCES개)
        → GPT-4o 프롬프트 구성 (mode별로 다른 템플릿) → 응답 생성
        → {"text": str, "sources": [{contract_type, article_number, source_url}, ...]}

    (구) 제목 임베딩 기반 후보 추리기(2단계)는 제거됨 — 실측 결과, 같은 카테고리
    안에서는 제목이 "OO업종 표준하도급계약서"처럼 업종명만 다른 획일적 템플릿이라
    제목 유사도가 조항 내용 관련성과 무관하게 나왔고, 두 차례(보일러플레이트 조항,
    업종 특화 조항) 실측에서 전부 카테고리 필터만 썼을 때보다 결과가 나빠지는 것으로
    확인됨. build_title_embeddings.py, title_embeddings.npz는 더 이상 rag.py에서
    사용하지 않음 (스크립트 자체는 필요시 삭제해도 무방).

공개 API:
    classify_document_category(document_text) -> str | None   (1단계, /analyze 시점 1회 호출)
    answer_query(query_text, mode="chat", category=None, context=None) -> dict  (진입점, 클릭마다)
"""

import logging
import os

from dotenv import load_dotenv
from openai import OpenAI
from pinecone import Pinecone

load_dotenv()

from categories import CATEGORIES

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

# ── 설정 ────────────────────────────────────────────────────────────────────

EMBEDDING_MODEL = "text-embedding-3-small"
GENERATION_MODEL = "gpt-4o"
PINECONE_INDEX_NAME = "legalenz-index"

TOP_K = 5           # Pinecone 검색 시 가져올 후보 개수 (dedup 이전)
MAX_SOURCES = 3      # dedup 이후 최종 응답에 포함할 최대 출처 개수

# ⚠️ 튜닝 대상 — 4주차 정확도 측정(F1) 후 조정 예정. 현재는 임시값.
# 조정 시 이 값만 바꾸면 됨. search()가 매 호출마다 실제 유사도 점수를 로그로
# 남기니, 4주차엔 그 로그 분포를 보고 정할 것 (감으로 정하지 말 것).
CONFIDENCE_THRESHOLD = 0.5

NO_EVIDENCE_RESPONSE = {
    "text": "관련 표준계약서 근거를 찾지 못했습니다. 이 조항은 표준계약서와 직접 비교하기 어려운 특수 조항일 수 있습니다.",
    "sources": [],
}


class RAGServiceError(Exception):
    """
    rag.py 내부에서 외부 API(OpenAI, Pinecone) 호출 실패를 감싸는 도메인 예외.

    routes.py는 openai/pinecone의 원본 예외 타입을 몰라도 되고, 이 예외 하나만
    잡아서 HTTP 상태 코드로 변환하면 된다 (예: raise HTTPException(502, str(e))).
    """
    pass

openai_client = OpenAI()
pc = Pinecone()
index = pc.index(PINECONE_INDEX_NAME)


# ── 1단계: 사용자 계약서 카테고리 분류 ─────────────────────────────────────

DOCUMENT_CLASSIFICATION_MODEL = "gpt-4o-mini"  # classifier.py와 동일하게 가벼운 모델 사용
DOCUMENT_TEXT_SAMPLE_LENGTH = 3000  # 전체 문서 대신 앞부분만 사용 (비용/속도)


def classify_document_category(document_text: str) -> str | None:
    """
    사용자가 업로드한 계약서 전체 텍스트를 보고 6개 카테고리 중 하나로 분류한다.

    조항 단위가 아니라 문서 전체를 딱 한 번만 판단하면 되는 작업이라 /analyze 업로드
    시점에 1회만 호출하는 걸 전제로 설계함. 결과(category)를 프론트가 들고 있다가,
    이후 조항 클릭마다 answer_query(category=...)에 계속 넘겨주는 구조.

    Pinecone과 무관 — GPT 판단만 사용 (classifier.py의 조항 위험도 분류와 같은
    성격의 "LLM이 내용 보고 분류" 작업).

    Returns:
        categories.py의 카테고리 키(예: "subcontract"), 확신 없으면 None
        (None이면 호출 측에서 category 필터 없이 검색하는 걸 전제로 함)
    """
    categories_list = "\n".join(f"- {key}: {config['label']}" for key, config in CATEGORIES.items())
    system_prompt = (
        "당신은 계약서 문서를 보고 아래 6개 카테고리 중 하나로 분류하는 AI입니다.\n\n"
        f"{categories_list}\n\n"
        "카테고리 키 중 하나만 답하세요 (예: subcontract). 설명 없이 키만 답하세요. "
        "확신이 없으면 반드시 'unknown'이라고만 답하세요."
    )

    try:
        response = openai_client.chat.completions.create(
            model=DOCUMENT_CLASSIFICATION_MODEL,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": document_text[:DOCUMENT_TEXT_SAMPLE_LENGTH]},
            ],
        )
    except Exception as e:
        raise RAGServiceError(f"문서 카테고리 분류 실패: {e}") from e

    answer = response.choices[0].message.content.strip()
    return answer if answer in CATEGORIES else None


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
        category: categories.py의 카테고리 키(예: "subcontract"). 내부적으로
            CATEGORIES[category]["label"](예: "표준하도급계약서")로 변환해서 필터링한다.
            None이면 카테고리 제한 없음(전체 7,537개 벡터 대상).
        top_k: 가져올 후보 개수 (dedup 이전 raw 개수)

    Returns:
        [{"score": float, "contract_type": str, "file_name": str, "article_number": str,
          "source_url": str, "text": str}, ...] — 유사도 내림차순

    Raises:
        ValueError: category가 categories.py에 없는 키인 경우
        RAGServiceError: Pinecone 검색 자체가 실패한 경우
    """
    query_embedding = embed_query(query_text)

    query_kwargs = {
        "vector": query_embedding,
        "top_k": top_k,
        "include_metadata": True,
    }

    if category is not None:
        if category not in CATEGORIES:
            raise ValueError(
                f"알 수 없는 카테고리: {category!r} (사용 가능: {list(CATEGORIES.keys())})"
            )
        contract_type_label = CATEGORIES[category]["label"]
        query_kwargs["filter"] = {"contract_type": {"$eq": contract_type_label}}

    try:
        response = index.query(**query_kwargs)
    except Exception as e:
        raise RAGServiceError(f"Pinecone 검색 실패: {e}") from e

    results = []
    for match in response.matches:
        results.append({
            "score": match.score,
            "contract_type": match.metadata.get("contract_type", ""),
            "file_name": match.metadata.get("file_name", ""),
            "article_number": match.metadata.get("article_number", ""),
            "source_url": match.metadata.get("source_url", ""),
            "text": match.metadata.get("text", ""),
        })

    # 4주차 임계값 조정 근거 확보용 — 실제 유사도 분포를 남겨둔다.
    scores = [r["score"] for r in results]
    logger.info("search(%r) top_k=%d scores=%s", query_text[:30], top_k, scores)

    return results


# ── dedup ───────────────────────────────────────────────────────────────────

def dedup(results: list[dict], max_sources: int = MAX_SOURCES) -> list[dict]:
    """
    같은 file_name(표준계약서 파일)에서 여러 조항이 검색되면 유사도 최고 1개만 남긴다.
    이후 유사도 내림차순으로 최대 max_sources개만 반환.
    """
    best_per_file: dict[str, dict] = {}
    for r in results:
        fn = r["file_name"]
        if fn not in best_per_file or r["score"] > best_per_file[fn]["score"]:
            best_per_file[fn] = r

    deduped = sorted(best_per_file.values(), key=lambda r: -r["score"])
    return deduped[:max_sources]


# ── 근거 검색 (생성 없이) ────────────────────────────────────────────────

def retrieve_evidence(query_text: str, category: str | None = None) -> list[dict]:
    """
    검색(category 필터) + dedup + 신뢰도 임계값까지 수행하고, 근거 조항 리스트만
    반환한다. GPT 생성은 하지 않는다.

    classifier.py가 위험도 분류 시 참고 자료로 쓰거나(검증 근거 확보), answer_query()가
    대안 문구 생성 전 단계로 재사용하는 공유 진입점.

    Args:
        query_text: 조항 원문 또는 자유 텍스트 질문
        category: categories.py 카테고리 키. None이면 카테고리 제한 없음.

    Returns:
        dedup된 근거 리스트 (score 포함, 최대 MAX_SOURCES개). 신뢰도 임계값 미달이면 빈 리스트.
    """
    results = search(query_text, category=category)

    if not results or results[0]["score"] < CONFIDENCE_THRESHOLD:
        return []

    return dedup(results)


# ── 응답 생성 ─────────────────────────────────────────────────────────────

def _build_messages(query_text: str, sources: list[dict], mode: str, context: dict | None) -> list[dict]:
    """mode별로 GPT-4o에 보낼 프롬프트를 구성한다."""
    evidence_block = "\n\n".join(
        f"[{s['contract_type']} {s['article_number']}]\n{s['text']}"
        for s in sources
    )

    if mode == "alternative":
        # 하이라이트 클릭 — 분류 Agent가 넘긴 위험 조항에 대한 대안 문구 생성
        # context는 classifier.ClassifiedClause 기준: article_number(사용자 계약서 쪽 조 번호),
        # risk_level, reason. FTC 조 번호(evidence_block 안의 것)와는 다른 값이니 혼동 주의.
        user_article_number = (context or {}).get("article_number") or "해당 조항"
        risk_level = (context or {}).get("risk_level", "")
        reason = (context or {}).get("reason", "")
        system_prompt = (
            "당신은 계약서 조항의 위험을 분석하고 공정거래위원회 표준계약서를 근거로 "
            "대안 문구를 제안하는 법률 보조 AI입니다. 아래 표준계약서 조항들을 근거로 삼아, "
            "사용자 조항을 어떻게 수정하면 좋을지 구체적인 대안 문구를 제시하세요. "
            "답변에서 사용자 조항을 지칭할 때는 반드시 주어진 조 번호로 명시하세요. "
            "근거로 삼을 만한 표준계약서 조항이 부족하면 억지로 답변을 만들지 말고 "
            "근거가 부족하다고 답하세요."
        )
        user_prompt = (
            f"[분석 대상 조항: {user_article_number}]\n{query_text}\n\n"
            f"[분류 결과] 위험도: {risk_level}, 사유: {reason}\n\n"
            f"[참고할 FTC 표준계약서 조항]\n{evidence_block}"
        )
    else:
        # 자유 텍스트 채팅 — 대화형 응답
        system_prompt = (
            "당신은 계약서 관련 질문에 공정거래위원회 표준계약서를 근거로 답변하는 "
            "법률 보조 AI입니다. 아래 표준계약서 조항을 참고해 질문에 답하세요. "
            "근거가 부족하면 근거가 부족하다고 솔직히 답하세요."
        )
        user_prompt = (
            f"[질문]\n{query_text}\n\n"
            f"[참고할 FTC 표준계약서 조항]\n{evidence_block}"
        )

    return [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]


def generate_response(query_text: str, sources: list[dict], mode: str, context: dict | None = None) -> dict:
    """dedup된 검색 결과를 근거로 GPT-4o 응답을 생성하고 응답 스키마로 포장한다."""
    messages = _build_messages(query_text, sources, mode, context)

    try:
        response = openai_client.chat.completions.create(
            model=GENERATION_MODEL,
            messages=messages,
        )
    except Exception as e:
        raise RAGServiceError(f"대안 문구 생성 실패: {e}") from e

    text = response.choices[0].message.content

    return {
        "text": text,
        "sources": [
            {
                "contract_type": s["contract_type"],
                "article_number": s["article_number"],
                "source_url": s["source_url"],
            }
            for s in sources
        ],
    }


# ── 진입점 ──────────────────────────────────────────────────────────────────

def answer_query(
    query_text: str,
    mode: str = "chat",
    category: str | None = None,
    context: dict | None = None,
) -> dict:
    """
    RAG 파이프라인 진입점. 하이라이트 클릭과 자유 텍스트 채팅이 공유하는 단일 함수.

    Args:
        query_text: 검색·생성에 쓸 텍스트.
            - mode="alternative": 사용자 계약서 조항 원문 (classifier.ClassifiedClause.text)
            - mode="chat": 사용자가 입력한 자유 텍스트 질문
        mode: "alternative"(하이라이트 클릭, 대안 문구 생성) | "chat"(자유 텍스트, 대화형 응답)
        category: categories.py 카테고리 키로 검색 범위 제한. None이면 전체 검색.
        context: mode="alternative"일 때 분류 Agent 결과 일부 (classifier.ClassifiedClause 참고).
            {"article_number": "제5조", "risk_level": "High", "reason": "..."} 형태

    Returns:
        {"text": str, "sources": [{"contract_type", "article_number", "source_url"}, ...]}
    """
    deduped = retrieve_evidence(query_text, category=category)

    if not deduped:
        return NO_EVIDENCE_RESPONSE

    return generate_response(query_text, deduped, mode, context)
