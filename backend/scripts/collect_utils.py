import re
import os

import requests
from bs4 import BeautifulSoup

from categories import CATEGORIES

BASE_URL = "https://www.ftc.go.kr"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
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
    """
    게시판 목록 페이지를 파싱해 항목 리스트를 반환.

    title_link의 href(view_href)를 추가로 반환.
    backfill_metadata.py가 여기서 nttSn을 뽑아 source_url을 조합하는 데 사용.
    """
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
                "download_href": download_link.get('href', ''),
                "view_href": title_link.get('href', ''),
            })

    return items


def extract_ntt_sn(view_href):
    """
    view_href(예: '/www/selectBbsNttView.do?key=202&bordCd=201&nttSn=46431')에서
    nttSn 값만 추출. 매칭 실패 시 None.

    주의: view_href가 'javascript:goView(...)' 형태의 JS 호출이면 이 정규식으로는
    못 뽑는다 — 실행해서 실제 href 값부터 확인 필요 (회의록 미확인 사항).
    """
    match = re.search(r'nttSn=(\d+)', view_href)
    return match.group(1) if match else None


def build_source_url(bordCd, key, ntt_sn):
    """
    최소 URL 파라미터(key, bordCd, nttSn)만으로 source_url 조합.
    """
    return f"{BASE_URL}/www/selectBbsNttView.do?key={key}&bordCd={bordCd}&nttSn={ntt_sn}"
