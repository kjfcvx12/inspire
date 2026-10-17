import copy

import pytest

from quote import assumptions, engine


@pytest.fixture(autouse=True)
def fixed_assumptions():
    """테스트는 코드에 고정된 DEFAULTS로 돈다. 운영용 data/assumptions.json을 바꿔도 테스트가 깨지지 않는다."""
    engine.apply_assumptions(copy.deepcopy(assumptions.DEFAULTS))
    yield
    engine.apply_assumptions(copy.deepcopy(assumptions.DEFAULTS))


@pytest.fixture(autouse=True)
def isolated_history_db(tmp_path, monkeypatch):
    """이력 DB를 테스트마다 임시 경로로 돌린다(운영 data/quotes.db를 읽거나 만들지 않는다). 개별 시험이 따로 정하면 그 값이 우선한다."""
    monkeypatch.setenv("QUOTE_DB_PATH", str(tmp_path / "history_test.db"))
