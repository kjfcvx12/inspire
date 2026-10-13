"""Claude 호출 공통 래퍼. 재시도(tenacity) · usage 기록 · 프롬프트 캐싱 · mock 폴백 · 스트리밍을 한곳에 둔다.

규칙(발표용): 호출 코드는 anthropic을 직접 부르지 않고 이 모듈을 거친다.
- 재시도: 429/5xx/연결 오류만 지수 백오프로 재시도. 인증·잘못된 요청은 즉시 포기(재시도해도 소용없음).
- 폴백: 끝내 실패하면 LLMUnavailable. `ask()`/`stream_text()`는 예외 대신 mock 응답(Reply.mock=True)을 돌려준다.
- 비용: 성공한 호출은 모두 usage_log.record()로 기록한다.
- 캐싱: system을 cache_control 블록으로 보낸다(접두 512토큰 미만이면 API가 조용히 캐시하지 않는다).
- 모델: CLAUDE_MODEL 환경변수로 교체 가능. Sonnet 5.5는 강제 tool_choice(any/tool)가 400이므로 쓰지 않는다.
"""
import os
from dataclasses import dataclass, field
from typing import Callable, Iterator, Optional, Union

import anthropic
from tenacity import Retrying, retry_if_exception, stop_after_attempt, wait_exponential_jitter

from . import usage_log

MODEL = os.environ.get("CLAUDE_MODEL", "claude-sonnet-5-5")
MAX_ATTEMPTS = 3   # 최초 1회 + 재시도 2회
WAIT_BASE = 1.0    # 초. 테스트에서는 0으로 내린다
WAIT_MAX = 8.0

Fallback = Union[str, Callable[[str], str], None]


class LLMUnavailable(Exception):
    """재시도 후에도 실패했거나 재시도해도 소용없는 오류(키 없음 등). 호출자는 mock 폴백을 쓴다."""


class LLMRefusal(LLMUnavailable):
    """모델이 안전상 이유로 응답을 거절했다(stop_reason == "refusal")."""


@dataclass
class Reply:
    text: str
    mock: bool = False             # True면 API 응답이 아니라 폴백 문구다
    error: Optional[str] = None
    stop_reason: Optional[str] = None
    truncated: bool = False        # max_tokens로 잘렸는지
    usage: dict = field(default_factory=dict)


_client = None


def get_client():
    """재시도는 이 모듈이 맡으므로 SDK 자체 재시도는 끈다(이중 재시도 방지)."""
    global _client
    if _client is None:
        try:
            from dotenv import load_dotenv
            load_dotenv()
        except ImportError:
            pass
        _client = anthropic.Anthropic(max_retries=0)
    return _client


def is_retryable(exc: BaseException) -> bool:
    if isinstance(exc, (anthropic.APIConnectionError, anthropic.RateLimitError)):
        return True
    if isinstance(exc, anthropic.APIStatusError):
        return exc.status_code in (408, 409) or exc.status_code >= 500
    return False


def _retrying(extra_stop: Optional[Callable[[], bool]] = None) -> Retrying:
    def should_retry(exc):
        return is_retryable(exc) and not (extra_stop and extra_stop())
    return Retrying(stop=stop_after_attempt(MAX_ATTEMPTS),
                    wait=wait_exponential_jitter(multiplier=WAIT_BASE, max=WAIT_MAX, jitter=0.5),
                    retry=retry_if_exception(should_retry), reraise=True)


def _system(system, cache: bool):
    if not system:
        return None
    if cache and isinstance(system, str):
        return [{"type": "text", "text": system, "cache_control": {"type": "ephemeral"}}]
    return system


def _params(messages, model, max_tokens, system, tools, cache, effort, extra) -> dict:
    p = {"model": model or MODEL, "max_tokens": max_tokens, "messages": messages, **extra}
    s = _system(system, cache)
    if s:
        p["system"] = s
    if tools:
        p["tools"] = tools
    if effort:
        p["output_config"] = {**p.get("output_config", {}), "effort": effort}
    return p


def _invoke(method: str, params: dict, tag: str):
    """messages.<method>(**params)를 재시도와 함께 호출하고 usage를 기록한다."""
    try:
        for attempt in _retrying():
            with attempt:
                resp = getattr(get_client().messages, method)(**params)
    except ValueError:
        raise  # 스키마/인자 오류(pydantic ValidationError 포함)는 호출자가 처리한다
    except Exception as e:
        raise LLMUnavailable(f"{type(e).__name__}: {str(e)[:200]}") from e
    usage_log.record(params["model"], resp.usage, tag=tag, stop_reason=resp.stop_reason)
    if resp.stop_reason == "refusal":
        raise LLMRefusal("모델이 응답을 거절했습니다(refusal)")
    return resp


def create(*, messages, model=None, max_tokens=2048, system=None, tools=None, tag="",
           cache=True, effort=None, **extra):
    """재시도 + 기록이 붙은 messages.create. 실패하면 LLMUnavailable."""
    return _invoke("create", _params(messages, model, max_tokens, system, tools, cache, effort, extra), tag)


def parse(*, messages, output_format, model=None, max_tokens=2048, system=None, tag="", cache=True, **extra):
    """재시도 + 기록이 붙은 messages.parse(구조화 출력). 스키마 불일치는 ValueError 계열로 올라온다."""
    p = _params(messages, model, max_tokens, system, None, cache, None, extra)
    p["output_format"] = output_format
    return _invoke("parse", p, tag)


def text_of(resp) -> str:
    return "".join(b.text for b in resp.content if getattr(b, "type", None) == "text")


def _as_messages(prompt):
    return prompt if isinstance(prompt, list) else [{"role": "user", "content": prompt}]


def _fallback_text(fallback: Fallback, prompt, err: str) -> str:
    base = str(prompt) if not isinstance(prompt, list) else str(prompt[-1].get("content", ""))
    if callable(fallback):
        return fallback(base)
    if isinstance(fallback, str):
        return fallback
    return f"(mock) API를 사용할 수 없어 예시 응답을 보여줍니다. 원인: {err}"


def ask(prompt, *, system=None, fallback: Fallback = None, tag="", **kw) -> Reply:
    """한 번 묻고 Reply를 받는다. API가 안 되면 예외 대신 mock Reply를 돌려준다."""
    try:
        r = create(messages=_as_messages(prompt), system=system, tag=tag, **kw)
    except LLMUnavailable as e:
        return Reply(text=_fallback_text(fallback, prompt, str(e)), mock=True, error=str(e))
    u = r.usage
    return Reply(text=text_of(r), stop_reason=r.stop_reason, truncated=r.stop_reason == "max_tokens",
                 usage={"input": getattr(u, "input_tokens", 0), "output": getattr(u, "output_tokens", 0),
                        "cache_read": getattr(u, "cache_read_input_tokens", 0) or 0})


def stream_text(prompt, *, system=None, fallback: Fallback = None, tag="", model=None, max_tokens=2048,
                cache=True, effort=None, **extra) -> Iterator[str]:
    """텍스트 조각을 흘려보낸다. Streamlit: st.write_stream(llm.stream_text(...)).
    첫 조각 전의 일시 오류만 재시도한다(이미 내보낸 글자는 되돌릴 수 없다)."""
    params = _params(_as_messages(prompt), model, max_tokens, system, None, cache, effort, extra)
    state = {"emitted": False}
    final = None
    try:
        for attempt in _retrying(extra_stop=lambda: state["emitted"]):
            with attempt:
                with get_client().messages.stream(**params) as s:
                    for chunk in s.text_stream:
                        state["emitted"] = True
                        yield chunk
                    final = s.get_final_message()
    except Exception as e:
        msg = f"{type(e).__name__}: {str(e)[:200]}"
        if state["emitted"]:
            yield f"\n\n(⚠ 응답이 중간에 끊겼습니다: {msg})"
        else:
            yield _fallback_text(fallback, prompt, msg)
        return
    if final is not None:
        usage_log.record(params["model"], final.usage, tag=tag, stop_reason=final.stop_reason)
