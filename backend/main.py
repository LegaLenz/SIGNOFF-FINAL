import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.routes import router

app = FastAPI(
    title="LegaLenz API",
    description="계약서·약관 자동 리스크 분석 Agent",
    version="0.1.0",
)

# 배포 환경마다 프론트엔드 origin이 다르므로 ALLOWED_ORIGINS(콤마 구분)로 오버라이드 가능하게 함.
# 미설정 시 기존 로컬 개발 기본값(Vite dev server)을 그대로 사용.
_allowed_origins = [
    origin.strip()
    for origin in os.getenv("ALLOWED_ORIGINS", "http://localhost:5173").split(",")
    if origin.strip()
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=_allowed_origins,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router)
