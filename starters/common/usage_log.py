"""API 사용량·비용 기록. 호출마다 logs/usage.jsonl에 한 줄을 추가한다(프롬프트 내용은 저장하지 않는다).
단가는 1M 토큰당 USD이며 2026-10-06 기준 자료다. 발표 전에 console.anthropic.com에서 다시 확인할 것."""
import json
import os
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

# model: (input, output, cache_read) USD per 1M tokens. 캐시 쓰기는 입력 단가의 1.25배로 가정한다.
# Haiku의 cache_read는 입력의 0.1배로 가정한 값이다.
PRICES = {
    "claude-sonnet-5-5": (2.00, 10.00, 0.20),
    "claude-opus-5-5": (4.00, 20.00, 0.20),
    "claude-haiku-5-5": (0.10, 0.50, 0.01),
}


def log_path() -> Path:
    return Path(os.environ.get("USAGE_LOG_PATH", ROOT / "logs" / "usage.jsonl"))


def cost_usd(model, inp, out, cache_read=0, cache_write=0):
    """모르는 모델이면 None(비용 미산정)."""
    p = PRICES.get(model)
    if not p:
        return None
    pin, pout, pread = p
    return (inp * pin + out * pout + cache_read * pread + cache_write * pin * 1.25) / 1_000_000


def record(model, usage, tag="", stop_reason=None) -> dict:
    """응답의 usage를 기록하고 한 줄 dict를 돌려준다. 기록 실패가 앱을 멈추지 않게 한다."""
    inp = getattr(usage, "input_tokens", 0) or 0
    out = getattr(usage, "output_tokens", 0) or 0
    cr = getattr(usage, "cache_read_input_tokens", 0) or 0
    cw = getattr(usage, "cache_creation_input_tokens", 0) or 0
    usd = cost_usd(model, inp, out, cr, cw)
    row = {"ts": datetime.now().isoformat(timespec="seconds"), "tag": tag, "model": model,
           "input": inp, "output": out, "cache_read": cr, "cache_write": cw,
           "usd": None if usd is None else round(usd, 6), "stop_reason": stop_reason}
    try:
        p = log_path()
        p.parent.mkdir(parents=True, exist_ok=True)
        with p.open("a", encoding="utf-8") as f:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
    except OSError:
        pass
    return row


def rows() -> list:
    p = log_path()
    if not p.exists():
        return []
    out = []
    for line in p.read_text(encoding="utf-8").splitlines():
        try:
            out.append(json.loads(line))
        except ValueError:
            continue
    return out


def summary(items=None) -> dict:
    items = rows() if items is None else items
    s = {"calls": 0, "input": 0, "output": 0, "cache_read": 0, "cache_write": 0,
         "usd": 0.0, "unpriced": 0, "truncated": 0}
    for r in items:
        s["calls"] += 1
        for k in ("input", "output", "cache_read", "cache_write"):
            s[k] += r.get(k) or 0
        if r.get("usd") is None:
            s["unpriced"] += 1
        else:
            s["usd"] += r["usd"]
        if r.get("stop_reason") == "max_tokens":
            s["truncated"] += 1
    s["usd"] = round(s["usd"], 6)
    return s
