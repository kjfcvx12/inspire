"""시연용 저장본 만들기: 예시 문장 5개를 실제 에이전트(API)로 돌려 data/demo_cache.json에 저장한다. 실제 API 약 15회(약 $0.15).
사용: python scripts/make_demo_cache.py   (mock으로 떨어진 결과는 저장하지 않고 건수만 알린다)"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / "starters")]
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from quote import agent  # noqa: E402
from quote.examples import EXAMPLES  # noqa: E402
from quote.replay import DEFAULT_PATH, save_cache  # noqa: E402


def main() -> None:
    results = {}
    for i, text in enumerate(EXAMPLES, 1):
        r = agent.run(text)
        results[text] = r
        print(f"[{i}/{len(EXAMPLES)}] {'MOCK' if r.mock else 'ok'} · 시나리오 {len(r.quotes)}개 · 단계 {r.steps} · 미검증 금액 {len(r.unverified)}건 · {text[:30]}")
    saved = save_cache(results)
    mocks = sum(r.mock for r in results.values())
    print(f"저장 {saved}건, mock 제외 {mocks}건 → {DEFAULT_PATH.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
