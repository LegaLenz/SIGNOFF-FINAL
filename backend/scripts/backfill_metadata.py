import json
import os

from collect_utils import (
    CATEGORIES,
    BASE_SAVE_DIR,
    clean_title,
    get_max_page,
    get_list,
    extract_ntt_sn,
    build_source_url,
)

SOURCE = "공정거래위원회"

OUTPUT_PATH = os.path.join(BASE_SAVE_DIR, "..", "metadata", "source_urls.json")


def backfill_category(category, config):
    """
    카테고리 하나를 순회하며 로컬에 이미 존재하는 파일에 한해 source_url을 매칭한다.
    반환값: {category::file_name: {...}} 형태 딕셔너리
    """
    bordCd = config["bordCd"]
    key = config["key"]
    save_dir = os.path.join(BASE_SAVE_DIR, category)

    results = {}
    skipped_missing_file = []
    skipped_no_ntt_sn = []

    if not os.path.isdir(save_dir):
        print(f"⚠️  {category}: 로컬 폴더가 없음 ({save_dir}) — 스킵")
        return results

    max_page = get_max_page(bordCd, key)
    print(f"\n=== {category} 백필 시작 (총 {max_page}페이지) ===")

    for page in range(1, max_page + 1):
        items = get_list(bordCd, key, page)
        for item in items:
            number = item["number"]
            title = item["title"]
            view_href = item["view_href"]
            clean = clean_title(title)
            file_name = f"{number}_{clean}.txt"
            file_path = os.path.join(save_dir, file_name)

            if not os.path.exists(file_path):
                # collect_contracts.py에서 변환 실패했거나, 아직 안 받은 파일
                skipped_missing_file.append(file_name)
                continue

            ntt_sn = extract_ntt_sn(view_href)
            if ntt_sn is None:
                skipped_no_ntt_sn.append(file_name)
                continue

            source_url = build_source_url(bordCd, key, ntt_sn)
            vector_key = f"{category}::{file_name}"

            results[vector_key] = {
                "title": title,
                "category": category,
                "contract_type": config["label"],
                "source": SOURCE,
                "source_url": source_url,
            }

    print(f"  매칭 완료: {len(results)}건")
    if skipped_missing_file:
        print(f"  ⚠️  로컬 파일 없어서 스킵: {len(skipped_missing_file)}건")
        for name in skipped_missing_file[:5]:
            print(f"     - {name}")
        if len(skipped_missing_file) > 5:
            print(f"     ... 외 {len(skipped_missing_file) - 5}건")
    if skipped_no_ntt_sn:
        print(f"  ⚠️  nttSn 추출 실패로 스킵: {len(skipped_no_ntt_sn)}건")
        for name in skipped_no_ntt_sn[:5]:
            print(f"     - {name}")

    return results


def main():
    all_results = {}

    for category, config in CATEGORIES.items():
        all_results.update(backfill_category(category, config))

    os.makedirs(os.path.dirname(OUTPUT_PATH), exist_ok=True)
    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(all_results, f, ensure_ascii=False, indent=2)

    print(f"\n=== 전체 백필 완료: {len(all_results)}건 저장 ===")
    print(f"저장 위치: {os.path.abspath(OUTPUT_PATH)}")


if __name__ == "__main__":
    main()
