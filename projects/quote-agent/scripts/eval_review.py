"""AI 계산 에이전트 정확도 측정(실제 API). 엔진 값이 정답이다. 사용: python scripts/eval_review.py [--runs N]
결과는 logs/eval_review.json에 남기고 사례별 일치 여부와 합계 차이를 출력한다. 호출마다 usage.jsonl에도 기록된다."""
import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT)]

from quote import review                                     # noqa: E402
from quote.engine import QuoteRequest, calculate             # noqa: E402

CASES = {
    "기준안": {},
    "10주(단기)": {"weeks": 10},
    "24주": {"weeks": 24},
    "상주": {"onsite": True},
    "영문": {"english_deliverables": True},
    "사후지원 3개월": {"support_months": 3},
    "할인 10%": {"discount_pct": 10},
    "6명 팀": {"team": {"PM": 1, "수석컨설턴트": 1, "컨설턴트": 3, "분석가": 1}},
    "상주+영문+단기": {"weeks": 12, "onsite": True, "english_deliverables": True},
    "고려대 17주 6명": {"client": "고려대학교", "weeks": 17, "team": {"PM": 1, "수석컨설턴트": 1, "컨설턴트": 3, "분석가": 1}},
}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--runs", type=int, default=1)
    runs = ap.parse_args().runs
    rows, ok = [], 0
    for name, over in CASES.items():
        q = calculate(QuoteRequest(**over))
        for i in range(runs):
            r = review.ai_recompute(q)
            ok += r["status"] == "일치"
            rows.append({"case": name, "run": i + 1, "status": r["status"], "engine": q.total, "ai": r["ai_total"], "diff": r["diff"]})
            print(f"{name:<16} #{i + 1} {r['status']:<4} 엔진 {q.total:>13,} AI {r['ai_total'] or 0:>13,} 차이 {r['diff']}")
    print(f"일치 {ok}/{len(rows)}")
    (ROOT / "logs").mkdir(exist_ok=True)
    (ROOT / "logs" / "eval_review.json").write_text(json.dumps({"match": ok, "total": len(rows), "rows": rows}, ensure_ascii=False, indent=1), encoding="utf-8")


if __name__ == "__main__":
    main()
