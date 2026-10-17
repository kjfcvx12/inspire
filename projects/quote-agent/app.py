"""견적 에이전트 (Streamlit). 요청 문장 → 에이전트가 도구로 시나리오 계산 → 기준안(서울대 PI) 대비 비교.
단가·기준안은 공개 정보가 없어 가정값이다(사이드바에 표시). 견적은 담당자 검토 전 초안이다."""
import pandas as pd
import streamlit as st

from common.ui import md_safe
from quote import agent
from quote.engine import (CLIENT_SCALE, DELIVERABLE_WEIGHT, MODULE_WEIGHT, RATES, QuoteRequest, assumption_label,
                          assumption_text, baseline_quote, calculate, diff, sensitivity)
from quote.export import to_xlsx

st.set_page_config(page_title="견적 에이전트", layout="wide")
st.title("용역 견적 에이전트")
st.info("초안입니다. 담당자 검토 전에는 고객에게 보내지 마세요. 기준안과 단가는 공개 정보가 없어 가정값입니다. "
        "금액 단위는 원, 공급가액은 부가세 별도, 합계는 부가세 포함입니다.")

EXAMPLES = ["고려대에서 같은 용역을 3개월에 5명으로 요청했어. 견적 보여줘",
            "연세대, 20주, 상주 필수, 영문 산출물 포함, 종료 후 3개월 지원, 인원은 기준안과 동일하게",
            "고려대에서 예산 250,000,000원(부가세 포함) 안으로 해달래. 가능한 안을 보여줘",
            "연세대, 연구비관리 단계는 빼고 나머지 세 단계만. 인원은 어떻게 하면 돼?",
            "고려대, 기준안과 같은데 데이터 이관 계획서를 산출물로 추가해줘"]
with st.sidebar:
    st.subheader("가정값")
    st.caption(assumption_label() + " · 파일: data/assumptions.json")
    for title, table in (("월 단가(원)", RATES), ("단계 공수 비중", MODULE_WEIGHT),
                         ("산출물 공수 비중", DELIVERABLE_WEIGHT), ("대학 규모 계수", CLIENT_SCALE)):
        st.dataframe(pd.Series(table, name=title).to_frame(), width="stretch")
    st.caption(assumption_text())
    use_ai = st.toggle("AI 해석 사용", value=True, help="끄면 요청 문장을 외부 AI로 보내지 않고 규칙 기반으로만 해석합니다(정확도 낮음).")
    pick = st.radio("예시 요청", EXAMPLES, index=None)

text = st.text_area("견적 요청", value=pick or "", height=90, placeholder="예: 고려대, 4개월, 6명, 상주 없음")
if st.button("견적 만들기", type="primary", disabled=not text.strip()):
    with st.spinner("에이전트가 견적을 계산하는 중..."):
        st.session_state["res"] = agent.run(text.strip(), use_ai=use_ai)

res = st.session_state.get("res")
base = baseline_quote()
if res:
    if res.mock:
        st.warning("AI를 쓰지 않았거나 쓸 수 없어 규칙 기반 mock으로 동작했습니다. 해석 정확도가 낮습니다.")
    st.markdown(md_safe(res.text))
    if res.unverified:
        st.error("설명 속 다음 금액은 엔진 계산 결과에 없습니다. 아래 표의 숫자를 기준으로 보세요: " + ", ".join(res.unverified))

if res and res.quotes:
    first = res.quotes[0].request
    with st.expander("이렇게 이해했습니다 (확인하고 고칠 수 있어요)", expanded=True):
        with st.form("confirm"):
            c1, c2, c3 = st.columns(3)
            weeks = c1.number_input("기간(주)", 1, 104, first.weeks)
            discount = c1.number_input("할인율(%)", 0.0, 100.0, float(first.discount_pct))
            team = {r: c2.number_input(f"{r} 인원", 0, 20, first.team.get(r, 0)) for r in RATES}
            modules = c3.multiselect("단계", list(MODULE_WEIGHT), first.modules)
            delivs = c3.multiselect("산출물", list(DELIVERABLE_WEIGHT), first.deliverables)
            onsite = c3.checkbox("상주", first.onsite)
            english = c3.checkbox("영문 산출물", first.english_deliverables)
            extras = ", ".join(f"{e.name} {e.effort_pct:g}%({e.reason or '근거 없음'})" for e in first.extra_items)
            st.markdown(f"발주: {md_safe(first.client)}" + (f" · 신규 항목 :orange-badge[LLM 추정] {md_safe(extras)}" if extras
                                                         else " · 신규 항목 없음"))
            if st.form_submit_button("이 조건으로 다시 계산"):
                try:
                    req = first.model_copy(update={
                        "label": agent.unique_label("수정 확인안", [x.request.label for x in res.quotes]), "weeks": int(weeks), "duration_months": None, "discount_pct": discount,
                        "team": {r: n for r, n in team.items() if n}, "modules": modules, "deliverables": delivs,
                        "onsite": onsite, "english_deliverables": english})
                    res.quotes.append(calculate(QuoteRequest(**req.model_dump())))
                except ValueError as e:
                    st.error(f"조건을 확인하세요: {str(e)[:200]}")

if res and res.quotes:
    rows = {"기준안": base.lines}
    for q in res.quotes:
        rows[q.request.label] = q.lines
    df = pd.DataFrame(rows).fillna(0).astype(int)
    df.loc["공급가액(VAT 별도)"] = [base.supply] + [q.supply for q in res.quotes]
    df.loc["합계(VAT 포함)"] = [base.total] + [q.total for q in res.quotes]
    df.loc["필요 대비 투입 공수(%)"] = [round(base.capacity * 100)] + [round(q.capacity * 100) for q in res.quotes]
    df.loc["원가 대비 이윤율(%)"] = [round(base.margin * 100, 1)] + [round(q.margin * 100, 1) for q in res.quotes]
    st.subheader("시나리오 비교 (원)")
    st.dataframe(df.style.format("{:,.1f}", subset=pd.IndexSlice[["원가 대비 이윤율(%)"], :])
                 .format("{:,.0f}", subset=pd.IndexSlice[df.index.difference(["원가 대비 이윤율(%)"]), :]),
                 width="stretch")

    label = st.radio("자세히 볼 안", [q.request.label for q in res.quotes], horizontal=True)
    q = next(x for x in res.quotes if x.request.label == label)
    d = diff(base, q)
    team_txt = " · ".join(f"{r} {n}" for r, n in q.request.team.items())
    st.markdown(f"**{md_safe(q.request.label)}** — 기준안 대비 {d['합계(VAT 포함)']:+,}원 · {q.request.client} · "
                f"{q.request.weeks}주 · {sum(q.request.team.values())}명({team_txt})")
    st.caption(f"계산 기준: 가정값 {q.assumptions_version} ({q.assumptions_as_of})")
    for w in q.warnings:
        st.warning(w)
    alloc = pd.DataFrame(q.allocation).T.fillna(0).astype(int)
    alloc.index = [f"{i} (LLM 추정)" if i.startswith("신규:") else i for i in alloc.index]
    st.caption("단계 × 산출물별 공급가액 배분(원, 비중은 가정값)")
    st.dataframe(alloc.style.format("{:,.0f}"), width="stretch")
    with st.expander("하나씩 바꾸면? (민감도: 선택한 안 기준, VAT 포함)"):
        sens = pd.DataFrame(sensitivity(q.request))
        st.dataframe(sens.style.format({"총액(VAT 포함)": "{:,.0f}", "차이(VAT 포함)": "{:+,.0f}"}),
                     width="stretch", hide_index=True)
    st.download_button("엑셀로 내려받기 (초안)", to_xlsx(q, base),
                       file_name=f"견적_{q.request.client}_{q.request.weeks}주.xlsx",
                       mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

if res:
    with st.expander(f"에이전트 도구 호출 기록 ({res.steps}단계)"):
        for t in res.trace:
            st.code(t, language="json")
