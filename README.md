# LegaLenz 📄⚖️

> 계약서·약관 자동 리스크 분석 Agent

계약서를 PDF 또는 이미지로 업로드하면 조항 단위로 리스크 등급(High / 기타)을 분류하고,  
공정거래위원회 표준계약서를 근거로 대안 문구까지 자동 제안하는 AI Agent 서비스입니다.

---

## 📌 프로젝트 소개

프리랜서·스타트업이 계약서를 받았을 때 독소 조항을 직접 파악하기 어렵고,  
변호사 검토는 건당 30~50만 원에 수일이 걸립니다.  
LegaLenz는 1분 안에 어디가 문제인지, 왜 문제인지, 어떻게 고치는지를 한 번에 알려줍니다.

---

## ✨ 주요 기능

- **PDF / 이미지 업로드** — PDF 또는 계약서 촬영 사진을 바로 업로드
- **자동 텍스트 추출** — PDF는 PDFMiner, 이미지는 EasyOCR로 텍스트 추출
- **조항 단위 자동 파싱** — 조항 경계를 감지해 분리
- **리스크 등급 분류** — 각 조항을 High / 기타로 분류하고 이유 설명
- **하이라이트 UI** — High(빨강) 조항만 색상으로 시각화
- **대안 문구 자동 제안** — 공정거래위 표준계약서 기반 수정 문구 생성

---

## 🛠 기술 스택

### Backend
| 역할 | 기술 | 비용 |
|------|------|------|
| 서버 프레임워크 | FastAPI (Python 3.11+) | 무료 |
| PDF 텍스트 추출 | PDFMiner | 무료 |
| 이미지 텍스트 추출 | EasyOCR | 무료 |
| 조항 분류 LLM | GPT-4o / GPT-4o-mini (미확정) | 유료 (종량제) |
| 대안 문구 생성 LLM | GPT-4o | 유료 (종량제) |
| 에이전트 프레임워크 | LangChain | 무료 |
| Vector DB | Pinecone | 무료 플랜 |
| 임베딩 | OpenAI text-embedding-3-small | 유료 (종량제) |

> ⚠️ 조항 분류(classifier.py) 모델은 GPT-4o / GPT-4o-mini 중 아직 미확정 — `classifier.py`의 `_MODEL` 상수 확정 후 본 문서 업데이트 필요. 대안 문구 생성(RAG)은 GPT-4o로 확정.

### Frontend
| 역할 | 기술 |
|------|------|
| UI 프레임워크 | React + Vite |
| 스타일링 | Tailwind CSS v4 (`@tailwindcss/vite`) |
| 패널 레이아웃 | react-resizable-panels |

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
LangChain 분류 Agent — GPT-4o/GPT-4o-mini(미확정) (High / 기타 분류)
        ↓
RAG 파이프라인 (Pinecone 검색 → GPT-4o 대안 문구 생성)
        ↓
React 하이라이트 UI (High 조항 색상 강조)
```

---

## 📁 프로젝트 구조

```
legalens/
├── backend/
│   ├── main.py
│   ├── Dockerfile                 # ✅ FastAPI + uvicorn --reload (single-stage)
│   ├── requirements.txt          
│   ├── .env                      # ✅ backend 전용 env (DB, API키) — 로컬/Docker 공용, git에는 커밋 안 함
│   ├── .env.example
│   ├── api/
│   │   └── routes.py
│   ├── core/
│   │   ├── extractor.py
│   │   ├── parser.py
│   │   ├── classifier.py
│   │   └── rag.py
│   ├── data/
│   │   └── standard_contracts/
│   └── scripts/                  # ✅ 추가 — index_contracts.py 등 단발성 스크립트
│       └── index_contracts.py
├── frontend/
│   ├── Dockerfile                 # ✅ Node + Vite (single-stage, hot reload)
│   ├── src/
│   │   ├── components/
│   │   │   ├── Upload.jsx        # 홈 화면 (드롭존)
│   │   │   ├── Editor.jsx        # 문서 패널 (조항 렌더링 · High 하이라이트)
│   │   │   └── ChatPanel.jsx     # 채팅 패널 (대안 문구 요청 · 스크롤)
│   │   ├── mocks/
│   │   │   └── clauses.json      # 프론트 개발용 mock 데이터
│   │   └── App.jsx
│   ├── package.json
│   └── index.html
├── docker-compose.yml             # ✅ backend + frontend 로컬 개발용 (배포용 아님)
├── .gitignore
└── README.md
```

> env 파일은 `backend/.env` 하나만 사용합니다. 루트에는 별도 `.env.example`을 두지 않습니다 — `docker-compose.yml`이 `backend/.env`를 `env_file`로 직접 참조합니다.

---

## ⚙️ 환경 변수 설정

`backend/.env.example`을 복사해 `backend/.env` 파일을 생성하고 아래 값을 채워주세요. (Docker로 실행할 때도 동일한 `backend/.env`를 사용합니다.)

```bash
cp backend/.env.example backend/.env
```

```env
# OpenAI (LLM + Embeddings)
OPENAI_API_KEY=your_openai_api_key

# Pinecone
PINECONE_API_KEY=your_pinecone_api_key
PINECONE_INDEX_NAME=legalens-index
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
cp backend/.env.example backend/.env
# backend/.env 파일에 API 키 입력
```

### 3. EasyOCR 모델 다운로드 (자동)

> EasyOCR은 첫 실행 시 한국어 모델 (약 500MB~1GB) 을 자동 다운로드합니다.  
> Docker 로컬 개발 환경에서는 `~/.EasyOCR` 캐시 경로를 named volume(`easyocr_models`)으로 마운트해두었기 때문에, 최초 1회만 다운로드되고 이후 컨테이너를 껐다 켜도 다시 받지 않습니다. 별도 사전 다운로드는 필요 없습니다.

### 4. Docker로 실행 (로컬 개발용 — backend + frontend, hot reload)

```bash
docker-compose up --build
```

- backend: http://localhost:8000 (FastAPI, `uvicorn --reload`)
- frontend: http://localhost:5173 (Vite dev server)

> 배포 최적화(멀티스테이지 빌드 등)를 하지 않은 로컬 개발/CI 테스트용 구성입니다. 실제 배포 이미지는 이후 별도로 구성합니다.

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
| 6/25 ~ 7/2 | 1주차 | 개발 환경·GitHub 세팅 후 표준계약서를 수집해 Pinecone에 임베딩하고, PDF·EasyOCR 파싱 파이프라인과 LangChain 분류 Agent(GPT-4o/GPT-4o-mini 미확정)를 구현해 FastAPI 엔드포인트까지 완성 |
| 7/3 ~ 7/9 | 2주차 | 분류 Agent와 RAG 파이프라인을 연결하고 백엔드 E2E 테스트를 마친 뒤 프론트엔드 기본 구조 착수 |
| 7/10 ~ 7/16 | 3주차 | 프론트엔드 구현을 마무리하고 프론트-백엔드를 연결, Docker 로컬 개발 환경까지 구성 |
| 7/17 ~ 7/23 | 4주차 | 테스트 계약서 30~50건으로 Ground Truth 레이블링과 F1 정확도를 측정한 뒤, 프롬프트 개선·재측정을 거쳐 Docker 배포 |
| 7/24 ~ 7/30 | 5주차 | 발표 준비 🎤 및 마무리 개선 |

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
| 임소현 | PDF 파싱 · EasyOCR 연동 · 분류 Agent (GPT-4o/GPT-4o-mini, 모델 미확정) · FastAPI 서버 · RAG 연동 · 프론트 문서/채팅 패널 · 전체 조립 |
| 이서진 | 표준계약서 데이터 수집 · Pinecone 인덱싱 · RAG 파이프라인 (rag.py) · 대안 문구 생성 · 프론트 공통 컴포넌트/홈/처리중 화면/패널 레이아웃/세션 리셋 정책 · Docker 배포 |

---

## 📎 기획안

[LegaLenz 프로젝트 기획안 보기](./docs/LegaLens_기획안.pdf)

---

## 📅 개발 기간

2026 · HATESLOP 4th ENGINEER FINAL PROJECT

---

## 📅 주차별 상세 계획

### 1주차 (6/25 ~ 7/2) — 사전 준비 · 파싱 · 데이터 수집

**임소현**
- Python 3.11 · FastAPI 개발 환경 세팅
- PDFMiner + Unstructured 설치 및 테스트
- 조항 파싱 로직 초안 설계
- PDF 조항 단위 파싱 파이프라인 구현
- EasyOCR 연동 및 이미지 텍스트 추출 테스트
- 파일 타입 감지 로직 구현 (PDF / 이미지 분기)
- FastAPI 서버 기본 구조 셋업

**이서진**
- Pinecone 계정 생성 및 환경 세팅
- OpenAI Embeddings 연동 테스트
- 공정거래위 표준계약서 30종 수집 시작 및 완료 · 전처리
- Pinecone 인덱스 생성
- 표준계약서 임베딩 → Pinecone 업로드

**같이**
- GitHub 레포 생성 · 브랜치 전략 합의 · .env 구조 설계 · 발표 자료 제작 및 준비
- 파싱 결과물 JSON 포맷 합의 · 중간 점검

---

### 2주차 (7/3 ~ 7/9) — 분류 Agent 구축 · RAG 파이프라인 연결 · 프론트 착수

**임소현**
- LangChain 분류 Agent 구축
- High/기타 분류 프롬프트 설계
- GPT-4o/GPT-4o-mini 연동 및 분류 테스트 (모델 미확정)
- FastAPI 파일 업로드 엔드포인트 완성
- 분류 Agent → RAG 파이프라인 연결 (`retrieve_evidence` 연동)
- 백엔드 E2E 테스트 스크립트 작성 (`test_e2e.py`)

**이서진**
- RAG 파이프라인 기본 구조 설계
- Pinecone 유사도 검색 구현
- 검색 결과 품질 테스트
- `rag.py` 구현 (search · dedup · retrieve_evidence · answer_query)
- Vite + Tailwind CSS v4 프론트 초기 세팅
- 공통 컴포넌트(로고, 배지, 버튼) · 홈 화면(드롭존) · 처리중 화면 구현 착수

**같이**
- 분류 Agent ↔ RAG 연결 포인트 합의 · API 명세 작성
- 전체 백엔드 E2E 테스트 (PDF 업로드 → 대안 문구 출력까지)
- 프론트-백 API 스키마 대조 및 확정

---

### 3주차 (7/10 ~ 7/16) — 프론트엔드 구현 완료 · 프론트-백 연결 · Docker 로컬 환경 구성

**임소현**
- 문서 패널 (`Editor.jsx`) — 조항 목록 렌더링, `risk_level === "High"` 빨간 하이라이트
- 채팅 패널 (`ChatPanel.jsx`) — 하이라이트 클릭 → 대안 문구 요청, 스크롤·퍼딩 처리
- 전체 조립 (`App.jsx`) — 홈 → 처리중 → 결과 화면 전환 상태관리

**이서진**
- 홈 화면(드롭존) · 처리중 화면 마무리
- 패널 리사이즈 구현 (`react-resizable-panels`)
- 이탈 리텐션 정책 (`beforeunload`, 뒤로가기 확인)
- `docker-compose up`으로 로컬에서 프론트-백 동시 구동되는 개발용 컨테이너 환경 구성 (배포용이 아닌 팀원 간 환경 통일 + CI 테스트용, 실제 배포는 4주차)

**같이**
- mock 데이터 → 실제 API 교체 · 프론트-백 통합 테스트
- Docker 컨테이너 환경에서 통합 테스트 진행 (로컬 환경 차이로 인한 문제 방지)

---

### 4주차 (7/17 ~ 7/23) — 정확도 검증 · 개선 · 배포

**임소현**
- Precision / Recall / F1 측정 스크립트 작성
- 오분류 케이스 분석
- 프롬프트 개선 및 정확도 재측정
- README 최종 업데이트

**이서진**
- 전체 테스트셋 LegaLenz 분석 실행
- 대안 문구 적절성 평가 (3점 척도)
- Docker 배포 · 최종 배포 환경 점검
- 데모용 테스트 계약서 준비

**같이**
- 테스트 계약서 30~50건 제작 · Ground Truth 레이블링 · 수치 확인

---

### 5주차 (7/24 ~ 7/30) — 발표 준비 🎤 및 개선

**같이**
- 발표 자료 제작 · 발표 리허설
- 여유 시간에 마이너 개선 사항 반영
- 7/30 발표 🎤
