from fastapi import APIRouter, File, HTTPException, UploadFile

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

    return {
        "filename": file.filename,
        "clause_count": len(clauses),
        "clauses": clauses,
        # TODO (2주차): classifier.py — High/Mid/Low 분류 결과 추가
        # TODO (3주차): rag.py      — 대안 문구 추가
    }
