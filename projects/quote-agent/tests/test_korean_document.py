import pytest

from quote.document import quote_document
from quote.engine import QuoteRequest, baseline_quote, calculate
from quote.korean import annotate_won, to_korean


@pytest.mark.parametrize("n,expected", [
    (0, "영"), (1, "일"), (10, "십"), (100, "백"), (1_000, "천"), (10_000, "일만"), (12_345, "일만 이천삼백사십오"),
    (1_000_000, "백만"), (100_000_000, "일억"), (353_560_000, "삼억 오천삼백오십육만"),
    (321_418_000, "삼억 이천백사십일만 팔천"), (32_142_000, "삼천이백십사만 이천"),
    (1_000_000_000_000, "일조"), (-5_000, "마이너스 오천"),
])
def test_to_korean(n, expected):
    assert to_korean(n) == expected


def test_annotate_won_adds_reading_after_amounts_only():
    out = annotate_won("총액은 353,560,000원이고 기간은 16주, 5명입니다. 2026년 12,345원")
    assert "353,560,000원(삼억 오천삼백오십육만 원)" in out
    assert "12,345원(일만 이천삼백사십오 원)" in out
    assert "16주, 5명" in out and "2026년" in out                      # 금액이 아닌 숫자는 그대로
    assert annotate_won(out) == out                                   # 이미 붙어 있으면 다시 붙이지 않는다
    assert annotate_won("수수료 500원") == "수수료 500원"                  # 만 원 미만은 읽기를 붙이지 않는다


def test_document_numbers_equal_engine_and_have_korean():
    q = calculate(QuoteRequest(client="고려대학교", weeks=12, onsite=True))
    doc = quote_document(q, baseline_quote())
    assert doc["합계"]["금액"] == q.total and doc["공급가액"]["금액"] == q.supply and doc["부가세"]["금액"] == q.vat
    assert doc["합계"]["한글"] == to_korean(q.total)
    assert {i["항목"]: i["금액"] for i in doc["항목"]} == q.lines
    assert doc["일금"] == f"일금 {to_korean(q.total)}원정"
    assert "초안" in doc["고지"] and q.assumptions_version in doc["계산 기준"]
    assert doc["수신"] == "고려대학교" and doc["기간"] == "12주"


def test_annotate_won_keeps_the_minus_sign():
    assert annotate_won("차이는 -71,236,000원입니다") == "차이는 -71,236,000원(마이너스 칠천백이십삼만 육천 원)입니다"
    assert annotate_won("차이는 +24,819,000원") == "차이는 +24,819,000원(이천사백팔십일만 구천 원)"
    assert "(마이너스" not in annotate_won("기간 2026-12,345원")   # 앞 숫자에 붙은 하이픈은 부호가 아니다
