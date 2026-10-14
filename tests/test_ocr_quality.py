"""OCR 결과 신뢰도 처리: 판독불가 표시 제거·비율 경고, 쪽 번호만 읽힌 쪽 제외."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "starters"))
sys.path.insert(0, str(ROOT / "tests"))
from common import docloader  # noqa: E402
from test_pdf_korean import mixed_pdf  # noqa: E402


def test_clean_ocr_text_strips_markers_and_counts_unreadable():
    raw = "환불 규정 [판독불가] 7일 이내 [판독 불가] 신청\n안녕히 가세요 [다른 문자]\n[메이테이 문자: 판독 불가]"
    clean, bad, words = docloader.clean_ocr_text(raw)
    assert bad == 3
    assert "판독" not in clean and "다른 문자" not in clean
    assert "환불 규정" in clean and "안녕히 가세요" in clean
    assert words == len(clean.split())


def test_low_reliability_ocr_is_reported_but_readable_text_is_indexed(tmp_path):
    mixed_pdf(tmp_path / "m.pdf")

    def shaky(path, pages):
        return {2: "[판독불가] 환불 [판독불가] [판독불가] 규정 [판독불가] 안내문 [판독불가]"}
    chunks, skipped = docloader.load_chunks(str(tmp_path), ocr=shaky)
    reasons = " | ".join(why for _, why in skipped)
    assert "OCR 신뢰 낮음" in reasons
    page2 = " ".join(t for s, t in chunks if s.endswith("#p2"))
    assert "환불" in page2 and "판독" not in page2


def test_reliable_ocr_has_no_warning(tmp_path):
    mixed_pdf(tmp_path / "m.pdf")

    def good(path, pages):
        return {2: "환불은 구매 후 7일 이내에 신청할 수 있습니다. 단순 변심은 반품 배송비를 고객이 부담합니다. "
                   "[판독불가]"}
    chunks, skipped = docloader.load_chunks(str(tmp_path), ocr=good)
    assert skipped == []                      # [판독불가] 1곳은 비율이 낮아 경고하지 않는다


def test_page_number_only_ocr_result_counts_as_missing(tmp_path):
    mixed_pdf(tmp_path / "m.pdf")
    chunks, skipped = docloader.load_chunks(str(tmp_path), ocr=lambda p, pages: {2: "1"})
    assert not any(s.endswith("#p2") for s, _ in chunks)
    assert any("누락" in why and "p2" in why for _, why in skipped)


def test_cache_key_changes_with_prompt(tmp_path, monkeypatch):
    """프롬프트를 바꾸면 이전 프롬프트로 만든 캐시를 재사용하지 않는다."""
    from common import llm, usage_log
    from test_retrieval_stack import make_pdf
    monkeypatch.setattr(usage_log, "ROOT", tmp_path)
    pdf = tmp_path / "s.pdf"
    make_pdf(pdf, ["page one"])
    calls = []

    class R:
        stop_reason = "end_turn"
        content = [type("B", (), {"type": "text", "text": "[[PAGE 1]]\n첫 쪽 글자"})()]
    monkeypatch.setattr(llm, "create", lambda **kw: calls.append(1) or R())
    docloader.claude_ocr_pages(pdf)
    docloader.claude_ocr_pages(pdf)
    assert len(calls) == 1
    monkeypatch.setattr(docloader, "OCR_PROMPT", docloader.OCR_PROMPT + " (변경)")
    docloader.claude_ocr_pages(pdf)
    assert len(calls) == 2
