"""문서 폴더 → 검색용 청크 [(출처, 텍스트)]. .txt .md .pdf 지원(.pdf는 pypdf, 페이지 번호를 출처에 붙인다).

    chunks, skipped = load_chunks("data")          # 출처 예: data/faq.md, data/guide.pdf#p3
    Index(chunks)                                   # common.textsearch / common.embedsearch

읽지 못한 파일은 예외로 죽지 않고 skipped에 사유와 함께 돌려준다(앱 사이드바에 표시된다).
  - 암호화·손상 PDF, UTF-8이 아닌 텍스트, 빈 파일
  - 스캔본 PDF(텍스트 레이어 없음): 기본은 skipped로 알린다. PDF_OCR=claude 이면 Claude 비전으로 읽는다
    (API 비용 발생, logs/ocr_cache에 결과를 저장해 같은 파일을 다시 읽지 않는다).
    일부 쪽만 스캔인 혼합 PDF도 쪽 단위로 알리고, OCR이 켜져 있으면 그 쪽만 읽는다.
PDF의 줄바꿈이 한글 단어 중간을 쪼개는 문제는 긴 줄 뒤의 줄바꿈만 이어 붙여 줄인다(제목·짧은 줄은 유지)."""
import base64
import hashlib
import os
import re
from pathlib import Path
from typing import Callable, Optional

TEXT_EXT = (".txt", ".md")
PDF_EXT = (".pdf",)
OCR_MAX_PAGES = 20            # 한 파일에서 OCR로 읽을 최대 쪽 수(비용 상한)
OCR_MAX_BYTES = 20 * 1024 * 1024
_HANGUL = re.compile(r"[가-힣]")


def split_text(text: str, size: int = 500, overlap: int = 50) -> list[str]:
    """size 글자 단위로 자르되 overlap만큼 겹친다(문장 경계에서 잘려 검색이 빗나가는 것을 줄인다)."""
    if size <= overlap:
        raise ValueError("size는 overlap보다 커야 합니다")
    text = re.sub(r"[ \t]+\n", "\n", text).strip()
    if not text:
        return []
    step = size - overlap
    return [text[i:i + size] for i in range(0, len(text), step) if text[i:i + size].strip()]


def unwrap_korean_lines(text: str, ratio: float = 0.8) -> str:
    """PDF 자동 줄바꿈으로 쪼개진 한글 단어를 잇는다. 그 쪽에서 가장 긴 줄의 ratio 이상인 줄이고,
    줄 끝과 다음 줄 첫 글자가 모두 한글일 때만 줄바꿈을 지운다(제목·목록·문단 끝 같은 짧은 줄은 유지)."""
    lines = text.split("\n")
    longest = max((len(ln) for ln in lines), default=0)
    if longest < 10:
        return text
    out = [lines[0]] if lines else []
    for prev, cur in zip(lines, lines[1:]):
        if prev and cur and len(prev) >= ratio * longest and _HANGUL.match(prev[-1]) and _HANGUL.match(cur[0]):
            out[-1] += cur
        else:
            out.append(cur)
    return "\n".join(out)


def _open_pdf(path: Path):
    try:
        from pypdf import PdfReader
    except ImportError as e:
        raise RuntimeError("pypdf가 설치돼 있지 않습니다(pip install pypdf)") from e
    reader = PdfReader(str(path))
    if reader.is_encrypted:
        try:
            ok = reader.decrypt("")
        except Exception as e:
            raise RuntimeError("암호화된 PDF") from e
        if not ok:
            raise RuntimeError("암호화된 PDF")
    return reader


def _read_pdf(path: Path):
    """[(쪽 번호, 텍스트)] — 텍스트가 없는 쪽은 빈 문자열."""
    reader = _open_pdf(path)
    return [(i + 1, unwrap_korean_lines(page.extract_text() or "")) for i, page in enumerate(reader.pages)]


def claude_ocr_pages(path: Path, pages: Optional[list] = None) -> dict:
    """Claude 비전으로 PDF의 글자를 읽는다. {쪽 번호: 텍스트}. pages가 있으면 그 쪽만 돌려준다.
    PDF 전체를 한 번에 보내고(쪽 수·용량 상한 적용) 결과는 logs/ocr_cache에 저장한다. 실패하면 예외."""
    from . import llm
    from .usage_log import ROOT
    data = path.read_bytes()
    if len(data) > OCR_MAX_BYTES:
        raise RuntimeError(f"OCR 대상이 너무 큽니다({len(data) // 1024 // 1024}MB > 20MB)")
    n_pages = len(_open_pdf(path).pages)
    if n_pages > OCR_MAX_PAGES:
        raise RuntimeError(f"OCR 쪽 수 상한 초과({n_pages} > {OCR_MAX_PAGES})")
    cache = ROOT / "logs" / "ocr_cache" / (hashlib.sha1(data).hexdigest() + ".txt")
    if cache.is_file():
        raw = cache.read_text(encoding="utf-8")
    else:
        prompt = ("이 PDF의 모든 쪽에 보이는 글자를 있는 그대로 옮겨 적으세요. 요약·해석·번역 금지. "
                  "표는 행 단위로 한 줄씩. 각 쪽은 맨 앞에 [[PAGE 번호]] 한 줄을 쓰고 시작하세요. "
                  "글자가 없는 쪽은 [[PAGE 번호]]만 쓰세요.")
        content = [{"type": "document", "source": {"type": "base64", "media_type": "application/pdf",
                                                  "data": base64.standard_b64encode(data).decode()}},
                   {"type": "text", "text": prompt}]
        r = llm.create(messages=[{"role": "user", "content": content}], max_tokens=8192, tag="pdf_ocr")
        raw = llm.text_of(r)
        if r.stop_reason == "max_tokens":
            raw += "\n[[OCR 출력이 길이 제한으로 잘렸을 수 있음]]"
        cache.parent.mkdir(parents=True, exist_ok=True)
        cache.write_text(raw, encoding="utf-8")
    parts = re.split(r"\[\[PAGE\s*(\d+)\]\]", raw)
    found = {int(parts[i]): parts[i + 1].strip() for i in range(1, len(parts) - 1, 2)}
    if not found:  # 마커를 못 지켰으면 전체를 첫 쪽으로 취급
        found = {1: raw.strip()}
    return {n: t for n, t in found.items() if (pages is None or n in pages) and t}


def _default_ocr() -> Optional[Callable]:
    return claude_ocr_pages if os.environ.get("PDF_OCR", "").lower() == "claude" else None


def load_chunks(docs_dir: str = "data", size: int = 500, overlap: int = 50, ocr: Optional[Callable] = None):
    """(chunks, skipped) 반환. skipped는 [(경로, 사유)]. ocr: (Path, pages) → {쪽: 텍스트}, 기본은 PDF_OCR 환경변수."""
    ocr = ocr or _default_ocr()
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
                if not got:
                    skipped.append((rel, "빈 파일"))
            elif ext in PDF_EXT:
                got = []
                pages = _read_pdf(p)
                empty = [n for n, t in pages if not t.strip()]
                texts = {n: t for n, t in pages if t.strip()}
                if empty and ocr is not None:
                    try:
                        texts.update(ocr(p, empty))
                        empty = [n for n in empty if n not in texts]
                    except Exception as e:  # OCR 실패는 문서 전체를 막지 않는다
                        skipped.append((rel, f"OCR 실패: {type(e).__name__}: {str(e)[:80]}"))
                for n in sorted(texts):
                    got += [(f"{rel}#p{n}", c) for c in split_text(texts[n], size, overlap)]
                if empty:
                    label = ("텍스트 없음(스캔본일 수 있음; PDF_OCR=claude로 읽을 수 있음)" if not texts
                             else "텍스트 없는 쪽 누락(스캔 쪽): " + ", ".join(f"p{n}" for n in empty[:10]))
                    skipped.append((rel, label))
            else:
                continue
        except UnicodeDecodeError:
            skipped.append((rel, "UTF-8이 아님"))
            continue
        except Exception as e:  # 손상·암호화·pypdf 없음
            if isinstance(e, RuntimeError):  # 우리가 만든 사유 문장("암호화된 PDF" 등)
                reason = str(e)[:80]
            elif type(e).__name__.startswith("Pdf"):
                reason = f"손상된 PDF ({type(e).__name__})"
            else:
                reason = f"{type(e).__name__}: {str(e)[:80]}"
            skipped.append((rel, reason))
            continue
        chunks += got
    return chunks, skipped
