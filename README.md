# LegaLenz 📄⚖️

> 계약서·약관 자동 리스크 분석 Agent

계약서를 PDF 또는 이미지로 업로드하면 조항 단위로 리스크 등급(High / Mid / Low)을 분류하고,  
공정거래위원회 표준계약서를 근거로 대안 문구까지 자동 제안하는 AI Agent 서비스입니다.

---

## 📌 프로젝트 소개

프리랜서·스타트업이 계약서를 받았을 때 독소 조항을 직접 파악하기 어렵고,  
변호사 검토는 건당 30~50만 원에 수일이 걸립니다.  
LegaLens는 1분 안에 어디가 문제인지, 왜 문제인지, 어떻게 고치는지를 한 번에 알려줍니다.

---

## ✨ 주요 기능

- **PDF / 이미지 업로드** — PDF 또는 계약서 촬영 사진을 바로 업로드
- **자동 텍스트 추출** — PDF는 PDFMiner, 이미지는 EasyOCR로 텍스트 추출
- **조항 단위 자동 파싱** — 조항 경계를 감지해 분리
- **리스크 등급 분류** — 각 조항을 High / Mid / Low로 분류하고 이유 설명
- **하이라이트 UI** — High(빨강) / Mid(주황) / Low(노랑) 색상으로 시각화
- **대안 문구 자동 제안** — 공정거래위 표준계약서 기반 수정 문구 생성
- **결과 PDF 다운로드** — 분석 결과 저장 및 공유

---

## 🛠 기술 스택

### Backend
| 역할 | 기술 | 비용 |
|------|------|------|
| 서버 프레임워크 | FastAPI (Python 3.11+) | 무료 |
| PDF 텍스트 추출 | PDFMiner | 무료 |
| 이미지 텍스트 추출 | EasyOCR | 무료 |
| 조항 분류 LLM | GPT-4o-mini | 유료 (종량제) |
| 대안 문구 생성 LLM | GPT-4o | 유료 (종량제) |
| 에이전트 프레임워크 | LangChain | 무료 |
| Vector DB | Pinecone | 무료 플랜 |
| 임베딩 | OpenAI text-embedding-3-small | 유료 (종량제) |
| DB | PostgreSQL | 무료 |

### Frontend
| 역할 | 기술 |
|------|------|
| UI 프레임워크 | React |
| 텍스트 에디터 | Lexical |
| 스타일링 | Tailwind CSS |

### Infra
| 역할 | 기술 |
|------|------|
| 컨테이너 | Docker + Docker Compose |
| 배포 | Render / Railway |
| CI/CD | GitHub Actions |

---

## 🏗 시스템 아키텍처

```
사용자 업로드 (PDF or 이미지)
        ↓
파일 타입 감지
        ↓
┌──────────────────┬──────────────────────┐
│  PDF             │  이미지 (사진 촬영)   │
│  PDFMiner        │  EasyOCR             │
│  텍스트 추출     │  텍스트 추출          │
└──────────────────┴──────────────────────┘
        ↓
Unstructured (조항 단위 파싱)
        ↓
LangChain 분류 Agent — GPT-4o-mini (High / Mid / Low 분류)
        ↓
RAG 파이프라인 (Pinecone 검색 → GPT-4o 대안 문구 생성)
        ↓
React 하이라이트 UI (색상 구분 + PDF 저장)
```

---

## 📁 프로젝트 구조

```
legalens/
├── backend/
│   ├── main.py
│   ├── requirements.txt          
│   ├── .env.example              # ✅ backend 전용 env (DB, API키)
│   ├── api/
│   │   └── routes.py
│   ├── core/
│   │   ├── extractor.py
│   │   ├── parser.py
│   │   ├── classifier.py
│   │   └── rag.py
│   ├── db/
│   │   └── models.py
│   ├── data/
│   │   └── standard_contracts/
│   └── scripts/                  # ✅ 추가 — index_contracts.py 등 단발성 스크립트
│       └── index_contracts.py
├── frontend/
│   ├── src/
│   │   ├── components/
│   │   │   ├── Upload.jsx
│   │   │   ├── Editor.jsx
│   │   │   └── RiskPanel.jsx
│   │   └── App.jsx
│   ├── package.json              # ✅ npm init 하면 자동 생성
│   └── index.html                # ✅ Vite 쓰면 필요
├── docker-compose.yml
├── .env.example                  # ✅ 루트에도 Docker용으로 하나 (DB URL 등)
├── .gitignore
└── README.md
```

---

## ⚙️ 환경 변수 설정

`.env.example`을 복사해 `.env` 파일을 생성하고 아래 값을 채워주세요.

```env
# OpenAI (LLM + Embeddings)
OPENAI_API_KEY=your_openai_api_key

# Pinecone
PINECONE_API_KEY=your_pinecone_api_key
PINECONE_INDEX_NAME=legalens-index

# PostgreSQL
DATABASE_URL=postgresql://user:password@localhost:5432/legalens
```

---

## 🚀 실행 방법

### 1. 레포지토리 클론

```bash
git clone https://github.com/your-username/legalens.git
cd legalens
```

### 2. 환경 변수 설정

```bash
cp .env.example .env
# .env 파일에 API 키 입력
```

### 3. EasyOCR 모델 사전 다운로드

> EasyOCR은 첫 실행 시 한국어 모델 (약 500MB~1GB) 을 자동 다운로드합니다.  
> 배포 환경에서는 Docker 빌드 시 미리 다운로드해두는 것을 권장합니다.

```bash
python -c "import easyocr; easyocr.Reader(['ko', 'en'])"
```

### 4. Docker로 실행

```bash
docker-compose up --build
```

### 5. 로컬 개발 환경 (Docker 없이)

```bash
# 백엔드
cd backend
pip install -r requirements.txt
uvicorn main:app --reload

# 프론트엔드
cd frontend
npm install
npm run dev
```

### 6. 표준계약서 데이터 인덱싱

```bash
cd backend
python scripts/index_contracts.py
```

---

## 📅 개발 일정

| 기간 | 단계 | 주요 내용 |
|------|------|-----------|
| 6/25 ~ 6/29 | 사전 준비 | 개발 환경 세팅 · GitHub 세팅 · 표준계약서 수집 시작 |
| 6/30 ~ 7/6 | 1주차 | PDF 파싱 파이프라인 · EasyOCR 연동 · 표준계약서 Pinecone 임베딩 |
| 7/7 ~ 7/13 | 2주차 | LangChain 분류 Agent · GPT-4o-mini 연동 · FastAPI 엔드포인트 완성 |
| 7/14 ~ 7/20 | 3주차 | GPT-4o 대안 문구 생성 · RAG 파이프라인 연결 · 백엔드 E2E 테스트 |
| 7/21 ~ 7/24 | 4주차 | React + Lexical 하이라이트 UI · 프론트 ↔ 백엔드 연결 |
| 7/25 ~ 7/27 | 5주차 | 테스트셋 30~50건 제작 · Ground Truth 레이블링 · F1 정확도 측정 |
| 7/28 ~ 7/30 | 6주차 | 프롬프트 개선 · Docker 배포 · 발표 준비 🎤 |

---

## 📊 정확도 검증

자체 제작한 테스트 계약서 30~50건으로 정량 평가를 수행했습니다.

| 평가 항목 | 목표 | 결과 |
|-----------|------|------|
| High 리스크 분류 정확도 (F1) | 85% 이상 | 측정 예정 |
| 조항 파싱 정확도 | 90% 이상 | 측정 예정 |
| 대안 문구 적절성 (3점 척도) | 2.5 이상 | 측정 예정 |
| 분析 처리 시간 (10p 기준) | 60초 이내 | 측정 예정 |

> Ground Truth: 공정거래위원회 불공정 약관 심사 지침 기준으로 직접 레이블링

---

## ⚠️ 유의사항

> **본 서비스는 법률 자문이 아닌 참고용입니다.**  
> 중요한 계약은 반드시 전문 변호사와 상담하시기 바랍니다.

> **이미지 업로드 시 유의사항**  
> 계약서를 평평하게 펴서 정면으로 선명하게 촬영해 주세요.  
> 기울어지거나 조명이 강한 사진은 텍스트 인식률이 낮아질 수 있습니다.

---

## 👥 팀원

| 이름 | 역할 |
|------|------|
| 임소현 | PDF 파싱 · EasyOCR 연동 · 분류 Agent · FastAPI 서버 · 표준계약서 데이터 수집 |
| 이서진 | Pinecone 인덱싱 · RAG 파이프라인 · 대안 문구 생성 Chain · Docker 배포 |

---

## 📎 기획안

[LegaLens 프로젝트 기획안 보기](./docs/LegaLens_기획안.pdf)

---

## 📅 개발 기간

2026 · HATESLOP 4th ENGINEER FINAL PROJECT

---

## 📅 주차별 상세 계획

### 사전 준비 (6/25 ~ 6/29)

**임소현**
- Python 3.11 · FastAPI 개발 환경 세팅
- PDFMiner + Unstructured 설치 및 테스트
- 조항 파싱 로직 초안 설계
- 표준계약서 데이터 전처리 참여

**이서진**
- 공정거래위 표준계약서 30종 수집 시작
- Pinecone 계정 생성 및 환경 세팅
- OpenAI Embeddings 연동 테스트

**같이**
- GitHub 레포 생성 · 브랜치 전략 합의 · .env 구조 설계 · 발표 자료 제작 및 준비

---

### 1주차 (6/30 ~ 7/6) — 파싱 · 데이터 수집

**임소현**
- PDF 조항 단위 파싱 파이프라인 구현
- EasyOCR 연동 및 이미지 텍스트 추출 테스트
- 파일 타입 감지 로직 구현 (PDF / 이미지 분기)
- FastAPI 서버 기본 구조 셋업

**이서진**
- 표준계약서 30종 수집 완료 및 전처리
- Pinecone 인덱스 생성
- 표준계약서 임베딩 → Pinecone 업로드

**같이**
- 파싱 결과물 JSON 포맷 합의 · 중간 점검

---

### 2주차 (7/7 ~ 7/13) — 분류 Agent 구축

**임소현**
- LangChain 분류 Agent 구축
- High/Mid/Low 분류 프롬프트 설계
- GPT-4o-mini 연동 및 분류 테스트
- FastAPI 파일 업로드 엔드포인트 완성

**이서진**
- RAG 파이프라인 기본 구조 설계
- Pinecone 유사도 검색 구현
- 검색 결과 품질 테스트

**같이**
- 분류 Agent ↔ RAG 연결 포인트 합의 · API 명세 작성

---

### 3주차 (7/14 ~ 7/20) — RAG + 대안 문구 생성

**임소현**
- 분류 Agent → RAG 파이프라인 연결
- 백엔드 통합 테스트
- React 프론트 기본 구조 셋업

**이서진**
- GPT-4o 대안 문구 생성 Chain 구현
- 표준계약서 근거 포함 응답 포맷 설계
- PostgreSQL 분석 이력 저장 구현

**같이**
- 전체 백엔드 E2E 테스트 (PDF/이미지 업로드 → 대안 문구 출력까지)

---

### 4주차 (7/21 ~ 7/24) — 프론트엔드 구현

**임소현**
- Lexical 하이라이트 에디터 구현
- 리스크 색상 구분 UI (High/Mid/Low)

**이서진**
- 리스크 분석 결과 패널 구현
- PDF 다운로드 기능 추가

**같이**
- 프론트 ↔ 백엔드 API 연결 · UI 통합 테스트

---

### 5주차 (7/25 ~ 7/27) — 정확도 검증

**임소현**
- Precision / Recall / F1 측정 스크립트 작성
- 오분류 케이스 분석

**이서진**
- 전체 테스트셋 LegaLens 분석 실행
- 대안 문구 적절성 평가 (3점 척도)

**같이**
- 테스트 계약서 30~50건 제작 · Ground Truth 레이블링 · 수치 확인

---

### 6주차 (7/28 ~ 7/30) — 개선 · 발표 준비 🎤

**임소현**
- 프롬프트 개선 및 정확도 재측정
- README 최종 업데이트

**이서진**
- Docker 배포 · 최종 배포 환경 점검
- 데모용 테스트 계약서 준비

**같이**
- 발표 자료 제작 · 발표 리허설 · 7/30 발표 🎤

