"""실제 API 비용 리포트. 사용: python scripts/cost_report.py [--tag rag_agent]
logs/usage.jsonl(호출마다 기록됨)을 집계해 발표용 표를 출력한다. 추정이 아니라 기록된 usage 값이다."""
import sys
from collections import defaultdict
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(_ROOT), str(_ROOT / "starters")]  # 레포와 단독 프로젝트 모두 지원
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
from common import usage_log  # noqa: E402


def main():
    tag = sys.argv[sys.argv.index("--tag") + 1] if "--tag" in sys.argv else None
    items = [r for r in usage_log.rows() if tag is None or r.get("tag") == tag]
    if not items:
        print("기록 없음 — API를 호출하면 logs/usage.jsonl에 쌓입니다. (발표에는 '측정 없음'으로 표기)")
        return
    s = usage_log.summary(items)
    per_call = s["usd"] / max(s["calls"], 1)
    print("## 실제 API 비용 (기록 기준)")
    print(f"- 호출 {s['calls']}회 · 입력 {s['input']:,} · 출력 {s['output']:,} 토큰"
          f" (캐시 읽기 {s['cache_read']:,} / 쓰기 {s['cache_write']:,})")
    print(f"- 합계 **${s['usd']:.4f}** · 호출당 평균 ${per_call:.4f}")
    if s["unpriced"]:
        print(f"- ⚠ 단가를 모르는 모델 호출 {s['unpriced']}건은 비용에서 제외됨")
    if s["truncated"]:
        print(f"- ⚠ max_tokens로 잘린 응답 {s['truncated']}건 — 답변이 잘렸을 수 있음")
    groups = defaultdict(list)
    for r in items:
        groups[(r.get("tag") or "-", r.get("model"))].append(r)
    print("\n| 태그 | 모델 | 호출 | 입력 | 출력 | USD |")
    print("|---|---|---|---|---|---|")
    for (t, m), g in sorted(groups.items()):
        gs = usage_log.summary(g)
        print(f"| {t} | {m} | {gs['calls']} | {gs['input']:,} | {gs['output']:,} | ${gs['usd']:.4f} |")
    first, last = items[0]["ts"], items[-1]["ts"]
    print(f"\n기간: {first} ~ {last}")
    print("단가 기준: starters/common/usage_log.py의 PRICES (2026-10-06 자료, 발표 전 재확인)")


if __name__ == "__main__":
    main()
