"""금액을 한글 읽기로 바꾼다(353,560,000 → '삼억 오천삼백오십육만'). 화면에서 숫자와 한글을 함께 보여주기 위한 표시용이다."""
import re

_DIGITS = "영일이삼사오육칠팔구"
_SMALL = ["", "십", "백", "천"]
_BIG = ["", "만", "억", "조", "경"]
_AMOUNT = re.compile(r"(?<![\d,.])(-?)(\d{1,3}(?:,\d{3})+|\d{5,})\s?원(?!\()")
MIN_ANNOTATE = 10_000   # 만 원 미만에는 읽기를 붙이지 않는다


def _group(n: int) -> str:
    """0 < n < 10000을 읽는다. 십·백·천 앞의 '일'은 생략한다(1,141 → 천백사십일)."""
    out = ""
    for pos, ch in enumerate(str(n).zfill(4)):
        d, unit = int(ch), _SMALL[3 - pos]
        if d == 0:
            continue
        out += unit if d == 1 and unit else _DIGITS[d] + unit
    return out


def to_korean(n: int) -> str:
    """정수를 한글 읽기로 바꾼다. 0은 '영', 음수는 '마이너스'를 붙인다."""
    n = int(n)
    if n == 0:
        return _DIGITS[0]
    if n < 0:
        return "마이너스 " + to_korean(-n)
    parts, i = [], 0
    while n:
        n, g = divmod(n, 10_000)
        if g:
            parts.append(_group(g) + _BIG[i])
        i += 1
    return " ".join(reversed(parts))


def annotate_won(text: str) -> str:
    """문장 속 'N원' 금액 뒤에 한글 읽기를 괄호로 붙인다. 이미 붙어 있거나 만 원 미만이면 그대로 둔다."""
    def repl(m):
        n = int(m.group(2).replace(",", ""))
        if n < MIN_ANNOTATE:
            return m.group(0)
        return f"{m.group(0)}({'마이너스 ' if m.group(1) else ''}{to_korean(n)} 원)"
    return _AMOUNT.sub(repl, text)
