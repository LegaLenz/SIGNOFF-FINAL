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
        → 근거를 찾았으면: GPT-4o 프롬프트 구성 (mode별로 다른 템플릿) → 근거 기반 응답
        → 근거를 못 찾았고 mode="alternative"면: 고정 fallback 문구
        → 근거를 못 찾았고 mode="chat"이면:
            → classify_scope()로 질문이 서비스 범위(표준계약서 6종 관련 계약/법률 질문,
              또는 document_clauses로 전달된 사용자의 업로드 계약서 자체에 대한 질문) 안인지 판단
                → 범위 안: GPT 일반 지식 + document_clauses(있으면)로 답변 (disclaimer 없이)
                → 범위 밖: 정중한 거절 응답
        mode="chat"이면 document_clauses(프론트가 매 요청마다 함께 보내는, 현재 화면에
        렌더링된 계약서 조항 전체)가 근거 유무와 무관하게 항상 프롬프트에 함께 들어간다.
        단, 질문에 "제N조" 언급이 있으면 _filter_document_clauses()가 해당 조항만
        추려서 넣는다(토큰 절감). 언급이 없으면 전체를 그대로 넣는 안전한 fallback.
        → {"text": str, "sources": [{contract_type, article_number, source_url}, ...]}

공개 API:
    RAGServiceError                                                — 도메인 예외
    search(query_text, category, top_k) -> list[dict]             — Pinecone 검색
    retrieve_evidence(query_text, category) -> list[dict]         — 검색+dedup+임계값
    classify_scope(query_text) -> bool                             — 범위 판단 (mode="chat" 근거 없음 시)
    answer_query(query_text, mode, category, context) -> dict     — 진입점 (생성 포함)
"""

import json
import logging
import re

from dotenv import load_dotenv
from openai import OpenAI
from pinecone import Pinecone

load_dotenv()

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

# ── 설정 ────────────────────────────────────────────────────────────────────

EMBEDDING_MODEL = "text-embedding-3-small"
GENERATION_MODEL = "gpt-4o"
LIGHT_MODEL = "gpt-4o-mini"  # 범위 판단(classify_scope) + 근거 없는 일반 답변(case2) 공용. gpt-4o(TPM 30,000)보다 TPM 여유가 훨씬 커 rate limit 병목을 분산시킨다.
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

OUT_OF_SCOPE_RESPONSE = {
    "text": "죄송하지만 이 질문은 계약서 분석 서비스의 범위를 벗어나 답변드리기 어려워요. 계약서 조항이나 계약·법률 관련 용어에 대해 질문해 주시면 도와드릴게요.",
    "sources": [],
}

# 서비스가 다루는 표준계약서 6종 — 범위 판단 프롬프트에 그대로 노출된다.
SCOPE_CATEGORIES_LABEL = "표준약관, 표준하도급계약서, 표준가맹계약서, 표준유통거래계약서, 표준대리점거래계약서, 표준비밀유지계약서(NDA)"


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
            from scripts.categories import CATEGORIES
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


# ── 문서 컨텍스트 (사용자가 업로드한 계약서 원문, mode="chat") ────────────────────

# 질문 안에 섞여 있는 "제N조" / "제N조의M" 언급을 찾는다. clause_utils.ARTICLE_RE는
# 줄 시작(^)에만 매칭되도록 만들어져 있어(파싱용) 문장 중간에 등장하는
# "제5조랑 제8조 비교해줘" 같은 표현은 못 잡는다 — 여긴 자유 텍스트 질문 안
# 어디든 등장할 수 있으므로 앵커 없이 별도 정규식을 쓴다.
_MENTIONED_ARTICLE_RE = re.compile(r"제\s*(\d+)\s*조(?:\s*의\s*(\d+))?")


def _extract_mentioned_articles(query_text: str) -> set[str]:
    """질문에서 언급된 조항 번호를 document_clauses의 article_number 표기("제5조", "제5조의2")로 정규화해 추출."""
    mentioned = set()
    for main, sub in _MENTIONED_ARTICLE_RE.findall(query_text):
        mentioned.add(f"제{main}조" + (f"의{sub}" if sub else ""))
    return mentioned


def _filter_document_clauses(query_text: str, document_clauses: list[dict] | None) -> list[dict] | None:
    """
    질문에 명시적으로 언급된 조항 번호가 있으면 해당 조항만 골라 문서 컨텍스트로
    쓴다 — case1(gpt-4o)에서 매 요청마다 문서 전체를 재전송해 TPM 한도에
    부딪히는 문제를 줄이기 위함.

    번호가 없거나(예: "손해배상 조항이 뭐야?") 매칭되는 조항이 하나도 없으면
    document_clauses를 그대로 반환한다 — 안전한 fallback. 이 필터는 토큰을
    줄이기 위한 것이지 정확도를 위해 정보를 빼는 게 아니므로, 특정 조항을
    콕 집어 가리키는 게 확실한 경우에만 좁힌다.
    """
    if not document_clauses:
        return document_clauses

    mentioned = _extract_mentioned_articles(query_text)
    if not mentioned:
        return document_clauses

    matched = [c for c in document_clauses if c.get("article_number") in mentioned]
    return matched or document_clauses


def _build_document_context_block(document_clauses: list[dict] | None) -> str:
    """
    프론트가 /chat 요청마다 함께 보내는, 현재 화면에 렌더링된 계약서 조항
    (article_number, text)을 프롬프트에 넣을 텍스트 블록으로 변환한다.

    document_clauses가 없으면(구버전 프론트 호환 등) 빈 문자열 — 문서 컨텍스트
    없이도 기존처럼 동작해야 한다. 어떤 조항이 넘어오는지는 answer_query()가
    _filter_document_clauses()로 미리 추려서 결정한다 — 이 함수는 항상
    주어진 리스트를 그대로 직렬화만 한다.
    """
    if not document_clauses:
        return ""
    lines = [
        f"[{c.get('article_number') or '조 번호 없음'}]\n{c.get('text', '')}"
        for c in document_clauses
    ]
    return "\n\n[사용자가 업로드한 계약서 조항 전문]\n" + "\n\n".join(lines)


# ── 범위 판단 & 일반 답변 (근거 없음, mode="chat") ────────────────────────────────

def classify_scope(query_text: str, document_clauses: list[dict] | None = None) -> bool:
    """
    Pinecone 근거를 못 찾은 자유 질문이 이 서비스가 다루는 범위
    (표준계약서 6종 관련 계약/법률 질문, 또는 사용자가 업로드한 계약서 자체에 대한 질문)
    안에 있는지 gpt-4o-mini로 판단한다.

    document_clauses를 함께 주는 이유: "이 계약서 제8조는 어떤 내용인가요?" 같은
    지시어 질문은 질문 텍스트만 보면 FTC 표준계약서와 무관해 보여 범위 밖으로
    오분류되기 쉽다. 실제 업로드된 조항 원문이 컨텍스트로 있으면 그 조항을
    가리키는 질문임을 판별기가 알아볼 수 있다.

    "범위 내"의 판단 기준은 일반 법률 지식이 아니라 [문서 근거(사용자가 업로드한
    이 계약서) + FTC 표준계약서 6종 카테고리]와의 관련 여부다. 문서 원문에 실제
    등장하거나 직접 관련된 질문("이의제기권이 뭐야?" ↔ 원문에 "이의를 제기하지
    아니한다"가 있는 경우)은, 그 표현이 모델의 일반 지식 사전에 흔한 법률 용어로
    등재돼 있는지와 무관하게 true여야 한다 — 이게 [1순위] 규칙이다. 문서에 없거나
    document_clauses가 아예 없는 경우에도 FTC 6개 카테고리 일반 계약/법률 질문은
    여전히 범위 내로 봐야 하므로 [2순위] 규칙은 문서 유무와 무관하게 항상 적용된다.

    분류 전용 호출이라 생성(GENERATION_MODEL)과 분리해 저렴한 모델을 쓴다.
    분류 실패 시에는 범위 밖(False)으로 처리해 근거 없는 답변을 만들지 않는다.
    """
    if document_clauses:
        document_section = (
            "\n\n아래는 사용자가 현재 업로드해 화면에 띄워둔 계약서 원문입니다. "
            "질문을 판단하기 전에 이 원문에 관련된 내용이 있는지 먼저 확인하세요."
            f"{_build_document_context_block(document_clauses)}"
        )
    else:
        document_section = ""

    system_prompt = (
        "당신은 계약서 위험 분석 서비스의 질문 범위 판별기입니다. "
        f"이 서비스는 공정거래위원회 표준계약서 6종({SCOPE_CATEGORIES_LABEL})을 근거로 "
        "계약서 조항의 위험 여부를 분석해주는 서비스입니다."
        f"{document_section}\n\n"
        "판단 기준은 다음 두 가지이며, 이 순서로 확인해 하나라도 해당하면 in_scope를 true로 판단하세요:\n\n"
        "[1순위] 문서 근거 우선 원칙 (사용자가 업로드한 계약서 원문이 위에 주어진 경우)\n"
        "질문에 등장하는 핵심 개념이나 표현이 위 계약서 원문에 등장하거나 원문 조항의 내용과 "
        "직접 관련되는지 먼저 확인하세요. 관련이 있다면, 그 표현이 일반적으로 널리 알려진 "
        "법률 용어인지 여부와 무관하게 true로 판단하세요.\n\n"
        "[2순위] 일반 카테고리 관련성 원칙 (문서에 없거나 문서가 주어지지 않은 경우에도 항상 적용)\n"
        "- 계약서 조항, 계약 조건, 계약 당사자의 권리·의무·책임·대금·해지 등에 관한 질문\n"
        "- 계약/법률 용어의 의미를 묻는 질문\n"
        "- 특정 업종(예: 화학, 제조, 유통 등) 맥락이 섞여 있어도 계약 조항이나 책임 범위 등을 "
        "다루는 질문이면 업종에 상관없이 true\n"
        "- 사용자가 업로드한 계약서 조항의 번호나 내용을 가리키는 질문(예: '제8조가 뭐야', "
        "'이 조항 위험해?')도 true\n\n"
        "위 두 원칙 중 어디에도 해당하지 않는, 계약·법률과 전혀 무관한 질문(일반 상식, 유명인 신상 "
        "등)만 false로 판단하세요.\n\n"
        "예시:\n"
        '- "유해화학물질 취급 조항에 책임 범위를 제한하는 게 일반적인가요?" → {"in_scope": true} '
        "(업종은 화학이지만 계약 조항의 책임 범위를 묻는 질문)\n"
        '- "하도급대금이 뭐야?" → {"in_scope": true}\n'
        '- "장원영 생일이 언제야?" → {"in_scope": false}\n\n'
        '반드시 JSON 객체 {"in_scope": true} 또는 {"in_scope": false} 형식으로만 응답하세요.'
    )
    try:
        response = openai_client.chat.completions.create(
            model=LIGHT_MODEL,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": query_text},
            ],
            response_format={"type": "json_object"},
            temperature=0,
        )
        parsed = json.loads(response.choices[0].message.content)
        return bool(parsed.get("in_scope", False))
    except Exception as e:
        logger.warning("[RAG] classify_scope 실패, 범위 밖으로 처리: %s", e)
        return False


def generate_general_chat_response(query_text: str, document_clauses: list[dict] | None = None) -> dict:
    """
    Pinecone 근거는 없지만 범위 안(계약/법률 일반 질문, 또는 업로드된 계약서 자체에
    대한 질문)으로 판단된 질문에 답변한다. sources는 항상 빈 리스트.

    document_clauses가 있으면 사용자가 업로드한 계약서 원문을 근거로 답하고,
    없으면 기존처럼 계약/법률 일반 지식으로 답한다.

    근거 유무를 언급하는 disclaimer는 절대 넣지 않는다 — 가독성과 신뢰도를 해친다.
    """
    system_prompt = (
        "당신은 계약서 및 법률 관련 질문에 답변하는 법률 보조 AI입니다. "
        "표준계약서 검색 근거는 없지만, 계약/법률 일반 지식을 바탕으로 "
        "질문에 자연스럽고 명확하게 답변하세요. "
        "사용자가 업로드한 계약서 조항 전문이 주어지면 그 원문 내용을 근거로 답변하세요. "
        "근거 자료가 없다는 사실이나 이를 암시하는 문구는 절대 언급하지 마세요."
        f"{_build_document_context_block(document_clauses)}"
    )
    try:
        # gpt-4o(TPM 30,000)가 이 서비스의 rate limit 병목이라 근거 없는
        # 일반 답변까지 gpt-4o로 보내면 짧은 간격 연속 채팅에서 429가 잘 난다.
        # 근거 기반 답변(generate_response)만 gpt-4o를 쓰고, 여긴 TPM 여유가
        # 훨씬 큰 gpt-4o-mini로 부하를 분산한다.
        response = openai_client.chat.completions.create(
            model=LIGHT_MODEL,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": query_text},
            ],
        )
    except Exception as e:
        raise RAGServiceError(f"일반 답변 생성 실패: {e}") from e

    return {"text": response.choices[0].message.content, "sources": []}


# ── 응답 생성 ─────────────────────────────────────────────────────────────────

def _build_messages(
    query_text: str,
    sources: list[dict],
    mode: str,
    context: dict | None,
    document_clauses: list[dict] | None = None,
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
            "근거가 부족하면 억지로 답변을 만들지 말고 근거가 부족하다고 답하세요.\n\n"
            "출력 형식은 다음 규칙을 반드시 따르세요:\n"
            "- 답변은 정확히 [대안 문구]와 [근거] 두 섹션으로만 구성하세요. 다른 섹션을 추가하지 마세요.\n"
            "- 마크다운 헤더(#, ##, ###, #### 등)를 사용하지 마세요. 섹션 제목은 반드시 [대안 문구], [근거] 형태의 대괄호 라벨만 사용하세요.\n"
            "- 코드블록(```)을 사용하지 마세요.\n"
            "- 번호 목록(1. 2. 3. 등)을 사용하지 마세요.\n"
            "- [대안 문구] 섹션은 조항 원문 형식으로, ①②③ 같은 항 번호 기호를 사용해 작성하세요.\n"
            "- [근거] 섹션은 참고한 표준계약서의 조 번호를 명시하며 왜 이렇게 수정했는지 설명하세요."
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
            "사용자가 업로드한 계약서 조항 전문이 함께 주어지면, 질문이 그 조항을 "
            "가리키는 경우 표준계약서 조항과 비교하며 실제 조항 원문 내용을 근거로 답변하세요. "
            "근거가 부족하면 솔직히 답하세요."
        )
        user_prompt = (
            f"[질문]\n{query_text}\n\n"
            f"[참고할 FTC 표준계약서 조항]\n{evidence_block}"
            f"{_build_document_context_block(document_clauses)}"
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
    document_clauses: list[dict] | None = None,
) -> dict:
    """dedup된 검색 결과를 근거로 GPT-4o 응답을 생성한다."""
    messages = _build_messages(query_text, sources, mode, context, document_clauses)
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
    document_clauses: list[dict] | None = None,
) -> dict:
    """
    RAG 파이프라인 진입점.

    Args:
        query_text: 검색·생성에 쓸 텍스트.
        mode: "alternative" (하이라이트 클릭) | "chat" (자유 텍스트)
        category: categories.py 카테고리 키. None이면 전체 검색.
        context: mode="alternative"일 때 분류 결과.
                 {"article_number": str, "risk_level": str, "reason": str}
        document_clauses: mode="chat"일 때, 현재 화면에 렌더링된 계약서 조항 전체
                 ([{"article_number": str, "text": str}, ...]). 사용자가 업로드한
                 계약서 자체를 가리키는 질문("이 계약서 제8조는...")에 답하기 위한
                 문서 컨텍스트로 프롬프트에 삽입되고, classify_scope 범위 판단에도 쓰인다.
                 질문에 조항 번호가 명시돼 있으면 _filter_document_clauses()가
                 해당 조항만 추려서 쓴다(토큰 절감, case1/case2 공통 적용).

    Returns:
        {"text": str, "sources": [{"contract_type", "article_number", "source_url"}, ...]}
    """
    logger.info("[RAG-DEBUG] answer_query query_text: %r", query_text)

    if mode == "chat":
        document_clauses = _filter_document_clauses(query_text, document_clauses)

    sources = retrieve_evidence(query_text, category=category)

    # 5. retrieve_evidence() 반환값
    logger.info(
        "[RAG-DEBUG] sources 수신: %s",
        [{"score": round(s["score"], 4), "contract_type": s["contract_type"], "article_number": s["article_number"]} for s in sources],
    )

    if not sources:
        if mode != "chat":
            return NO_EVIDENCE_RESPONSE.copy()

        in_scope = classify_scope(query_text, document_clauses=document_clauses)
        logger.info("[RAG] 근거 없음, mode=chat → classify_scope(%r) = %s", query_text, in_scope)
        if in_scope:
            return generate_general_chat_response(query_text, document_clauses=document_clauses)
        return OUT_OF_SCOPE_RESPONSE.copy()

    return generate_response(query_text, sources, mode, context, document_clauses=document_clauses)
