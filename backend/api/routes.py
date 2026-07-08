from fastapi import APIRouter, File, HTTPException, UploadFile

from core.classifier import classify_clauses
from core.extractor import extract_text
from core.parser import parse_clauses

router = APIRouter()

ALLOWED_CONTENT_TYPES = {"application/pdf", "image/jpeg", "image/png", "image/webp"}


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
        classified = classify_clauses(clauses)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"리스크 분류 실패: {e}")

    return {
        "filename": file.filename,
        "clause_count": len(classified),
        "clauses": classified,
        # TODO (2주차): rag.generate_alternatives(classified) 결과 추가
        #   - 각 조항에 alternative 또는 warning 포함
    }


# TODO (4주차 이후): POST /chat
#   분석 결과를 컨텍스트로 받아 사용자 추가 질문에 답변하는 챗봇 엔드포인트.
#   프론트 UI 완성 후 구현 예정.
#
#   예상 요청 포맷:
#     {"analysis_id": str, "message": str}
#   예상 응답 포맷:
#     {"reply": str}
