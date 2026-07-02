import os
import sys
import zipfile
import requests
import magic

from collect_utils import (
    BASE_URL,
    HEADERS,
    CATEGORIES,
    BASE_SAVE_DIR,
    clean_title,
    get_max_page,
    get_list,
)


def convert_to_txt(input_path, txt_path, number):
    file_type = magic.from_file(input_path).lower()

    if 'hancom' in file_type or 'hwp' in file_type:
        from hwp5.hwp5txt import main as hwp5_main
        original_argv = sys.argv
        try:
            sys.argv = ['hwp5txt', input_path, '--output', txt_path]
            hwp5_main()
        except SystemExit:
            pass
        finally:
            sys.argv = original_argv

    elif 'zip' in file_type:
        with zipfile.ZipFile(input_path, 'r') as z:
            for name in z.namelist():
                ext = os.path.splitext(name)[1].lower()
                if ext in ['.hwp', '.pdf', '.docx']:
                    extracted_path = os.path.join(os.path.dirname(input_path), os.path.basename(name))
                    with z.open(name) as src, open(extracted_path, 'wb') as dst:
                        dst.write(src.read())
                    result = convert_to_txt(extracted_path, txt_path, number)
                    os.remove(extracted_path)
                    return result
        print(f"ZIP 안에 지원 형식 없음 [{number}]")
        return False

    elif 'pdf' in file_type:
        from pdfminer.high_level import extract_text
        text = extract_text(input_path)
        with open(txt_path, 'w', encoding='utf-8') as f:
            f.write(text)

    elif 'word' in file_type or 'officedocument' in file_type or 'docx' in file_type:
        from docx import Document
        doc = Document(input_path)
        text = '\n'.join([p.text for p in doc.paragraphs])
        with open(txt_path, 'w', encoding='utf-8') as f:
            f.write(text)

    else:
        print(f"지원하지 않는 형식 [{number}]: {file_type}")
        return False

    return os.path.exists(txt_path)


def download_and_convert(item, save_dir, saved_titles):
    number = item["number"]
    title = item["title"]
    download_href = item["download_href"]
    clean = clean_title(title)

    if clean in saved_titles:
        print(f"스킵 (중복 제목): [{number}] {clean}")
        return
    saved_titles.add(clean)

    filename = f"{number}_{clean}"
    input_path = os.path.join(save_dir, f"{filename}.tmp")
    txt_path = os.path.join(save_dir, f"{filename}.txt")

    if os.path.exists(txt_path):
        print(f"스킵 (이미 존재): {txt_path}")
        return

    url = BASE_URL + download_href.replace('./', '/www/')
    response = requests.get(url, headers=HEADERS)
    with open(input_path, "wb") as f:
        f.write(response.content)

    try:
        success = convert_to_txt(input_path, txt_path, number)
        if success:
            print(f"완료: {txt_path}")
        else:
            print(f"변환 실패 [{number}]: {clean}")
    except Exception as e:
        print(f"변환 실패 [{number}]: {e}")
    finally:
        if os.path.exists(input_path):
            os.remove(input_path)


def collect(category, config):
    save_dir = os.path.join(BASE_SAVE_DIR, category)
    os.makedirs(save_dir, exist_ok=True)
    saved_titles = set()

    max_page = get_max_page(config["bordCd"], config["key"])
    print(f"\n=== {category} 수집 시작 (총 {max_page}페이지) ===")

    for page in range(1, max_page + 1):
        print(f"페이지 {page}/{max_page} 처리 중...")
        items = get_list(config["bordCd"], config["key"], page)
        for item in items:
            download_and_convert(item, save_dir, saved_titles)


if __name__ == "__main__":
    for category, config in CATEGORIES.items():
        collect(category, config)

    print("\n=== 전체 수집 완료 ===")
