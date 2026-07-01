import re
import os
import sys
import zipfile
import requests
import magic
from bs4 import BeautifulSoup

BASE_URL = "https://www.ftc.go.kr"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}

CATEGORIES = {
    "standard_terms":  {"bordCd": "201", "key": "202"},
    "subcontract":     {"bordCd": "202", "key": "203"},
    "franchise":       {"bordCd": "203", "key": "204"},
    "distribution":    {"bordCd": "204", "key": "205"},
    "agency":          {"bordCd": "205", "key": "206"},
    "nda":             {"bordCd": "206", "key": "207"},
}

BASE_SAVE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "../data/standard_contracts")


def clean_title(title):
    title = re.sub(r'\[.*?\]', '', title)
    title = re.sub(r'\(.*?\)', '', title)
    title = title.strip()
    title = re.sub(r'\s+', '_', title)
    return title


def get_max_page(bordCd, key):
    url = f"{BASE_URL}/www/selectBbsNttList.do?bordCd={bordCd}&key={key}&pageIndex=1"
    response = requests.get(url, headers=HEADERS)
    soup = BeautifulSoup(response.text, 'html.parser')

    page_nums = []
    for link in soup.find_all('a'):
        href = link.get('href', '')
        if 'pageIndex=' in href:
            try:
                num = int(href.split('pageIndex=')[-1])
                page_nums.append(num)
            except:
                pass

    return max(page_nums) if page_nums else 1


def get_list(bordCd, key, page):
    url = f"{BASE_URL}/www/selectBbsNttList.do?bordCd={bordCd}&key={key}&pageIndex={page}"
    response = requests.get(url, headers=HEADERS)
    soup = BeautifulSoup(response.text, 'html.parser')

    items = []
    rows = soup.select('table tbody tr')
    for row in rows:
        num_td = row.select_one('td:first-child')
        title_link = row.select_one('a[href*="selectBbsNttView"]')
        download_link = row.select_one('a[href*="downloadBbsFile"]')

        if num_td and title_link and download_link:
            items.append({
                "number": num_td.get_text(strip=True),
                "title": title_link.get_text(strip=True),
                "download_href": download_link.get('href', '')
            })

    return items


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
