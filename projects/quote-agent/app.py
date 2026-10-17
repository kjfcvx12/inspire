"""견적 에이전트 (Streamlit). 요청 문장 → 에이전트가 도구로 시나리오 계산 → 기준안(서울대 PI) 대비 비교.
단가·기준안은 공개 정보가 없어 가정값이다(사이드바에 표시). 견적은 담당자 검토 전 초안이다."""
import copy
from datetime import date

import pandas as pd
import streamlit as st

from common.ui import md_safe
from quote import agent, engine, history
from quote.assumptions_io import next_version, save_assumptions
from quote.document import quote_document
from quote.explain import explain
from quote.korean import annotate_won, to_korean
from quote.replay import load_cache, lookup
from quote.engine import (CLIENT_SCALE, DELIVERABLE_WEIGHT, MODULE_WEIGHT, RATES, QuoteRequest, assumption_label,
                          assumption_text, baseline_quote, calculate, diff, sensitivity)
from quote.examples import EXAMPLES
from quote.export import to_xlsx

st.set_page_config(page_title="견적 에이전트", layout="wide")
st.title("용역 견적 에이전트")
st.info("가정값 기반 초안이며 실제 견적이 아닙니다. 설명은 AI가 생성했고, 금액은 엔진이 계산합니다. "
        "대학명은 예시이고 단가·기준안은 공개 정보가 없어 가정한 값입니다. 담당자 검토 전에는 고객에게 보내지 마세요. "
        "금액 단위는 원, 공급가액은 부가세 별도, 합계는 부가세 포함입니다.")

def _on_pick():
    """예시를 고르면 입력창에 채우고 바로 실행한다(시연 중 타이핑을 줄인다)."""
    st.session_state["req_text"] = st.session_state["example"]
    st.session_state["autorun"] = True


def assumption_editor():
    """가정값을 화면에서 고치고, 검증을 통과하면 data/assumptions.json에 저장하고 실행 중인 엔진에 적용한다."""
    cfg = copy.deepcopy(engine._A)
    with st.expander("가정값 편집 (실제 값이 생기면 여기서 바꿉니다)"):
        if msg := st.session_state.pop("assump_msg", None):
            st.success(msg)
        with st.form("assumptions_form"):
            tables = {}
            for key, title, dynamic in (("rates", "월 단가(원)", False), ("module_weight", "단계 공수 비중", False),
                                        ("deliverable_weight", "산출물 공수 비중", False),
                                        ("client_scale", "대학 규모 계수(행 추가 가능)", True)):
                st.caption(title)
                df = pd.DataFrame({"이름": list(cfg[key]), "값": list(cfg[key].values())})
                tables[key] = st.data_editor(df, key=f"ed_{key}", hide_index=True,
                                             num_rows="dynamic" if dynamic else "fixed",
                                             disabled=False if dynamic else ["이름"])
            status = st.text_input("출처 표기", value=cfg["status"],
                                   help="예: '실제(서울대 견적서 2026-10)'. 화면과 견적서에 그대로 표시됩니다.")
            if st.form_submit_button("검증 후 저장하고 적용"):
                try:
                    new = copy.deepcopy(cfg)
                    for key, df in tables.items():
                        rows = {str(r["이름"]).strip(): r["값"] for _, r in df.iterrows() if str(r["이름"]).strip()}
                        if any(pd.isna(v) for v in rows.values()):
                            raise ValueError(f"{key}에 비어 있는 값이 있습니다")
                        new[key] = {k: (int(round(v)) if key == "rates" else float(v)) for k, v in rows.items()}
                    new.update(version=next_version(cfg["version"]), as_of=date.today().isoformat(),
                               status=status.strip() or cfg["status"])
                    save_assumptions(new)
                    engine.apply_assumptions(new)
                    st.session_state["assump_msg"] = (f"저장했습니다: 가정값 {new['version']}. 이후 견적부터 적용되고, "
                                                      "이미 만든 견적은 이전 버전 값으로 계산된 것입니다.")
                    st.rerun()
                except ValueError as e:
                    st.error(f"저장하지 않았습니다(기존 값 유지): {e}")


def run_request(text, use_ai, prefer_cache):
    """저장본 우선이면 예시 문장에 한해 저장본을 쓰고, API 장애로 mock이 됐을 때도 저장본이 있으면 대체한다."""
    hit = lookup(text, load_cache())
    st.session_state["replayed"] = False
    if hit and prefer_cache:
        st.session_state["replayed"] = True
        return hit
    res = agent.run(text, use_ai=use_ai)
    if res.mock and use_ai and hit:
        st.session_state["replayed"] = True
        return hit
    return res


with st.sidebar:
    st.subheader("가정값")
    st.caption(assumption_label() + " · 파일: data/assumptions.json")
    for title, table in (("월 단가(원)", RATES), ("단계 공수 비중", MODULE_WEIGHT),
                         ("산출물 공수 비중", DELIVERABLE_WEIGHT), ("대학 규모 계수", CLIENT_SCALE)):
        st.dataframe(pd.Series(table, name=title).to_frame(), width="stretch")
    st.caption(assumption_text())
    assumption_editor()
    use_ai = st.toggle("AI 해석 사용", value=True, help="끄면 요청 문장을 외부 AI로 보내지 않고 규칙 기반으로만 해석합니다(정확도 낮음).")
    prefer_cache = st.checkbox("시연 저장본 우선 사용 (네트워크 없이)",
                               help="예시 문장과 정확히 같을 때만 미리 저장한 실제 결과를 보여줍니다. API가 안 될 때도 같은 저장본으로 대체합니다.")
    st.radio("예시 요청 (누르면 바로 실행)", EXAMPLES, index=None, key="example", on_change=_on_pick)

# 입력창과 버튼을 폼으로 묶어, 타이핑만으로는 재실행되지 않게 한다(계산 중에 입력창을 건드려도 실행이 중단되지 않는다).
with st.form("request_form", border=False):
    text = st.text_area("견적 요청", key="req_text", height=90, placeholder="예: 고려대, 4개월, 6명, 상주 없음")
    clicked = st.form_submit_button("견적 만들기", type="primary")
if clicked and not text.strip():
    st.warning("요청 문장을 입력해 주세요.")
if (clicked or st.session_state.pop("autorun", False)) and text.strip():
    with st.spinner("에이전트가 견적을 계산하는 중..."):
        try:
            st.session_state["res"] = run_request(text.strip(), use_ai, prefer_cache)
        except Exception as e:   # 화면이 예외 덤프로 죽지 않게, 이유를 알리고 이전 결과는 지운다
            st.session_state.pop("res", None)
            st.error(f"견적을 만들지 못했습니다: {type(e).__name__}: {str(e)[:150]}")


def won_text(n: int) -> str:
    """'353,560,000원 (삼억 오천삼백오십육만 원)' 형태. 숫자와 한글을 함께 보여준다."""
    return f"{n:,}원 ({to_korean(n)} 원)"


def tab_summary(res, q, base):
    """숫자(공급가액·부가세·합계)를 먼저, 경고, 그 아래에 AI 설명 문장 순서로 보여준다."""
    d = diff(base, q)
    c1, c2, c3 = st.columns(3)
    c1.metric("공급가액 (VAT 별도)", f"{q.supply:,}원")
    c1.caption(f"{to_korean(q.supply)} 원")
    c2.metric("부가세", f"{q.vat:,}원")
    c2.caption(f"{to_korean(q.vat)} 원")
    c3.metric("합계 (VAT 포함)", f"{q.total:,}원", delta=f"기준안 대비 {d['합계(VAT 포함)']:+,}원", delta_color="off")
    c3.caption(f"{to_korean(q.total)} 원")
    for w in q.warnings:
        st.warning(w)
    st.markdown(md_safe(annotate_won(res.text)))
    st.caption("자세한 내용은 위 탭에서 볼 수 있습니다: 견적서(화면에서 바로 확인) · 비교 · 근거·민감도 · 조건 확인·수정")


def tab_sheet(q, base):
    """다운로드하지 않아도 화면에서 바로 보는 견적서."""
    doc = quote_document(q, base)
    with st.container(border=True):
        st.subheader(doc["제목"])
        st.caption(doc["고지"])
        left, right = st.columns(2)
        left.markdown(f"**수신** {md_safe(doc['수신'])}  \n**용역명** {doc['용역명']}  \n**기간** {doc['기간']}")
        right.markdown(f"**투입 인력** {doc['투입 인력']}  \n**범위** {doc['범위']}  \n**산출물** {doc['산출물']}")
        if doc["옵션"]:
            st.markdown("**옵션** " + ", ".join(doc["옵션"]))
        if doc["신규 항목(LLM 추정)"]:
            st.markdown("**신규 항목** :orange-badge[LLM 추정] " + md_safe("; ".join(doc["신규 항목(LLM 추정)"])))
        items = pd.DataFrame(doc["항목"]).rename(columns={"금액": "금액(원)", "한글": "한글 읽기"})
        st.dataframe(items.style.format({"금액(원)": "{:,.0f}"}), width="stretch", hide_index=True)
        st.markdown(f"**공급가액 (VAT 별도)** {won_text(doc['공급가액']['금액'])}  \n"
                    f"**부가세** {won_text(doc['부가세']['금액'])}")
        st.markdown(f"### {doc['일금']}  (₩{doc['합계']['금액']:,})")
        st.caption(doc["계산 기준"])
        for w in doc["경고"]:
            st.warning(w)
    b1, b2 = st.columns(2)
    b1.download_button("엑셀로 내려받기 (초안)", to_xlsx(q, base),
                       file_name=f"견적_{q.request.client}_{q.request.weeks}주.xlsx",
                       mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    if b2.button("이 안을 이력에 저장"):
        try:
            st.success(f"이력에 저장했습니다(번호 {history.save_quote(q)}). 내부용 기록이며 data/quotes.db에 남습니다.")
        except Exception as e:
            st.error(f"이력 저장 실패: {type(e).__name__}: {str(e)[:120]}")


def tab_compare(res, q, base):
    rows = {"기준안": base.lines}
    for x in res.quotes:
        rows[x.request.label] = x.lines
    df = pd.DataFrame(rows).fillna(0).astype(int)
    df.loc["공급가액(VAT 별도)"] = [base.supply] + [x.supply for x in res.quotes]
    df.loc["합계(VAT 포함)"] = [base.total] + [x.total for x in res.quotes]
    df.loc["필요 대비 투입 공수(%)"] = [round(base.capacity * 100)] + [round(x.capacity * 100) for x in res.quotes]
    df.loc["원가 대비 이윤율(%)"] = [round(base.margin * 100, 1)] + [round(x.margin * 100, 1) for x in res.quotes]
    st.caption("시나리오 비교 (원)")
    st.dataframe(df.style.format("{:,.1f}", subset=pd.IndexSlice[["원가 대비 이윤율(%)"], :])
                 .format("{:,.0f}", subset=pd.IndexSlice[df.index.difference(["원가 대비 이윤율(%)"]), :]),
                 width="stretch")
    totals = [("기준안", base.total)] + [(x.request.label, x.total) for x in res.quotes]
    st.caption("합계(VAT 포함) 한글 읽기")
    st.dataframe(pd.DataFrame({"안": [n for n, _ in totals], "합계(원)": [t for _, t in totals],
                               "한글 읽기": [f"{to_korean(t)} 원" for _, t in totals]})
                 .style.format({"합계(원)": "{:,.0f}"}), width="stretch", hide_index=True)
    alloc = pd.DataFrame(q.allocation).T.fillna(0).astype(int)
    alloc.index = [f"{i} (LLM 추정)" if i.startswith("신규:") else i for i in alloc.index]
    st.caption(f"'{q.request.label}'의 단계 × 산출물별 공급가액 배분(원, 비중은 가정값)")
    st.dataframe(alloc.style.format("{:,.0f}"), width="stretch")


def tab_basis(q):
    st.caption("이 금액은 어떻게 나왔나? (계산 근거)")
    ex = pd.DataFrame(explain(q))
    ex["한글 읽기"] = [f"{to_korean(int(a))} 원" if pd.notna(a) else "" for a in ex["금액"]]
    st.dataframe(ex.style.format({"금액": "{:,.0f}"}, na_rep="-"), width="stretch", hide_index=True)
    st.caption("하나씩 바꾸면? (민감도: 선택한 안 기준, VAT 포함)")
    sens = pd.DataFrame(sensitivity(q.request))
    st.dataframe(sens.style.format({"총액(VAT 포함)": "{:,.0f}", "차이(VAT 포함)": "{:+,.0f}"}),
                 width="stretch", hide_index=True)


def tab_edit(res):
    first = res.quotes[0].request
    st.caption("에이전트가 요청을 이렇게 이해했습니다. 고쳐서 다시 계산할 수 있습니다.")
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
                label = agent.unique_label("수정 확인안", [x.request.label for x in res.quotes])
                req = first.model_copy(update={
                    "label": label, "weeks": int(weeks), "duration_months": None, "discount_pct": discount,
                    "team": {r: n for r, n in team.items() if n}, "modules": modules, "deliverables": delivs,
                    "onsite": onsite, "english_deliverables": english})
                res.quotes.append(calculate(QuoteRequest(**req.model_dump())))
                st.session_state["pending_view"] = label    # 다시 그릴 때 새 안을 보고 있는 안으로 선택한다
                st.rerun()
            except ValueError as e:
                st.error(f"조건을 확인하세요: {str(e)[:200]}")


def tab_history():
    st.caption("내부용 — 고객에게 가는 견적서에는 넣지 않습니다.")
    try:
        hist = history.list_quotes(20)
    except Exception as e:
        hist, _ = [], st.error(f"이력을 읽지 못했습니다: {type(e).__name__}: {str(e)[:120]}")
    if not hist:
        st.caption("아직 저장한 견적이 없습니다. '견적서' 탭에서 '이 안을 이력에 저장'을 누르면 쌓입니다.")
        return
    st.dataframe(pd.DataFrame(hist), width="stretch", hide_index=True)
    with st.form("outcome_form"):
        st.caption("수주 결과를 기록하면, 쌓인 데이터로 비슷한 사례를 참고하는 기능의 기반이 됩니다. 탈락·보류도 함께 기록하세요.")
        oc1, oc2, oc3 = st.columns(3)
        qid = oc1.selectbox("견적 번호", [h["id"] for h in hist])
        outcome = oc2.selectbox("결과", ["수주", "탈락", "보류"])
        final = oc3.number_input("최종 계약금액(원, 모르면 0)", 0, 10_000_000_000, 0, step=1_000_000)
        if st.form_submit_button("결과 기록"):
            try:
                history.set_outcome(int(qid), outcome, int(final) or None)
                st.success("기록했습니다.")
            except ValueError as e:
                st.error(f"기록하지 못했습니다: {e}")


def tab_trace(res):
    st.caption(f"에이전트가 도구를 호출한 기록 ({res.steps}단계). 금액은 모두 엔진이 계산한 값입니다.")
    for t in res.trace:
        st.code(t, language="json")


res = st.session_state.get("res")
base = baseline_quote()
if not res:
    st.caption("요청을 쓰고 '견적 만들기'를 누르거나, 사이드바의 예시를 누르세요. 결과는 아래 탭으로 나뉘어 나옵니다.")
else:
    if st.session_state.get("replayed"):
        st.info("미리 저장해 둔 시연 결과입니다. 실시간 계산이 아니며, 저장 당시의 가정값 버전으로 계산된 값입니다.")
    elif res.mock:
        st.warning("AI를 쓰지 않았거나 쓸 수 없어 규칙 기반 mock으로 동작했습니다. 해석 정확도가 낮습니다.")
    if res.unverified:
        st.error("설명 속 다음 금액은 엔진 계산 결과에 없습니다. '견적서' 탭의 숫자를 기준으로 보세요: " + ", ".join(res.unverified))
    if not res.quotes:
        st.markdown(md_safe(annotate_won(res.text)))
        t_hist, t_trace = st.tabs(["이력", "기록"])
        with t_hist:
            tab_history()
        with t_trace:
            tab_trace(res)
    else:
        if "pending_view" in st.session_state:
            st.session_state["view_label"] = st.session_state.pop("pending_view")
        labels = [x.request.label for x in res.quotes]
        label = st.radio("보고 있는 안", labels, horizontal=True, key="view_label")
        q = next(x for x in res.quotes if x.request.label == label)
        t_sum, t_sheet, t_cmp, t_basis, t_edit, t_hist, t_trace = st.tabs(
            ["요약", "견적서", "비교", "근거·민감도", "조건 확인·수정", "이력", "기록"])
        with t_sum:
            tab_summary(res, q, base)
        with t_sheet:
            tab_sheet(q, base)
        with t_cmp:
            tab_compare(res, q, base)
        with t_basis:
            tab_basis(q)
        with t_edit:
            tab_edit(res)
        with t_hist:
            tab_history()
        with t_trace:
            tab_trace(res)
