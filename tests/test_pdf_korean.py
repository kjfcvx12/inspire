"""PDF 로딩의 한글·스캔본 경로. 실제 한글 PDF/OCR 호출은 수동 점검으로 확인했고(docs/history.md Entry 020),
여기서는 줄바꿈 이음, 혼합 PDF 쪽 단위 보고, OCR 주입/실패, OCR 결과 파싱·캐시를 가짜 객체로 고정한다."""
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "starters"))
sys.path.insert(0, str(ROOT / "tests"))
from common import docloader  # noqa: E402
from test_retrieval_stack import make_pdf  # noqa: E402


def mixed_pdf(path: Path):
    """1쪽은 텍스트, 2쪽은 텍스트 없는 쪽(스캔 쪽처럼)."""
    from pypdf import PdfReader, PdfWriter
    make_pdf(path, ["Page one has real text about refund policy"])
    w = PdfWriter()
    w.append(PdfReader(str(path)))
    w.add_blank_page(300, 200)
    with open(path, "wb") as f:
        w.write(f)


# ---------- 줄바꿈 이음 ----------

def test_unwrap_joins_midword_breaks_but_keeps_headings_and_short_lines():
    nl = "\n"
    text = nl.join([
        "한식 이용 안내서",                                       # 제목(짧음) → 유지
        "비빔밥은 밥 위에 나물과 고기를 올리고 고추장을 넣어 비벼 먹는 음식이다. 전주비빔밥이 가장 유명하",  # 긴 줄
        "며 육회를 올리기도 한다.",                                # 이어지는 줄
        "환불 규정: 시작 3일 전까지 전액 환불된다.",              # 짧은 줄 → 유지
    ])
    out = docloader.unwrap_korean_lines(text)
    assert "유명하며 육회를" in out                                # 단어 중간 줄바꿈이 이어졌다
    assert out.splitlines()[0] == "한식 이용 안내서"               # 제목은 본문에 붙지 않았다
    assert "한다." + nl + "환불 규정" in out                       # 짧은 줄 뒤에서는 줄바꿈 유지


def test_unwrap_keeps_english_and_very_short_text():
    nl = "\n"
    eng = nl.join(["the quick brown fox jumps over the lazy dog again and again", "and again"])
    assert docloader.unwrap_korean_lines(eng) == eng
    assert docloader.unwrap_korean_lines("가" + nl + "나") == "가" + nl + "나"


# ---------- 혼합 PDF / OCR 주입 ----------

def test_mixed_pdf_reports_the_missing_page(tmp_path):
    mixed_pdf(tmp_path / "m.pdf")
    chunks, skipped = docloader.load_chunks(str(tmp_path), ocr=None)
    assert any(s.endswith("m.pdf#p1") for s, _ in chunks)
    assert len(skipped) == 1 and "p2" in skipped[0][1] and "누락" in skipped[0][1]


def test_ocr_fills_missing_pages_and_clears_the_warning(tmp_path):
    mixed_pdf(tmp_path / "m.pdf")
    calls = []

    def fake_ocr(path, pages):
        calls.append(list(pages))
        return {2: "스캔 쪽에서 읽은 환불 안내 문장"}
    chunks, skipped = docloader.load_chunks(str(tmp_path), ocr=fake_ocr)
    assert calls == [[2]]                                   # 텍스트가 있는 1쪽은 OCR로 보내지 않는다
    assert skipped == []
    assert any(s.endswith("m.pdf#p2") and "환불" in t for s, t in chunks)


def test_ocr_failure_is_reported_and_other_pages_survive(tmp_path):
    mixed_pdf(tmp_path / "m.pdf")

    def broken_ocr(path, pages):
        raise RuntimeError("API 불가")
    chunks, skipped = docloader.load_chunks(str(tmp_path), ocr=broken_ocr)
    assert any(s.endswith("m.pdf#p1") for s, _ in chunks)
    reasons = " | ".join(why for _, why in skipped)
    assert "OCR 실패" in reasons and "누락" in reasons


def test_pdf_ocr_env_switch(monkeypatch):
    monkeypatch.delenv("PDF_OCR", raising=False)
    assert docloader._default_ocr() is None
    monkeypatch.setenv("PDF_OCR", "claude")
    assert docloader._default_ocr() is docloader.claude_ocr_pages


# ---------- claude_ocr_pages: 파싱·캐시·상한 ----------

class FakeReply:
    stop_reason = "end_turn"

    def __init__(self, text):
        self.content = [type("B", (), {"type": "text", "text": text})()]


@pytest.fixture
def ocr_env(tmp_path, monkeypatch):
    from common import llm, usage_log
    monkeypatch.setattr(usage_log, "ROOT", tmp_path)
    pdf = tmp_path / "scan.pdf"
    make_pdf(pdf, ["page one", "page two", "page three"])
    return llm, pdf


def test_claude_ocr_parses_pages_filters_and_uses_cache(ocr_env, monkeypatch):
    llm, pdf = ocr_env
    n = {"calls": 0}

    def fake_create(**kw):
        n["calls"] += 1
        block = kw["messages"][0]["content"][0]
        assert block["type"] == "document" and block["source"]["media_type"] == "application/pdf"
        return FakeReply("[[PAGE 1]]\n첫 쪽 글자\n[[PAGE 2]]\n\n[[PAGE 3]]\n셋째 쪽 글자")
    monkeypatch.setattr(llm, "create", fake_create)
    got = docloader.claude_ocr_pages(pdf, pages=[1, 3])
    assert got == {1: "첫 쪽 글자", 3: "셋째 쪽 글자"}        # 빈 쪽(2)은 제외, 요청한 쪽만
    again = docloader.claude_ocr_pages(pdf, pages=[3])
    assert again == {3: "셋째 쪽 글자"} and n["calls"] == 1   # 두 번째는 캐시에서


def test_claude_ocr_without_markers_falls_back_to_page_one(ocr_env, monkeypatch):
    llm, pdf = ocr_env
    monkeypatch.setattr(llm, "create", lambda **kw: FakeReply("마커 없이 온 전체 본문"))
    assert docloader.claude_ocr_pages(pdf) == {1: "마커 없이 온 전체 본문"}


def test_claude_ocr_page_limit(ocr_env, monkeypatch):
    llm, pdf = ocr_env
    monkeypatch.setattr(docloader, "OCR_MAX_PAGES", 2)
    monkeypatch.setattr(llm, "create", lambda **kw: pytest.fail("상한 초과인데 API를 호출했다"))
    with pytest.raises(RuntimeError, match="상한"):
        docloader.claude_ocr_pages(pdf)
