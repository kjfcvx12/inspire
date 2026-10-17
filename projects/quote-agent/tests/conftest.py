import copy

import pytest

from quote import assumptions, engine


@pytest.fixture(autouse=True)
def fixed_assumptions():
    """테스트는 코드에 고정된 DEFAULTS로 돈다. 운영용 data/assumptions.json을 바꿔도 테스트가 깨지지 않는다."""
    engine.apply_assumptions(copy.deepcopy(assumptions.DEFAULTS))
    yield
    engine.apply_assumptions(copy.deepcopy(assumptions.DEFAULTS))
