"""견적 에이전트 (Streamlit). 요청 문장 → 에이전트가 도구로 시나리오 계산 → 기준안(서울대 PI) 대비 비교.
단가·기준안은 공개 정보가 없어 가정값이다(사이드바에 표시)."""
import pandas as pd
import streamlit as st

from common.ui import md_safe
from quote import agent
from quote.engine import CLIENT_SCALE, MODULE_WEIGHT, RATES, baseline_quote, diff

st.set_page_config(page_title="견적 에이전트", layout="wide")
st.title("용역 견적 에이전트")
st.caption("기준안: 서울대학교 연구행정시스템 PI 용역(가정 단가). 금액은 엔진이 계산하고, 에이전트는 시나리오와 설명을 맡습니다.")

EXAMPLES = ["고려대에서 같은 용역을 3개월에 5명으로 요청했어. 견적 보여줘",
            "연세대, 20주, 상주 필수, 영문 산출물 포함, 종료 후 3개월 지원, 인원은 기준안과 동일하게",
            "카이스트 8주 안에 끝내달라는데 PM 1명, 분석가 1명으로 가능한 견적과 대안"]
with st.sidebar:
    st.subheader("가정값 (공개 정보 없음)")
    st.write("월 단가(원)", RATES)
    st.write("모듈 공수 비중", MODULE_WEIGHT)
    st.write("대학 규모 계수", CLIENT_SCALE)
    st.caption("간접경비 15% · 이윤 10% · VAT 10%. 기준안 16주, PM1·수석1·컨설턴트2·분석가2.")
    pick = st.radio("예시 요청", EXAMPLES, index=None)

text = st.text_area("견적 요청", value=pick or "", height=90, placeholder="예: 고려대, 4개월, 6명, 상주 없음")
if st.button("견적 만들기", type="primary", disabled=not text.strip()):
    with st.spinner("에이전트가 견적을 계산하는 중..."):
        st.session_state["res"] = agent.run(text.strip())

res = st.session_state.get("res")
base = baseline_quote()
if res:
    if res.mock:
        st.warning("API를 쓸 수 없어 규칙 기반 mock으로 동작했습니다. 해석 정확도가 낮습니다.")
    st.markdown(md_safe(res.text))
    if res.quotes:
        rows = {"기준안": base.lines}
        for q in res.quotes:
            rows[q.request.label] = q.lines
        df = pd.DataFrame(rows).fillna(0).astype(int)
        df.loc["공급가액"] = [base.supply] + [q.supply for q in res.quotes]
        df.loc["합계(VAT 포함)"] = [base.total] + [q.total for q in res.quotes]
        df.loc["필요 대비 투입 공수(%)"] = [round(base.capacity * 100)] + [round(q.capacity * 100) for q in res.quotes]
        st.subheader("시나리오 비교 (원)")
        st.dataframe(df.style.format("{:,.0f}"), use_container_width=True)
        for q in res.quotes:
            d = diff(base, q)
            st.markdown(f"**{md_safe(q.request.label)}** — 기준안 대비 {d['합계(VAT 포함)']:+,}원 · "
                        f"{q.request.client} · {q.request.weeks}주 · {sum(q.request.team.values())}명")
            for w in q.warnings:
                st.warning(w)
    with st.expander(f"에이전트 도구 호출 기록 ({res.steps}단계)"):
        for t in res.trace:
            st.code(t, language="json")
