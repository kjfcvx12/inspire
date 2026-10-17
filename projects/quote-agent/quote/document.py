"""화면에서 바로 보여줄 견적서 내용. 숫자는 모두 Quote(엔진 결과)에서 그대로 가져오고, 한글 읽기만 덧붙인다."""
from quote.engine import Quote, diff
from quote.korean import to_korean

NOTICE = "초안입니다. 가정값 기반이며 실제 견적이 아닙니다. 담당자 검토 전에는 고객에게 보내지 마세요."


def _won(n: int) -> dict:
    return {"금액": n, "한글": to_korean(n)}


def quote_document(q: Quote, base: Quote) -> dict:
    r = q.request
    d = diff(base, q)
    return {
        "제목": "견적서 (초안)", "고지": NOTICE, "수신": r.client,
        "용역명": "연구행정시스템 PI 용역 (서울대 기준안 기반, 가정 단가)", "기간": f"{r.weeks}주",
        "투입 인력": " · ".join(f"{k} {v}명" for k, v in r.team.items()),
        "범위": ", ".join(r.modules), "산출물": ", ".join(r.deliverables),
        "신규 항목(LLM 추정)": [f"{e.name} {e.effort_pct:g}% ({e.reason or '근거 없음'})" for e in r.extra_items],
        "옵션": [n for n, on in (("상주", r.onsite), ("영문 산출물", r.english_deliverables)) if on]
                + ([f"사후 지원 {r.support_months}개월"] if r.support_months else [])
                + ([f"협약 할인 {r.discount_pct:g}%"] if r.discount_pct else []),
        "항목": [{"항목": k, **_won(v)} for k, v in q.lines.items()],
        "공급가액": _won(q.supply), "부가세": _won(q.vat), "합계": _won(q.total),
        "일금": f"일금 {to_korean(q.total)}원정",
        "기준안 대비": _won(d["합계(VAT 포함)"]),
        "계산 기준": f"가정값 {q.assumptions_version} ({q.assumptions_as_of}) — 공개 정보가 없는 가정 단가",
        "경고": list(q.warnings),
    }
