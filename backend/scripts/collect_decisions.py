"""
공정위 의결서·재결서 PDF 크롤링 스크립트.

URL: https://case.ftc.go.kr/ocp/co/ltfr.do
필터: reprsntManagtTyCd=003 (시정명령), reprsntVioltTy=10* (불공정약관)
출력: backend/data/decisions/*.pdf

목록 페이지: Selenium headless Chrome (JS 렌더링 대응)
PDF 다운로드: requests (바이너리 파일 수신에 적합)

실행:
    cd backend
    python scripts/collect_decisions.py
    python scripts/collect_decisions.py --target 40 --delay 1.5
    python scripts/collect_decisions.py --dry-run   # 다운로드 없이 목록만 출력

사전 설치:
    pip install selenium webdriver-manager
"""

import argparse
import re
import sys
import time
from pathlib import Path
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

try:
    from selenium import webdriver
    from selenium.webdriver.chrome.options import Options as ChromeOptions
    from selenium.webdriver.chrome.service import Service as ChromeService
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support import expected_conditions as EC
    from selenium.webdriver.support.ui import WebDriverWait
    from webdriver_manager.chrome import ChromeDriverManager
except ImportError:
    print("[오류] selenium / webdriver-manager 패키지가 없습니다.")
    print("설치: pip install selenium webdriver-manager")
    sys.exit(1)

# ── 설정 ─────────────────────────────────────────────────────────────────────

BASE_URL      = "https://case.ftc.go.kr"
LIST_URL      = f"{BASE_URL}/ocp/co/ltfr.do"
FILE_LIST_URL = f"{BASE_URL}/ocp/co/getFileList.do"

SEARCH_PARAMS = {
    "pageIndex":          "1",
    "caseNo":             "",
    "caseNm":             "",
    "decsnNo":            "",
    "startRceptDt":       "",
    "endRceptDt":         "",
    "reprsntManagtTyCd":  "003",  # 대표조치유형: 시정명령
    "reprsntVioltTy":     "10*",  # 대표위반유형: 불공정약관
    "searchKrwd":         "",
}

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
    "Referer": LIST_URL,
    "Accept-Language": "ko-KR,ko;q=0.9",
}

OUTPUT_DIR    = Path(__file__).resolve().parents[1] / "data" / "decisions"
REQUEST_DELAY = 1.5   # 서버 부하 방지 (초)
PAGE_SIZE     = 10    # 사이트 기본 페이지당 항목 수
PAGE_LOAD_WAIT = 8    # 페이지 JS 렌더링 최대 대기 (초)


# ── WebDriver ─────────────────────────────────────────────────────────────────

def build_driver() -> webdriver.Chrome:
    """headless Chrome WebDriver 생성. ChromeDriver는 자동 설치."""
    options = ChromeOptions()
    options.add_argument("--headless=new")          # 창 없이 실행
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument("--window-size=1280,900")
    options.add_argument(f"user-agent={HEADERS['User-Agent']}")
    options.add_argument("--lang=ko-KR")
    # 불필요한 로그 억제
    options.add_experimental_option("excludeSwitches", ["enable-logging"])

    service = ChromeService(ChromeDriverManager().install())
    return webdriver.Chrome(service=service, options=options)


# ── 목록 파싱 ─────────────────────────────────────────────────────────────────

def _fill_form(driver: webdriver.Chrome, params: dict) -> None:
    """폼 필드에 값을 JS로 직접 입력."""
    for name, value in params.items():
        driver.execute_script(
            "var el = document.querySelector('[name=\"' + arguments[0] + '\"]');"
            "if (el) { el.value = arguments[1]; }",
            name, str(value)
        )


# 검색 버튼 셀렉터 — 사이트 구조에 맞게 순서대로 시도
_SEARCH_BTN_SELECTORS = [
    "button[type='submit']",
    "input[type='submit']",
    ".btn-search",
    "#searchBtn",
    ".btnSearch",
    "a.btn_search",
    "button.search",
]


def _click_search(driver: webdriver.Chrome) -> None:
    """검색 버튼 클릭 — 셀렉터 목록을 순서대로 시도하고 모두 실패하면 form.submit()."""
    for sel in _SEARCH_BTN_SELECTORS:
        try:
            driver.find_element(By.CSS_SELECTOR, sel).click()
            return
        except Exception:
            continue
    driver.execute_script("var f = document.querySelector('form'); if (f) f.submit();")


def fetch_list_page(page: int, driver: webdriver.Chrome) -> BeautifulSoup:
    """
    목록 페이지를 Selenium으로 로드하고 BeautifulSoup 반환.

    1. LIST_URL로 이동 (GET 파라미터 없음)
    2. 폼 필드에 SEARCH_PARAMS 값을 JS로 직접 입력 (pageIndex를 현재 페이지로 업데이트)
    3. 검색 버튼 클릭
    4. table tbody tr 등장까지 WebDriverWait
    """
    driver.get(LIST_URL)

    # 폼이 DOM에 나타날 때까지 대기
    try:
        WebDriverWait(driver, PAGE_LOAD_WAIT).until(
            EC.presence_of_element_located((By.TAG_NAME, "form"))
        )
    except Exception:
        pass

    # 현재 페이지 번호로 pageIndex 덮어쓰기
    _fill_form(driver, {**SEARCH_PARAMS, "pageIndex": str(page)})
    _click_search(driver)

    # 테이블 행이 나타날 때까지 대기 (JS 렌더링 완료 신호)
    try:
        WebDriverWait(driver, PAGE_LOAD_WAIT).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "table tbody tr"))
        )
    except Exception:
        # 대기 시간 초과 — 결과 없는 페이지일 수 있으므로 page_source 그대로 반환
        pass

    return BeautifulSoup(driver.page_source, "html.parser")


def _extract_doc_ids(tr) -> tuple[str, str] | None:
    """
    tr 내 a.down_files.pdf 버튼의 형제 input 두 개에서 (docId, docSn) 추출.
    버튼 또는 input이 없으면 None 반환.
    """
    btn = tr.select_one("a.down_files.pdf")
    if not btn:
        return None
    inputs = btn.parent.find_all("input")
    if len(inputs) < 2:
        return None
    return inputs[0].get("value", ""), inputs[1].get("value", "")


def download_pdf_direct(
    doc_id: str, doc_sn: str, fallback_name: str, session: requests.Session
) -> Path | None:
    """
    POST /ocp/co/getFileList.do — PDF 바이너리를 직접 수신해 파일로 저장.

    Content-Type이 application/pdf이면 응답 본문을 OUTPUT_DIR에 저장하고 Path 반환.
    파일명: Content-Disposition 헤더에서 추출, 없으면 fallback_name(case_id) 사용.
    실패 또는 PDF가 아닌 응답이면 None 반환.
    """
    post_headers = {
        **HEADERS,
        "Referer":      LIST_URL,
        "Content-Type": "application/x-www-form-urlencoded",
    }
    try:
        resp = session.post(
            FILE_LIST_URL,
            data={"docId": doc_id, "docSn": doc_sn},
            headers=post_headers,
            timeout=30,
        )
        resp.raise_for_status()
    except requests.RequestException as e:
        print(f"실패: {e}")
        return None

    content_type = resp.headers.get("Content-Type", "")
    if "pdf" not in content_type.lower():
        print(f"[경고] 예상치 않은 Content-Type: {content_type!r}")
        return None

    # 파일명: Content-Disposition 우선, 없으면 fallback_name
    stem = fallback_name
    cd = resp.headers.get("Content-Disposition", "")
    cd_match = re.search(r'filename[^;=\n]*=\s*["\']?([^"\';\n]+)', cd, re.IGNORECASE)
    if cd_match:
        cd_stem = Path(cd_match.group(1).strip()).stem
        if cd_stem:
            stem = cd_stem

    save_path = OUTPUT_DIR / f"{stem}.pdf"
    save_path.write_bytes(resp.content)
    return save_path


def parse_rows(soup: BeautifulSoup) -> list[dict]:
    """
    HTML에서 의결서 행 파싱.
    반환: [{"title": str, "case_id": str, "doc_id": str | None, "doc_sn": str | None}]

    ── 셀렉터 조정 포인트 ──
    실제 사이트 HTML 구조에 따라 아래 셀렉터를 수정:
      - 행: "table tbody tr"
      - 제목 링크: "a[href*='view']", "td.tit a"
      - PDF 버튼: a.down_files.pdf (형제 input[0]=docId, input[1]=docSn)
    """
    rows = []

    for tr in soup.select("table tbody tr"):
        # 제목 셀
        title_a = (
            tr.select_one("a[href*='view']")
            or tr.select_one("a[href*='View']")
            or tr.select_one("td.tit a")
            or tr.select_one("a")
        )
        if not title_a:
            continue

        title   = title_a.get_text(strip=True)
        case_id = _extract_case_id(title) or re.sub(r"\s+", "_", title)[:40]

        # PDF 버튼 형제 input에서 docId, docSn 추출
        doc_ids = _extract_doc_ids(tr)
        doc_id, doc_sn = doc_ids if doc_ids else (None, None)

        rows.append({
            "title":   title,
            "case_id": case_id,
            "doc_id":  doc_id,
            "doc_sn":  doc_sn,
        })

    return rows


def _extract_case_id(title: str) -> str | None:
    """제목에서 사건번호 추출 (예: '2024공약0012', '2024-공약-12')."""
    m = re.search(r"\d{4}[-_]?공약[-_]?\d+", title)
    return m.group().replace(" ", "") if m else None


# ── 메인 ─────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(description="공정위 의결서·재결서 PDF 크롤링")
    parser.add_argument("--target",  type=int,   default=40,           help="목표 다운로드 수 (기본: 40)")
    parser.add_argument("--delay",   type=float, default=REQUEST_DELAY, help="요청 간 딜레이 초")
    parser.add_argument("--dry-run", action="store_true",               help="다운로드 없이 목록만 출력")
    args = parser.parse_args()

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    print("=" * 60)
    print("공정위 의결서·재결서 PDF 크롤링 (Selenium headless)")
    print(f"URL   : {LIST_URL}")
    print(f"필터  : {SEARCH_PARAMS}")
    print(f"목표  : {args.target}개  |  저장: {OUTPUT_DIR}")
    if args.dry_run:
        print("[DRY-RUN] 다운로드 없이 목록만 출력합니다")
    print("=" * 60)

    print("\nChromeDriver 초기화 중...")
    driver  = build_driver()
    session = requests.Session()

    try:
        collected = 0
        page      = 1

        while collected < args.target and page <= 50:
            print(f"\n  페이지 {page} 로드 중...")

            soup = fetch_list_page(page, driver)

            # Selenium 세션 쿠키를 requests.Session에 동기화 (인증/csrf 쿠키 포함)
            for cookie in driver.get_cookies():
                session.cookies.set(cookie["name"], cookie["value"])

            rows = parse_rows(soup)

            if not rows:
                print("  결과 없음 — 수집 종료")
                if page == 1:
                    print()
                    print("  ⚠ 1페이지부터 결과가 없습니다. 아래를 확인하세요:")
                    print(f"    1. 브라우저에서 {LIST_URL} 직접 접속 후 필터 적용")
                    print(f"    2. 실제 파라미터 이름/값을 Network 탭에서 확인")
                    print(f"    3. SEARCH_PARAMS 상수 수정 후 재실행")
                break

            print(f"  {len(rows)}건 파싱됨")

            for item in rows:
                if collected >= args.target:
                    break

                doc_id = item["doc_id"]
                doc_sn = item["doc_sn"]

                if not doc_id or not doc_sn:
                    print(f"    [{item['case_id']}] PDF 버튼 없음 — 건너뜀")
                    continue

                # 이미 존재 여부를 case_id 기반 경로로 사전 확인
                if (OUTPUT_DIR / f"{item['case_id']}.pdf").exists():
                    print(f"    [{item['case_id']}] 이미 존재 — 건너뜀")
                    collected += 1
                    continue

                if args.dry_run:
                    print(f"    [DRY-RUN] {item['title'][:50]}  docId={doc_id}  docSn={doc_sn}")
                    collected += 1
                    continue

                print(f"    [{item['case_id']}] 다운로드...", end=" ")
                saved = download_pdf_direct(doc_id, doc_sn, item["case_id"], session)
                if saved:
                    size_kb = saved.stat().st_size // 1024
                    print(f"완료 ({size_kb}KB) → {saved.name}")
                    collected += 1
                else:
                    pass  # 오류 메시지는 download_pdf_direct 내부에서 출력

                time.sleep(args.delay)

            page += 1
            time.sleep(args.delay)

    finally:
        driver.quit()

    print()
    print("=" * 60)
    print(f"수집 완료: {collected}개 / 목표 {args.target}개")
    print(f"저장 위치: {OUTPUT_DIR}")
    print("=" * 60)


if __name__ == "__main__":
    main()
