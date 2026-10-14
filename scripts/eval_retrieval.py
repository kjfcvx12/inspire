"""검색 적중률 평가. 사용: python scripts/eval_retrieval.py eval/retrieval.jsonl [옵션]
  --docs data         검색 대상 문서 폴더(.txt .md .pdf)
  --mode bm25|hybrid|both   both면 두 방식을 나란히 비교한다(기본 both)
  -k 3                상위 k개 안에서 근거를 찾았는지 본다
  --min-hit 0.8       마지막 방식(both면 hybrid)의 hit@k가 이보다 낮으면 종료 코드 1
                      ('근거 없음' 통과율은 참고용이다: 의미 검색은 구조적으로 걸러내지 못해 합격 기준에 넣지 않는다)
결과는 logs/eval_retrieval.json에도 저장한다(발표 수치의 재현 가능한 출처)."""
import argparse
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / "starters")]  # 레포(starters/common)와 단독 프로젝트(./common) 모두 지원
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
from common import docloader, embedsearch, retrieval_eval  # noqa: E402


def fmt(v):
    return "-" if v is None else f"{v:.0%}"


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("cases")
    ap.add_argument("--docs", default="data")
    ap.add_argument("--mode", choices=["bm25", "hybrid", "both"], default="both")
    ap.add_argument("-k", type=int, default=3)
    ap.add_argument("--min-hit", type=float, default=0.8)
    a = ap.parse_args()

    os.chdir(ROOT)
    cases = retrieval_eval.load_cases(a.cases)
    if not cases:
        raise SystemExit(f"케이스가 없습니다: {a.cases} (주석뿐인 템플릿이면 케이스를 추가하세요)")
    chunks, skipped = docloader.load_chunks(a.docs)
    if not chunks:
        raise SystemExit(f"검색할 문서가 없습니다: {a.docs} {skipped}")
    for path, why in skipped:
        print(f"⚠ 건너뜀: {path} — {why}")

    modes = ["bm25", "hybrid"] if a.mode == "both" else [a.mode]
    results = {}
    for m in modes:
        idx = embedsearch.build_index(chunks, mode=m)
        rep = retrieval_eval.evaluate(idx, cases, a.k)
        rep["actual_mode"] = idx.mode
        rep["error"] = getattr(idx, "error", None)
        results[m] = rep

    print(f"문서 청크 {len(chunks)}개 · 케이스 {len(cases)}개 · k={a.k}\n")
    print("| 방식 | 실제 동작 | hit@k | MRR | 근거 없음 통과(참고) |")
    print("|---|---|---|---|---|")
    for m, r in results.items():
        none = f"{r['none_ok']}/{r['none_total']}" if r["none_total"] else "-"
        print(f"| {m} | {r['actual_mode']} | {fmt(r['hit_at_k'])} | {fmt(r['mrr'])} | {none} |")
    for m, r in results.items():
        if r["error"]:
            print(f"\n⚠ {m}: 임베딩을 쓰지 못해 BM25로 동작했습니다 — {r['error']}")
        misses = [x for x in r["rows"] if not x["ok"]]
        if misses:
            print(f"\n[{m}] 실패 케이스")
            for x in misses:
                print(f"- {x['q']}  → 상위: {x['top'] or '없음'}")

    out = ROOT / "logs" / "eval_retrieval.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps({"k": a.k, "chunks": len(chunks), "results": results}, ensure_ascii=False, indent=1),
                   encoding="utf-8")
    judge = results[modes[-1]]
    rate = judge["hit_at_k"]
    ok = rate is not None and rate >= a.min_hit
    print(f"\n기준 hit@{a.k} ≥ {a.min_hit:.0%} ({modes[-1]}) → {'PASS' if ok else 'FAIL'}  "
          f"(상세: {out.relative_to(ROOT)})")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
