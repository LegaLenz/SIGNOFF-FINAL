"""
표준계약서 인덱싱 스크립트.

backend/scripts/index_contracts.py

1. backend/data/standard_contracts/{category}/*.txt 읽기
2. clause_utils.split_clauses()로 조 단위 분리
   (제N조 → 번호(N.) → Unstructured → 단일조항 순 폴백 캐스케이드)
   → parser.py와 동일 함수를 공유해서 조항 그레인 일치 (1차 회의 §2 참고)
3. text-embedding-3-small로 임베딩
4. backfill_metadata.py가 생성한 _metadata.json에서 source_url 조회
5. Pinecone에 업로드 (vector_id = {category}::{filename}::{clause_index})

실행:
    cd backend
    python scripts/index_contracts.py
"""

import os
import sys
import json
import urllib.parse

from dotenv import load_dotenv

load_dotenv()

# backend/ 를 sys.path에 추가 → parser.py와 동일하게 "core" 패키지로 import
sys.path.append(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

from core.clause_utils import clean_text, split_clauses  # noqa: E402
from categories import CATEGORIES  # noqa: E402
from collect_utils import BASE_SAVE_DIR  # noqa: E402

from openai import OpenAI
from pinecone import Pinecone

EMBEDDING_MODEL = "text-embedding-3-small"
EMBEDDING_PRICE_PER_1M_TOKENS = 0.02  # USD, 2026년 기준 text-embedding-3-small 단가
PINECONE_INDEX_NAME = "legalenz-index"
SOURCE = "공정거래위원회"
EMBED_BATCH_SIZE = 100   # OpenAI embeddings 호출당 청크 수
UPSERT_BATCH_SIZE = 100  # Pinecone upsert 호출당 벡터 수

openai_client = OpenAI()
pc = Pinecone()  # PINECONE_API_KEY 환경변수에서 자동 로드
index = pc.index(PINECONE_INDEX_NAME)


def load_metadata(category):
    """
    backfill_metadata.py가 생성한 {category}/_metadata.json 로드.
    파일이 없으면 빈 dict 반환 (source_url 없이 진행, 경고만 출력).
    """
    save_dir = os.path.join(BASE_SAVE_DIR, category)
    metadata_path = os.path.join(save_dir, "_metadata.json")

    if not os.path.exists(metadata_path):
        print(f"⚠️  {category}: _metadata.json 없음 — source_url 없이 진행")
        return {}, save_dir

    with open(metadata_path, "r", encoding="utf-8") as f:
        return json.load(f), save_dir


def embed_texts(texts):
    """text-embedding-3-small로 배치 임베딩. (embeddings, 사용 토큰 수) 반환."""
    embeddings = []
    total_tokens = 0
    for i in range(0, len(texts), EMBED_BATCH_SIZE):
        batch = texts[i:i + EMBED_BATCH_SIZE]
        response = openai_client.embeddings.create(model=EMBEDDING_MODEL, input=batch)
        embeddings.extend(item.embedding for item in response.data)
        total_tokens += response.usage.total_tokens
    return embeddings, total_tokens


def build_metadata(config, file_name, source_url, article_number, clause_text):
    """
    Pinecone 메타데이터 dict 구성.

    Pinecone은 null 값을 허용하지 않는다. 필드를 아예 생략하는 대신 빈 문자열("")로
    채워서 모든 벡터가 6개 필드를 항상 동일하게 갖도록 통일한다 — 다운스트림(rag.py 등)
    에서 metadata.get() 없이 metadata["article_number"]처럼 바로 접근해도 KeyError가
    나지 않게 하기 위함. "" == 해당 필드 정보 없음(조항 번호 미인식 / source_url 미매칭).

    text: 조항 본문 그대로. GPT-4o 대안 문구 생성 시 근거로 삼을 실제 문구가 필요해서
    추가 (2-3주차 rag.py에서 사용). 조항 하나가 보통 수백 자 수준이라 Pinecone 메타데이터
    한도(40KB/벡터)엔 문제없음.
    """
    return {
        "contract_type": config["label"],
        "file_name": file_name,
        "source": SOURCE,
        "source_url": source_url or "",
        "article_number": article_number or "",
        "text": clause_text,
    }


def index_category(category, config):
    metadata_map, save_dir = load_metadata(category)

    if not os.path.isdir(save_dir):
        print(f"⚠️  {category}: 로컬 폴더 없음 — 스킵")
        return 0, 0

    txt_files = sorted(f for f in os.listdir(save_dir) if f.endswith(".txt"))
    print(f"\n=== {category} 인덱싱 시작 ({len(txt_files)}개 파일) ===")

    total_vectors = 0
    total_tokens = 0
    missing_metadata = []

    for file_name in txt_files:
        file_path = os.path.join(save_dir, file_name)
        with open(file_path, "r", encoding="utf-8") as f:
            raw = f.read()

        text = clean_text(raw)
        clauses = split_clauses(text)

        file_meta = metadata_map.get(file_name)
        if file_meta is None:
            missing_metadata.append(file_name)
        source_url = file_meta["source_url"] if file_meta else None

        chunk_texts = [c["text"] for c in clauses]
        embeddings, tokens_used = embed_texts(chunk_texts)
        total_tokens += tokens_used

        vectors = []
        for clause, embedding in zip(clauses, embeddings):
            # Pinecone record ID는 ASCII만 허용 (한글 파일명 그대로 못 씀).
            # file_name만 percent-encoding해서 ID에 쓰고, 원본은 metadata.file_name에 유지.
            safe_file_name = urllib.parse.quote(file_name, safe="")
            vector_id = f"{category}::{safe_file_name}::{clause['clause_index']}"
            metadata = build_metadata(
                config, file_name, source_url, clause["article_number"], clause["text"]
            )
            vectors.append((vector_id, embedding, metadata))

        for i in range(0, len(vectors), UPSERT_BATCH_SIZE):
            index.upsert(vectors=vectors[i:i + UPSERT_BATCH_SIZE])

        total_vectors += len(vectors)
        print(f"  완료: {file_name} ({len(clauses)}개 조항, {tokens_used}토큰)")

    print(f"  {category} 총 {total_vectors}개 벡터 업로드, {total_tokens}토큰 사용")
    if missing_metadata:
        print(f"  ⚠️  source_url 누락 (메타데이터 없음): {len(missing_metadata)}건")
        for name in missing_metadata[:5]:
            print(f"     - {name}")
        if len(missing_metadata) > 5:
            print(f"     ... 외 {len(missing_metadata) - 5}건")

    return total_vectors, total_tokens


def main():
    """
    실행:
        python scripts/index_contracts.py            # 전체 카테고리
        python scripts/index_contracts.py nda         # nda 카테고리만 (테스트용)
    """
    target = sys.argv[1] if len(sys.argv) > 1 else None

    if target is not None and target not in CATEGORIES:
        print(f"⚠️  알 수 없는 카테고리: {target}")
        print(f"   사용 가능: {', '.join(CATEGORIES.keys())}")
        return

    categories_to_run = {target: CATEGORIES[target]} if target else CATEGORIES

    grand_total_vectors = 0
    grand_total_tokens = 0
    for category, config in categories_to_run.items():
        vectors, tokens = index_category(category, config)
        grand_total_vectors += vectors
        grand_total_tokens += tokens

    estimated_cost = grand_total_tokens / 1_000_000 * EMBEDDING_PRICE_PER_1M_TOKENS
    print(f"\n=== 전체 인덱싱 완료: {grand_total_vectors}개 벡터 업로드 ===")
    print(f"=== 총 사용 토큰: {grand_total_tokens:,}토큰 (예상 비용: ${estimated_cost:.6f}) ===")


if __name__ == "__main__":
    main()
