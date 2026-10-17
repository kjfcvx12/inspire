"""Streamlit 화면용 작은 도우미. 모델 답변·금액을 st.write/st.caption에 그대로 넘기면 마크다운이 깨진다.
- '3~5일' 의 ~ 두 개가 취소선으로, '$0.01 ... $0.02' 의 $ 두 개가 수식으로 렌더링된다."""


def md_safe(text) -> str:
    """마크다운 특수문자(~ $)를 이스케이프해 글자 그대로 보이게 한다. None은 빈 문자열."""
    if text is None:
        return ""
    return str(text).replace("\\", "\\\\").replace("~", "\\~").replace("$", "\\$")
