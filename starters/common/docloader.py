"""문서 폴더 → 검색용 청크 [(출처, 텍스트)]. .txt .md .pdf 지원(.pdf는 pypdf, 페이지 번호를 출처에 붙인다).

    chunks, skipped = load_chunks("data")          # 출처 예: data/faq.md, data/guide.pdf#p3
    Index(chunks)                                   # common.textsearch / common.embedsearch

읽지 못한 파일(암호화·스캔본 PDF·인코딩 오류 등)은 예외로 죽지 않고 skipped에 사유와 함께 담아 돌려준다.
스캔본 PDF는 텍스트 레이어가 없어 빈 문자열이 나온다 → OCR은 하지 않으므로 skipped로 알린다."""
import re
from pathlib import Path

TEXT_EXT = (".txt", ".md")
PDF_EXT = (".pdf",)


def split_text(text: str, size: int = 500, overlap: int = 50) -> list[str]:
    """size 글자 단위로 자르되 overlap만큼 겹친다(문장 경계에서 잘려 검색이 빗나가는 것을 줄인다)."""
    if size <= overlap:
        raise ValueError("size는 overlap보다 커야 합니다")
    text = re.sub(r"[ \t]+\n", "\n", text).strip()
    if not text:
        return []
    step = size - overlap
    return [text[i:i + size] for i in range(0, len(text), step) if text[i:i + size].strip()]


def _read_pdf(path: Path):
    try:
        from pypdf import PdfReader
    except ImportError as e:
        raise RuntimeError("pypdf가 설치돼 있지 않습니다(pip install pypdf)") from e
    reader = PdfReader(str(path))
    if reader.is_encrypted:
        try:
            if not reader.decrypt(""):
                raise RuntimeError("암호화된 PDF")
        except Exception as e:  # 암호 해제 실패
            raise RuntimeError("암호화된 PDF") from e
    return [(i + 1, page.extract_text() or "") for i, page in enumerate(reader.pages)]


def load_chunks(docs_dir: str = "data", size: int = 500, overlap: int = 50):
    """(chunks, skipped) 반환. skipped는 [(경로, 사유)]."""
    chunks, skipped = [], []
    root = Path(docs_dir)
    if not root.is_dir():
        return chunks, [(str(root), "폴더 없음")]
    for p in sorted(root.rglob("*")):
        if not p.is_file():
            continue
        ext = p.suffix.lower()
        rel = p.as_posix()
        try:
            if ext in TEXT_EXT:
                text = p.read_text(encoding="utf-8")
                got = [(rel, c) for c in split_text(text, size, overlap)]
            elif ext in PDF_EXT:
                got = []
                for page_no, text in _read_pdf(p):
                    got += [(f"{rel}#p{page_no}", c) for c in split_text(text, size, overlap)]
                if not got:
                    skipped.append((rel, "텍스트 없음(스캔본 PDF일 수 있음)"))
            else:
                continue
        except UnicodeDecodeError:
            skipped.append((rel, "UTF-8이 아님"))
            continue
        except Exception as e:  # 손상·암호화·pypdf 없음
            skipped.append((rel, f"{type(e).__name__}: {str(e)[:80]}"))
            continue
        if not got and ext in TEXT_EXT:
            skipped.append((rel, "빈 파일"))
        chunks += got
    return chunks, skipped
