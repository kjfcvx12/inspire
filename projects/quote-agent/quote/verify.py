"""에이전트 설명 속 금액을 엔진 결과와 대조한다. 엔진이 낸 적 없는 금액은 '미검증'으로 표시한다(LLM이 지어낸 숫자 방어)."""
import re
from typing import Iterable, List

from quote.engine import Quote, baseline_quote, diff

_NUM = re.compile(r"\d{1,3}(?:,\d{3})+|\d{7,}")
_ABBR = re.compile(r"(\d{1,6}(?:\.\d{1,4})?)\s?억(?:\s?(\d{1,6}(?:,\d{3})*)\s?(천만|만))?\s?원?|(\d{1,6}(?:,\d{3})*)\s?(천만|만)\s?원")
_UNIT = {"만": 10_000, "천만": 10_000_000}
MAX_TEXT = 20_000        # 이보다 긴 설명은 앞부분만 검사한다(정규식 지연 방지)
MIN_AMOUNT = 1_000_000   # 이보다 작은 숫자(연도, 주 수, 인원 등)는 검사하지 않는다


def known_amounts(quotes: Iterable[Quote], extra: Iterable[int] = ()) -> set:
    quotes = list(quotes)
    base = baseline_quote()
    ok = set(extra)
    for q in [base, *quotes]:
        ok |= {q.supply, q.vat, q.total, *q.lines.values()}
        for row in q.allocation.values():
            ok |= set(row.values())
    for q in quotes:
        ok |= set(diff(base, q).values())
    for b in list(extra):                           # 예산과 각 안의 차이(예산 여유)
        ok |= {b - q.total for q in quotes} | {b - base.total}
    for a in quotes:                                # 시나리오끼리의 총액·공급가 차이
        for b in quotes:
            ok |= {a.total - b.total, a.supply - b.supply}
    return {abs(v) for v in ok}


def _abbr_value(m: "re.Match") -> tuple:
    """'3.5억', '3억 5,000만', '32,142만원' → (원 단위 값, 반올림 허용 오차). 표기 자릿수의 절반이 오차다."""
    if m.group(4):                                   # N만원, N천만원
        unit = _UNIT[m.group(5)]
        return int(m.group(4).replace(",", "")) * unit, unit / 2
    dec = m.group(1).partition(".")[2]
    value = float(m.group(1)) * 100_000_000
    if m.group(2):                                   # N억 M만 / N억 M천만
        unit = _UNIT[m.group(3)]
        return value + int(m.group(2).replace(",", "")) * unit, unit / 2
    return value, 0.5 * 10 ** (8 - max(len(dec), 1))   # 정수 '4억'도 0.05억(500만 원) 안에서만 일치로 본다


def unverified_amounts(text: str, quotes: Iterable[Quote], extra: Iterable[int] = ()) -> List[str]:
    """설명 속 금액 중 엔진 결과에 없는 것. 원 단위 숫자는 정확히 일치해야 하고, 억·만 축약은 표기 자릿수 반올림 안에서 일치해야 한다."""
    ok = known_amounts(quotes, extra)
    text = text[:MAX_TEXT]
    bad: List[str] = []
    for m in _NUM.findall(text):
        n = int(m.replace(",", ""))
        if n >= MIN_AMOUNT and n not in ok and m not in bad:
            bad.append(m)
    for m in _ABBR.finditer(text):
        value, tol = _abbr_value(m)
        shown = m.group(0).strip()
        if value >= MIN_AMOUNT and not any(abs(k - value) <= tol for k in ok) and shown not in bad:
            bad.append(shown)
    return bad
