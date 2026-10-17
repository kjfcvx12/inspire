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
