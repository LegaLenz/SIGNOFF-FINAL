"""
조항 단위 파싱 모듈.

전략:
  1. "제N조" 패턴으로 분리 (한국 계약서 최우선 기준)
  2. "N." 번호 패턴으로 분리 (제N조가 없을 때)
  3. Unstructured partition_text 활용 (위 두 패턴 모두 실패 시)
  4. 최후 수단: 전체를 단일 조항으로 반환

결과 포맷: List[{"clause_index": int, "text": str}]
"""

import re


# ── 조항 경계 패턴 ──────────────────────────────────────────────────────────
# 제N조 / 제N조의N  (줄 시작)
_ARTICLE_RE = re.compile(r"(?m)^(제\s*\d+\s*조(?:의\s*\d+)?)")

# N.  (1~99, 줄 시작, 점 뒤 공백 필수)
_NUMBERED_RE = re.compile(r"(?m)^(\d{1,2}\.)\s")


# ── 내부 헬퍼 ───────────────────────────────────────────────────────────────

def _clean(raw: str) -> str:
    text = re.sub(r"\f", "\n", raw)         # 폼피드 → 줄바꿈
    text = re.sub(r"[ \t]+", " ", text)     # 연속 공백 정리
    text = re.sub(r"\n{3,}", "\n\n", text)  # 과도한 빈 줄 제거
    return text.strip()


def _split_by_pattern(text: str, pattern: re.Pattern) -> list[dict]:
    """패턴 매치 위치를 경계로 삼아 텍스트를 조항 단위로 분리한다."""
    positions = [m.start() for m in pattern.finditer(text)]
    if not positions:
        return []

    clauses: list[dict] = []

    # 첫 경계 이전 전문(前文)이 있으면 preamble로 추가
    if positions[0] > 0:
        preamble = text[: positions[0]].strip()
        if preamble:
            clauses.append({"clause_index": 0, "text": preamble})

    for i, start in enumerate(positions):
        end = positions[i + 1] if i + 1 < len(positions) else len(text)
        chunk = text[start:end].strip()
        if chunk:
            clauses.append({"clause_index": len(clauses), "text": chunk})

    return clauses


def _split_by_unstructured(text: str) -> list[dict]:
    """
    Unstructured partition_text로 엘리먼트를 얻은 뒤,
    Title 타입 엘리먼트 중 조항 패턴과 일치하는 것을 경계로 삼아 그룹핑한다.
    """
    from unstructured.partition.text import partition_text

    elements = partition_text(text=text)
    clauses: list[dict] = []
    current: list[str] = []

    for el in elements:
        el_text = str(el).strip()
        if not el_text:
            continue

        is_boundary = type(el).__name__ == "Title" and (
            _ARTICLE_RE.match(el_text) or _NUMBERED_RE.match(el_text)
        )

        if is_boundary and current:
            clauses.append({"clause_index": len(clauses), "text": "\n".join(current)})
            current = [el_text]
        else:
            current.append(el_text)

    if current:
        clauses.append({"clause_index": len(clauses), "text": "\n".join(current)})

    return clauses


# ── 공개 API ─────────────────────────────────────────────────────────────────

def parse_clauses(text: str) -> list[dict]:
    """
    계약서 텍스트를 조항 단위 딕셔너리 리스트로 분리한다.

    Args:
        text: extractor.extract_text()가 반환한 원시 문자열.

    Returns:
        [{"clause_index": int, "text": str}, ...] 형태의 리스트.
        clause_index는 0-based.
    """
    cleaned = _clean(text)

    # 1순위: 제N조
    result = _split_by_pattern(cleaned, _ARTICLE_RE)
    if len(result) >= 2:
        return result

    # 2순위: 번호(N.)
    result = _split_by_pattern(cleaned, _NUMBERED_RE)
    if len(result) >= 2:
        return result

    # 3순위: Unstructured
    try:
        result = _split_by_unstructured(cleaned)
        if result:
            return result
    except Exception:
        pass

    # 최후 수단: 전체를 단일 조항으로
    return [{"clause_index": 0, "text": cleaned}]
