from fastapi import APIRouter, File, HTTPException, UploadFile

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

    # TODO (1주차): extractor.py — 파일 타입 감지 + 텍스트 추출
    # TODO (1주차): parser.py  — 조항 단위 파싱
    # TODO (2주차): classifier.py — High/Mid/Low 분류 Agent
    # TODO (3주차): rag.py — 대안 문구 생성
    return {"status": "not_implemented", "filename": file.filename}
