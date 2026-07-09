"""
파일 타입 감지 + 텍스트 추출 모듈.

PDF  → PDFMiner
이미지 (JPG / PNG / WEBP 등) → EasyOCR (한국어 + 영어)
"""

import io
from pathlib import Path

_PDF_EXTENSIONS = {".pdf"}
_IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".tiff", ".bmp"}

# EasyOCR Reader는 모델 로딩이 무거우므로 최초 1회만 초기화
_ocr_reader = None


def _get_ocr_reader():
    global _ocr_reader
    if _ocr_reader is None:
        import easyocr
        _ocr_reader = easyocr.Reader(["ko", "en"], gpu=False)
    return _ocr_reader


def detect_file_type(filename: str, content_type: str | None = None) -> str:
    """
    파일 확장자 또는 MIME 타입으로 파일 종류를 반환한다.

    Returns:
        "pdf" 또는 "image"

    Raises:
        ValueError: 지원하지 않는 형식일 때.
    """
    ext = Path(filename).suffix.lower()
    if ext in _PDF_EXTENSIONS or content_type == "application/pdf":
        return "pdf"
    if ext in _IMAGE_EXTENSIONS or (content_type and content_type.startswith("image/")):
        return "image"
    raise ValueError(f"지원하지 않는 파일 형식: {ext!r} (content_type={content_type!r})")


def _extract_pdf(data: bytes) -> str:
    from pdfminer.high_level import extract_text as _pdfminer_extract

    return _pdfminer_extract(io.BytesIO(data))


def _extract_image(data: bytes) -> str:
    import numpy as np
    from PIL import Image

    reader = _get_ocr_reader()
    image = Image.open(io.BytesIO(data)).convert("RGB")
<<<<<<< HEAD
=======
    # paragraph=True: 인접 텍스트 블록을 하나로 합쳐 자연스러운 줄바꿈 유지
>>>>>>> origin/dev
    lines: list[str] = reader.readtext(np.array(image), detail=0, paragraph=True)
    return "\n".join(lines)


def extract_text(filename: str, data: bytes, content_type: str | None = None) -> str:
    """
    파일 바이트에서 텍스트를 추출한다.

    Args:
        filename:     원본 파일명 (확장자 기반 감지에 사용).
        data:         파일 원시 바이트.
        content_type: HTTP Content-Type 헤더 값 (선택).

    Returns:
        추출된 텍스트 문자열.
    """
    file_type = detect_file_type(filename, content_type)
    if file_type == "pdf":
        return _extract_pdf(data)
    return _extract_image(data)
