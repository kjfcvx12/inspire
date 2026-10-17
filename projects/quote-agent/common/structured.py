"""구조화 출력 + 검증. LLM 응답을 pydantic 스키마로 받고, 실패하면 오류를 알려 다시 묻고, 끝내 안 되면 폴백한다.

규칙(발표용): 자유 텍스트를 정규식으로 파싱하지 않는다.
스키마가 계약이고, 계약을 못 지키면 '모른다'는 폴백으로 안전하게 내려간다.
방식: messages.parse(output_format=Model) — 강제 tool_choice는 Sonnet 5.5에서 400이라 쓰지 않는다.
"""
from dataclasses import dataclass
from typing import Any, Callable, Optional, Type, Union

from pydantic import BaseModel

from . import llm


@dataclass
class Structured:
    data: Optional[BaseModel]   # 검증된 스키마 인스턴스. 실패+폴백 없음이면 None
    mock: bool = False          # True면 API 결과가 아니라 폴백 값이다
    attempts: int = 0
    error: Optional[str] = None


def ask_structured(prompt: str, schema: Type[BaseModel], *, system: Optional[str] = None,
                   max_attempts: int = 2, fallback: Union[BaseModel, Callable[[str], BaseModel], None] = None,
                   tag: str = "structured", **kw) -> Structured:
    """prompt를 schema 형태로 받는다. 스키마 불일치는 오류 내용을 붙여 max_attempts까지 다시 묻는다."""
    def fall(err: str, attempts: int) -> Structured:
        fb = fallback(prompt) if callable(fallback) else fallback
        return Structured(data=fb, mock=True, attempts=attempts, error=err)

    note, last_err = "", "unknown"
    for attempt in range(1, max_attempts + 1):
        messages = [{"role": "user", "content": prompt + note}]
        try:
            resp = llm.parse(messages=messages, output_format=schema, system=system, tag=tag, **kw)
        except llm.LLMUnavailable as e:  # 호출 자체가 안 됨(재시도 소진·거절 포함): 다시 물어봐야 소용없다
            return fall(str(e), attempt)
        except ValueError as e:          # pydantic ValidationError / JSON 오류
            last_err = f"스키마 검증 실패: {str(e)[:200]}"
        else:
            parsed: Any = getattr(resp, "parsed_output", None)
            if parsed is not None:
                return Structured(data=parsed, attempts=attempt)
            last_err = "parsed_output 없음(스키마 불일치 또는 잘림)"
        note = f"\n\n[이전 응답이 요구한 스키마를 만족하지 않았습니다: {last_err}. 스키마에 정확히 맞게 다시 답하세요.]"
    return fall(last_err, max_attempts)
