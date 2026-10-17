"""에이전트 설명 속 금액을 엔진 결과와 대조한다. 엔진이 낸 적 없는 금액은 '미검증'으로 표시한다(LLM이 지어낸 숫자 방어)."""
import re
from typing import Iterable, List

from quote.engine import Quote, baseline_quote, diff

_NUM = re.compile(r"\d{1,3}(?:,\d{3})+|\d{7,}")
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


def unverified_amounts(text: str, quotes: Iterable[Quote], extra: Iterable[int] = ()) -> List[str]:
    ok = known_amounts(quotes, extra)
    bad: List[str] = []
    for m in _NUM.findall(text):
        n = int(m.replace(",", ""))
        if n >= MIN_AMOUNT and n not in ok and m not in bad:
            bad.append(m)
    return bad
