"""
표준계약서 제목(title) 임베딩 — _metadata.json과 분리해서 저장.

_metadata.json(크롤링 데이터, 재현 어려움)과 title_embedding(순수 계산 결과, 언제든
재현 가능)의 성격이 달라서 별도 파일로 관리한다:

    {category}/title_embeddings.npz — file_names, embeddings 두 배열을 한 파일에 저장

file_names[i]와 embeddings[i]가 항상 같은 파일 안에서 명시적으로 짝지어 저장되므로,
정렬 순서 등 암묵적 매핑에 의존하지 않는다 (별도 파일 2개로 나누면 서로 다른 시점에
갱신되어 순서가 어긋나는 클래식한 버그 패턴이 생길 수 있음).

_metadata.json은 전혀 건드리지 않음 (title 값을 읽기만 함).

제목이 바뀐 항목만 재계산하고, 안 바뀐 항목은 기존 임베딩을 그대로 재사용한다.

실행:
    cd backend
    python scripts/build_title_embeddings.py            # 전체 카테고리
    python scripts/build_title_embeddings.py subcontract # 카테고리 하나만
"""

import json
import os
import sys

import numpy as np
from dotenv import load_dotenv

load_dotenv()

from categories import CATEGORIES  # noqa: E402
from collect_utils import BASE_SAVE_DIR  # noqa: E402

from openai import OpenAI

EMBEDDING_MODEL = "text-embedding-3-small"
EMBED_BATCH_SIZE = 100
EMBEDDINGS_FILENAME = "title_embeddings.npz"

openai_client = OpenAI()


def embed_titles(titles: list[str]) -> list[list[float]]:
    """제목 리스트를 배치로 임베딩."""
    embeddings = []
    for i in range(0, len(titles), EMBED_BATCH_SIZE):
        batch = titles[i:i + EMBED_BATCH_SIZE]
        response = openai_client.embeddings.create(model=EMBEDDING_MODEL, input=batch)
        embeddings.extend(item.embedding for item in response.data)
    return embeddings


def load_source_metadata(save_dir: str) -> dict:
    """_metadata.json 읽기 (title 값의 출처, 이 스크립트는 이 파일을 절대 안 씀)."""
    metadata_path = os.path.join(save_dir, "_metadata.json")
    if not os.path.exists(metadata_path):
        return {}
    with open(metadata_path, "r", encoding="utf-8") as f:
        return json.load(f)


def load_existing_embeddings(save_dir: str) -> dict:
    """
    기존 title_embeddings.npz가 있으면 로드.
    {file_name: (title, embedding_row)} 형태로 반환. 없으면 빈 dict.

    npz 안에 file_names/titles/embeddings 세 배열이 같은 파일에 함께 저장돼 있어서,
    같은 인덱스 i의 세 값이 항상 한 세트로 짝지어져 있음이 보장된다.
    """
    npz_path = os.path.join(save_dir, EMBEDDINGS_FILENAME)
    if not os.path.exists(npz_path):
        return {}

    data = np.load(npz_path, allow_pickle=True)
    file_names = data["file_names"]
    titles = data["titles"]
    embeddings = data["embeddings"]

    return {
        file_names[i]: (titles[i], embeddings[i])
        for i in range(len(file_names))
    }


def process_category(category):
    save_dir = os.path.join(BASE_SAVE_DIR, category)
    metadata = load_source_metadata(save_dir)

    if not metadata:
        print(f"⚠️  {category}: _metadata.json 없음 또는 비어있음 — 스킵")
        return 0, 0

    existing = load_existing_embeddings(save_dir)

    file_names = sorted(metadata.keys())  # 이번 저장 호출 안에서만 쓰는 순서, 파일 간 암묵적 매핑 없음
    titles = [metadata[fn]["title"] for fn in file_names]

    to_embed_names = []
    to_embed_titles = []
    final_rows = [None] * len(file_names)

    for i, file_name in enumerate(file_names):
        title = titles[i]
        cached = existing.get(file_name)
        if cached is not None and cached[0] == title:
            final_rows[i] = cached[1]  # 제목 안 바뀜 — 기존 임베딩 재사용
        else:
            to_embed_names.append(file_name)
            to_embed_titles.append(title)

    if to_embed_titles:
        new_embeddings = embed_titles(to_embed_titles)
        new_embedding_map = dict(zip(to_embed_names, new_embeddings))
        for i, file_name in enumerate(file_names):
            if final_rows[i] is None:
                final_rows[i] = new_embedding_map[file_name]

    # file_names, titles, embeddings 세 배열을 하나의 npz 파일에 같은 순서로 저장
    # — 세 값이 항상 함께 짝지어 저장/로드되므로 순서가 어긋날 수 없음
    np.savez(
        os.path.join(save_dir, EMBEDDINGS_FILENAME),
        file_names=np.array(file_names, dtype=object),
        titles=np.array(titles, dtype=object),
        embeddings=np.array(final_rows, dtype=np.float32),
    )

    print(f"{category}: {len(to_embed_titles)}건 신규/재계산, 전체 {len(file_names)}건")
    return len(to_embed_titles), len(file_names)


def main():
    target = sys.argv[1] if len(sys.argv) > 1 else None

    if target is not None and target not in CATEGORIES:
        print(f"⚠️  알 수 없는 카테고리: {target}")
        print(f"   사용 가능: {', '.join(CATEGORIES.keys())}")
        return

    categories_to_run = [target] if target else list(CATEGORIES.keys())

    grand_new = 0
    grand_total = 0
    for category in categories_to_run:
        new_count, total_count = process_category(category)
        grand_new += new_count
        grand_total += total_count

    print(f"\n=== 완료: {grand_new}건 신규/재계산, 전체 {grand_total}건 ===")


if __name__ == "__main__":
    main()
