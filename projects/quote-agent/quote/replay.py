"""시연용 결과 저장본. 예시 문장과 정확히 일치할 때만 저장된 결과를 돌려주고, mock 결과는 저장하지 않는다.
파일이 없거나 깨져도 예외 없이 빈 dict를 돌려준다."""
import json
import os
from dataclasses import asdict
from datetime import datetime
from pathlib import Path
from typing import Dict, Optional

from common import llm
from quote.agent import AgentResult
from quote.engine import Quote
from quote.examples import EXAMPLES

DEFAULT_PATH = Path(__file__).resolve().parents[1] / "data" / "demo_cache.json"


def _p(path) -> Path:
    return Path(path or os.environ.get("QUOTE_DEMO_CACHE") or DEFAULT_PATH)


def _to_json(r: AgentResult) -> dict:
    d = asdict(r)
    d["quotes"] = [q.model_dump(mode="json") for q in r.quotes]
    return d


def _from_json(d: dict) -> AgentResult:
    if not isinstance(d["text"], str):
        raise ValueError("text는 문자열이어야 합니다")
    return AgentResult(text=d["text"], quotes=[Quote.model_validate(q) for q in d.get("quotes", [])],
                       trace=[str(t) for t in d.get("trace", [])], budgets=[int(b) for b in d.get("budgets", [])],
                       unverified=[str(u) for u in d.get("unverified", [])], mock=bool(d.get("mock", False)),
                       steps=int(d.get("steps", 0)))


def save_cache(results: Dict[str, AgentResult], path=None) -> int:
    """mock이 아닌 결과만 저장하고 저장한 건수를 돌려준다."""
    kept = {t: r for t, r in results.items() if not r.mock}
    versions = {q.assumptions_version for r in kept.values() for q in r.quotes}
    doc = {"generated_at": datetime.now().isoformat(timespec="seconds"), "model": llm.MODEL,
           "assumptions_version": sorted(versions)[0] if len(versions) == 1 else sorted(versions),
           "results": {t: _to_json(r) for t, r in kept.items()}}
    p = _p(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(doc, ensure_ascii=False, indent=1), encoding="utf-8")
    return len(kept)


def load_cache(path=None) -> Dict[str, AgentResult]:
    try:
        doc = json.loads(_p(path).read_text(encoding="utf-8"))
        return {t: _from_json(d) for t, d in doc["results"].items()}
    except Exception:    # 파일 없음·깨짐·형식 오류 모두 '저장본 없음'으로 취급한다
        return {}


def lookup(text: str, cache: Dict[str, AgentResult]) -> Optional[AgentResult]:
    return cache.get(text) if text in EXAMPLES else None
