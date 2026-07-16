import logging

from fastapi import APIRouter, File, HTTPException, UploadFile
from pydantic import BaseModel

logger = logging.getLogger(__name__)

from core.classifier import classify_clauses, classify_document_category
from core.extractor import extract_text
from core.parser import parse_clauses
from core.rag import RAGServiceError, answer_query

router = APIRouter()

ALLOWED_CONTENT_TYPES = {"application/pdf", "image/jpeg", "image/png", "image/webp"}

_MAX_PDF_BYTES   = 10 * 1024 * 1024  # 10 MB
_MAX_IMAGE_BYTES =  5 * 1024 * 1024  #  5 MB


# ── 요청 바디 모델 ────────────────────────────────────────────────────────────

class AlternativeRequest(BaseModel):
    clause_index: int
    article_number: str | None
    text: str
    document_category: str   # /analyze 응답에서 프론트가 보존했다가 전송
    risk_level: str          # "High" / "Mid" / "Low" — 프롬프트 컨텍스트용
    reason: str              # 분류 근거 — 프롬프트 컨텍스트용


# ── 엔드포인트 ────────────────────────────────────────────────────────────────

@router.get("/health")
async def health_check():
    return {"status": "ok"}


@router.post("/analyze")
async def analyze_contract(file: UploadFile = File(...)):
    if file.content_type not in ALLOWED_CONTENT_TYPES:
        raise HTTPException(
            status_code=415,
            detail=f"지원하지 않는 파일 형식입니다: {file.content_type}",
        )

    data = await file.read()

    # 파일 크기 제한
    is_pdf = file.content_type == "application/pdf"
    max_bytes = _MAX_PDF_BYTES if is_pdf else _MAX_IMAGE_BYTES
    limit_label = "10MB" if is_pdf else "5MB"
    if len(data) > max_bytes:
        raise HTTPException(
            status_code=400,
            detail=f"파일 크기 초과: {limit_label} 이하만 허용됩니다.",
        )

    try:
        text = extract_text(file.filename, data, file.content_type)
    except ValueError as e:
        raise HTTPException(status_code=415, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"텍스트 추출 실패: {e}")

    try:
        clauses = parse_clauses(text)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"조항 파싱 실패: {e}")

    try:
        document_category = classify_document_category(text)
        classified = classify_clauses(clauses, category=None)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"리스크 분류 실패: {e}")

    # 예상 처리 시간: 조항 수 * 1.5초 (레이트 리밋 딜레이 0.5초 + GPT 응답 ~1초)
    estimated_seconds = round(len(classified) * 1.5, 1)

    return {
        "filename": file.filename,
        "document_category": document_category,
        "clause_count": len(classified),
        "estimated_seconds": estimated_seconds,
        "clauses": classified,
    }


@router.post("/clauses/alternative")
async def get_alternative(req: AlternativeRequest):
    logger.info("[RAG-DEBUG] answer_query query_text: %r", req.text)
    try:
        result = answer_query(
            query_text=req.text,
            mode="alternative",
            category=None,  # document_category는 사람 읽기용 문자열 — categories.py 키 아님
            context={
                "article_number": req.article_number,
                "risk_level": req.risk_level,
                "reason": req.reason,
            },
        )
        has_evidence = bool(result["sources"])
        return {
            "clause_index": req.clause_index,
            "alternative": result["text"] if has_evidence else None,
            "source_url": result["sources"][0]["source_url"] if has_evidence else None,
            "reason": req.reason,
        }
    except RAGServiceError as e:
        raise HTTPException(status_code=502, detail=str(e))


# TODO (4주차 이후): POST /chat
#   분석 결과를 컨텍스트로 받아 사용자 추가 질문에 답변하는 챗봇 엔드포인트.
#   프론트 UI 완성 후 구현 예정.
#
#   예상 요청 포맷:
#     {"analysis_id": str, "message": str}
#   예상 응답 포맷:
#     {"reply": str}
