"""화면 흐름(AppTest). 입력창과 버튼은 폼이라 제출할 때만 실행되고, 결과는 다른 위젯을 건드려도 유지된다.
주의: 폼 안의 입력은 제출할 때 전달되므로 set_value와 click 사이에 run()을 끼우지 않는다."""
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

from quote import agent

APP = str(Path(__file__).resolve().parents[1] / "app.py")


@pytest.fixture
def app(monkeypatch, tmp_path):
    monkeypatch.setenv("QUOTE_DB_PATH", str(tmp_path / "q.db"))
    calls = []
    real = agent.run
    monkeypatch.setattr(agent, "run", lambda text, **kw: (calls.append(text), real(text, **kw))[1])
    at = AppTest.from_file(APP, default_timeout=60).run()
    at.toggle[0].set_value(False).run()        # AI 끄기: 외부 호출 없이 규칙 기반으로 돈다
    return at, calls


def _submit(at):
    [b for b in at.button if b.label == "견적 만들기"][0].click().run()


def test_submit_runs_once_and_shows_tabs(app):
    at, calls = app
    at.text_area[0].set_value("고대 3개월 5명")
    _submit(at)
    assert len(calls) == 1 and len(at.tabs) == 7 and not at.exception


def test_result_survives_other_widget_changes(app):
    at, calls = app
    at.text_area[0].set_value("고대 3개월 5명")
    _submit(at)
    at.toggle[0].set_value(False).run()
    assert len(at.tabs) == 7 and len(calls) == 1


def test_blank_submit_warns_and_does_not_run(app):
    at, calls = app
    at.text_area[0].set_value("   ")
    _submit(at)
    assert calls == [] and any("입력" in w.value for w in at.warning)


def test_example_click_runs_immediately(app):
    at, calls = app
    at.radio[0].set_value(at.radio[0].options[0]).run()
    assert len(calls) == 1 and len(at.tabs) == 7


def _has_metric(el):
    """열 묶음 안에 있는 메트릭까지 찾는다."""
    return el.type == "metric" or any(_has_metric(c) for c in getattr(el, "children", {}).values())


def test_summary_tab_shows_numbers_before_the_ai_text(app):
    at, calls = app
    at.text_area[0].set_value("고대 3개월 5명")
    _submit(at)
    kids = [c for _, c in sorted(at.tabs[0].children.items())]
    first_metric = next(i for i, c in enumerate(kids) if _has_metric(c))
    ai_text = next(i for i, c in enumerate(kids) if c.type == "markdown" and "(mock)" in str(c.value))
    assert first_metric < ai_text and ai_text < len(kids) - 1   # 숫자 → (경고) → AI 문장 → 안내 순서


def _example_radio(at):
    """결과가 나온 뒤에는 '보고 있는 안' 라디오가 앞에 오므로 순서가 아니라 이름으로 고른다."""
    return next(r for r in at.radio if r.label.startswith("예시 요청"))


def test_same_example_can_be_run_twice(app):
    """라디오는 이미 선택된 항목을 다시 눌러도 변화가 없으므로, 실행 뒤 선택을 비워 두 번째 클릭도 실행되게 한다."""
    at, calls = app
    first = _example_radio(at).options[0]
    _example_radio(at).set_value(first).run()
    _example_radio(at).set_value(first).run()
    assert calls == [first, first]


def test_example_runs_with_its_own_text_not_the_form_value(app):
    """폼 입력값이 비어 있어도(브라우저의 폼은 제출 전 값을 서버에 보내지 않는다) 예시 문장 자체로 실행한다."""
    at, calls = app
    at.text_area[0].set_value("")
    first = _example_radio(at).options[0]
    _example_radio(at).set_value(first).run()
    assert calls == [first]


def test_replay_banner_says_when_assumptions_changed_since_it_was_saved(app, monkeypatch):
    """저장본은 저장 당시의 가정값으로 계산된 숫자다. 가정값 버전이 바뀌었으면 안내에 그 차이를 알려야 한다."""
    from quote import engine
    from quote.examples import EXAMPLES
    at, calls = app
    at.checkbox[0].set_value(True)
    monkeypatch.setitem(engine._A, "version", "v9")
    at.text_area[0].set_value(EXAMPLES[0])
    _submit(at)
    banners = [i.value for i in at.info if "저장해 둔" in i.value]
    assert banners and "v9" in banners[0] and "v1" in banners[0]
    assert calls == []                                   # 저장본이라 에이전트(API)를 부르지 않았다


def test_sidebar_puts_examples_and_switches_before_the_long_assumption_tables(app):
    """사이드바가 길어 예시까지 내려가지 못하던 문제: 예시·스위치를 맨 위에, 가정값 표는 접힌 영역 안에 둔다."""
    at, _ = app
    kinds = [c.type for _, c in sorted(at.sidebar.children.items())]
    assert kinds.index("radio") < kinds.index("expander")
    assert kinds.index("toggle") < kinds.index("expander")
    top_level_tables = [k for k in kinds if k == "arrow_data_frame"]
    assert top_level_tables == []                        # 표 4개는 접힌 영역 안으로 들어갔다


def test_demo_features_can_be_switched_off_for_real_service(monkeypatch, tmp_path):
    """QUOTE_DEMO_MODE=0이면 예시 요청과 '시연 저장본' 체크박스가 사라지고, 예시 문장을 그대로 넣어도 저장본을 쓰지 않는다."""
    from quote.examples import EXAMPLES
    monkeypatch.setenv("QUOTE_DB_PATH", str(tmp_path / "q.db"))
    monkeypatch.setenv("QUOTE_DEMO_MODE", "0")
    calls = []
    real = agent.run
    monkeypatch.setattr(agent, "run", lambda text, **kw: (calls.append(text), real(text, **kw))[1])
    at = AppTest.from_file(APP, default_timeout=60).run()
    assert not any(r.label.startswith("예시 요청") for r in at.radio)
    assert not any("시연 저장본" in c.label for c in at.checkbox)
    at.toggle[0].set_value(False).run()                       # AI 끄기(외부 호출 없이)
    at.text_area[0].set_value(EXAMPLES[0])
    _submit(at)
    assert len(calls) == 1 and not any("저장해 둔" in i.value for i in at.info)    # 예시 문장이어도 저장본을 쓰지 않고 실제 계산


def _tab_labels(at):
    return [t.label for t in at.tabs]


def test_log_tab_is_hidden_when_there_is_no_reason_to_show_it(app):
    """정상 결과(저장본 경로: mock 아님, 미검증 금액 없음)에서는 개발자용 '기록' 탭을 보이지 않는다."""
    from quote.examples import EXAMPLES
    at, calls = app
    at.checkbox[0].set_value(True)
    at.text_area[0].set_value(EXAMPLES[0])
    _submit(at)
    assert "기록" not in _tab_labels(at) and len(at.tabs) == 6


def test_log_tab_appears_when_there_is_a_reason(app):
    """AI 없이 규칙 기반(mock)으로 동작했으면 이유를 확인할 수 있게 '기록' 탭을 보인다."""
    at, calls = app
    at.text_area[0].set_value("고대 3개월 5명")
    _submit(at)
    assert "기록" in _tab_labels(at)


def test_log_tab_can_be_forced_on(monkeypatch, app):
    from quote.examples import EXAMPLES
    at, calls = app
    monkeypatch.setenv("QUOTE_SHOW_LOG", "1")
    at.checkbox[0].set_value(True)
    at.text_area[0].set_value(EXAMPLES[0])
    _submit(at)
    assert "기록" in _tab_labels(at)


def _request_expander(at):
    return next(e for e in at.expander if "요청" in e.label)


def test_request_area_is_open_at_first_and_collapses_once_a_result_exists(app):
    """결과가 나오면 입력 영역을 접어, 작은 화면에서도 숫자가 맨 위에 보이게 한다."""
    at, calls = app
    assert _request_expander(at).proto.expanded is True
    at.text_area[0].set_value("고대 3개월 5명")
    _submit(at)
    assert len(calls) == 1 and _request_expander(at).proto.expanded is False


def test_top_banner_is_one_compact_message(app):
    at, _ = app
    assert len(at.info[0].value) <= 90 and "실제 견적이 아닙니다" in at.info[0].value


def test_request_area_is_a_fresh_collapsed_element_for_every_new_result(app):
    """사용자가 펼쳐 둔 입력 영역이 다음 결과에서도 남지 않도록, 요청마다 다른 요소(라벨)로 그린다."""
    at, calls = app
    at.text_area[0].set_value("고대 3개월 5명")
    _submit(at)
    first = _request_expander(at).label
    at.text_area[0].set_value("연대 20주")
    _submit(at)
    second = _request_expander(at)
    assert len(calls) == 2 and second.label != first and second.proto.expanded is False


def _edit_and_recalc(at, **changes):
    for label, value in changes.items():
        next(w for w in list(at.number_input) + list(at.multiselect) if w.label == label).set_value(value)
    [b for b in at.button if b.label == "이 조건으로 다시 계산"][0].click().run()


def _first_result(app):
    at, calls = app
    at.text_area[0].set_value("고대 3개월 5명")
    _submit(at)
    return at


def test_edit_with_zero_people_explains_in_plain_korean(app):
    at = _first_result(app)
    _edit_and_recalc(at, **{"PM 인원": 0, "수석컨설턴트 인원": 0, "컨설턴트 인원": 0, "분석가 인원": 0})
    msgs = " ".join(e.value for e in at.error)
    assert "1명 이상" in msgs and "validation" not in msgs.lower() and "Value error" not in msgs


def test_edit_with_no_stage_or_deliverable_explains_in_plain_korean(app):
    at = _first_result(app)
    _edit_and_recalc(at, **{"단계": [], "산출물": []})
    msgs = " ".join(e.value for e in at.error)
    assert "단계를 하나 이상" in msgs and "산출물을 하나 이상" in msgs and "validation" not in msgs.lower()


def test_valid_edit_still_adds_a_scenario(app):
    at = _first_result(app)
    _edit_and_recalc(at, **{"기간(주)": 14})
    assert not at.error and any("수정 확인안" in str(o) for r in at.radio for o in r.options)
