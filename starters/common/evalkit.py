"""골든셋 평가. 발표에 쓰는 정확도·통과율을 '재현 가능한 스크립트'로 만든다.

골든 파일(JSONL, 한 줄 한 케이스, `#`로 시작하는 줄과 빈 줄은 무시):
  {"id": "q1", "input": "환불 기한은?", "expect": {"contains": ["7일"]}, "tags": ["policy"]}
input: 문자열/숫자면 fn(input), dict면 fn(**input), list면 fn(*input).
expect 키(모두 만족해야 통과, 문자열 비교는 대소문자 무시):
  key        출력이 dict/객체일 때 먼저 이 키로 값을 꺼낸다(예: "r2")
  contains   모든 문자열이 포함 / not_contains  하나도 포함하지 않음
  regex      정규식이 검색됨        / equals   값이 같음 / any_of  후보 중 하나와 같음
  range      [lo, hi] 안에 있음      / approx   [값, 허용오차]
  judge      채점 기준 문장 → LLM 판정(judge 함수가 있을 때만. 없으면 '건너뜀'이며 통과율에서 제외)
"""
import json
import re
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

Judge = Callable[[Any, str, dict], Tuple[bool, str]]


@dataclass
class Case:
    id: str
    input: Any
    expect: Dict[str, Any]
    tags: List[str] = field(default_factory=list)


@dataclass
class Result:
    id: str
    status: str                  # pass | fail | error | skipped
    failures: List[str] = field(default_factory=list)
    output: str = ""
    seconds: float = 0.0
    tags: List[str] = field(default_factory=list)


@dataclass
class Report:
    results: List[Result]

    @property
    def graded(self) -> List[Result]:
        return [r for r in self.results if r.status != "skipped"]

    @property
    def passed(self) -> int:
        return sum(r.status == "pass" for r in self.results)

    @property
    def rate(self) -> float:
        g = self.graded
        return self.passed / len(g) if g else 0.0


def load_golden(path) -> List[Case]:
    cases, seen = [], set()
    for n, line in enumerate(Path(path).read_text(encoding="utf-8").splitlines(), 1):
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        try:
            row = json.loads(line)
        except ValueError as e:
            raise ValueError(f"{path}:{n} JSON 오류: {e}") from e
        if "input" not in row or not isinstance(row.get("expect"), dict):
            raise ValueError(f"{path}:{n} 'input'과 dict 형태의 'expect'가 필요합니다")
        cid = str(row.get("id", f"case{len(cases) + 1}"))
        if cid in seen:
            raise ValueError(f"{path}:{n} id 중복: {cid}")
        seen.add(cid)
        cases.append(Case(cid, row["input"], row["expect"], list(row.get("tags", []))))
    return cases


def _pick(output: Any, key: Optional[str]) -> Any:
    if key is None:
        return output
    if isinstance(output, dict):
        return output[key]
    return getattr(output, key)


def check(output: Any, expect: dict) -> List[str]:
    """실패 사유 목록. 비어 있으면 통과. judge는 여기서 다루지 않는다."""
    try:
        value = _pick(output, expect.get("key"))
    except (KeyError, AttributeError):
        return [f"출력에 key '{expect.get('key')}' 없음"]
    text = str(value).casefold()
    fails = []
    for s in expect.get("contains", []):
        if str(s).casefold() not in text:
            fails.append(f"contains 실패: {s!r}")
    for s in expect.get("not_contains", []):
        if str(s).casefold() in text:
            fails.append(f"not_contains 실패: {s!r}")
    if "regex" in expect and not re.search(expect["regex"], str(value), re.IGNORECASE):
        fails.append(f"regex 실패: {expect['regex']!r}")
    if "equals" in expect and str(value).casefold() != str(expect["equals"]).casefold():
        fails.append(f"equals 실패: {value!r} != {expect['equals']!r}")
    if "any_of" in expect and text not in [str(x).casefold() for x in expect["any_of"]]:
        fails.append(f"any_of 실패: {value!r}")
    if "range" in expect or "approx" in expect:
        try:
            num = float(value)
        except (TypeError, ValueError):
            return fails + [f"숫자가 아님: {value!r}"]
        if "range" in expect:
            lo, hi = expect["range"]
            if not lo <= num <= hi:
                fails.append(f"range 실패: {num} not in [{lo}, {hi}]")
        if "approx" in expect:
            target, tol = expect["approx"]
            if abs(num - target) > tol:
                fails.append(f"approx 실패: {num} vs {target}±{tol}")
    return fails


def _call(fn: Callable, inp: Any) -> Any:
    if isinstance(inp, dict):
        return fn(**inp)
    if isinstance(inp, list):
        return fn(*inp)
    return fn(inp)


def run_eval(fn: Callable, cases: List[Case], judge: Optional[Judge] = None) -> Report:
    results = []
    for c in cases:
        t0 = time.perf_counter()
        try:
            out = _call(fn, c.input)
        except Exception as e:  # 한 케이스의 예외가 전체 평가를 멈추지 않게 한다
            results.append(Result(c.id, "error", [f"{type(e).__name__}: {str(e)[:150]}"], tags=c.tags,
                                  seconds=time.perf_counter() - t0))
            continue
        fails = check(out, c.expect)
        status = "pass" if not fails else "fail"
        if "judge" in c.expect:
            if judge is None:
                if not fails:
                    status = "skipped"  # 규칙 검사는 통과했지만 판정 기준은 채점하지 못함
                    fails = ["judge 미실행(--judge 필요)"]
            else:
                ok, why = judge(out, c.expect["judge"], {"input": c.input})
                if not ok:
                    fails.append(f"judge 실패: {why}")
                    status = "fail"
        results.append(Result(c.id, status, fails, str(out)[:120].replace("\n", " "), tags=c.tags,
                              seconds=time.perf_counter() - t0))
    return Report(results)


def to_markdown(rep: Report) -> str:
    g = rep.graded
    lines = [f"## 평가 결과: {rep.passed}/{len(g)} 통과 ({rep.rate:.0%})"]
    skipped = len(rep.results) - len(g)
    if skipped:
        lines.append(f"- 건너뜀 {skipped}건(채점 불가, 통과율에서 제외)")
    tags: Dict[str, List[Result]] = {}
    for r in g:
        for t in r.tags or ["-"]:
            tags.setdefault(t, []).append(r)
    if len(tags) > 1 or "-" not in tags:
        lines += ["", "| 태그 | 통과 | 전체 |", "|---|---|---|"]
        for t, rs in sorted(tags.items()):
            lines.append(f"| {t} | {sum(r.status == 'pass' for r in rs)} | {len(rs)} |")
    bad = [r for r in rep.results if r.status in ("fail", "error")]
    if bad:
        lines += ["", "### 실패", "| id | 상태 | 사유 |", "|---|---|---|"]
        lines += [f"| {r.id} | {r.status} | {'; '.join(r.failures)} |" for r in bad]
    return "\n".join(lines)


def to_json(rep: Report) -> dict:
    return {"passed": rep.passed, "graded": len(rep.graded), "rate": round(rep.rate, 4),
            "results": [r.__dict__ for r in rep.results]}


def make_judge(model: str = "claude-haiku-5-5") -> Judge:
    """LLM 판정기. 구조화 출력으로 {passed, reason}을 받는다. API 불가 시 판정 실패(False)로 처리하지 않고 예외."""
    from pydantic import BaseModel

    from . import structured

    class Verdict(BaseModel):
        passed: bool
        reason: str

    def judge(output: Any, rubric: str, ctx: dict) -> Tuple[bool, str]:
        prompt = (f"채점 기준: {rubric}\n\n질문/입력: {ctx.get('input')}\n\n시스템 출력:\n{output}\n\n"
                  "기준을 만족하면 passed=true. reason은 한 문장.")
        r = structured.ask_structured(prompt, Verdict, model=model, tag="eval_judge", max_tokens=300)
        if r.mock or r.data is None:
            raise RuntimeError(f"judge 호출 실패: {r.error}")
        return r.data.passed, r.data.reason

    return judge
