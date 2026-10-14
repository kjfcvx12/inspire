"""common.ui.md_safe: 모델 답변의 ~ · $ 가 마크다운으로 해석되지 않게 이스케이프한다."""
from starters.common.ui import md_safe

BS = "\\"  # 역슬래시 한 글자


def test_tilde_pair_not_strikethrough():
    assert md_safe("기본 2~3일, 제주 3~5일") == f"기본 2{BS}~3일, 제주 3{BS}~5일"


def test_dollar_pair_not_math():
    assert md_safe("≈ $0.0047 · 누적 $0.0047") == f"≈ {BS}$0.0047 · 누적 {BS}$0.0047"


def test_none_and_non_str():
    assert md_safe(None) == ""
    assert md_safe(12) == "12"


def test_existing_backslash_is_doubled_so_it_cannot_cancel_the_escape():
    assert md_safe(f"a{BS}~") == f"a{BS}{BS}{BS}~"
