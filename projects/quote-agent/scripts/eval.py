"""골든셋 평가 실행. 사용: python scripts/eval.py eval/golden.jsonl --target app.py:search [옵션]
  --target FILE.py:함수   평가할 함수(입력 하나 또는 dict/list를 받는다)
  --min-pass 1.0          통과율이 이보다 낮으면 종료 코드 1 (기본 1.0 = 전부 통과)
  --judge                 expect.judge 케이스를 LLM으로 채점(API 비용 발생)
결과는 마크다운으로 출력하고 logs/eval_last.json에도 저장한다(발표 수치의 재현 가능한 출처)."""
import argparse
import importlib.util
import json
import logging
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / "starters")]  # 레포(starters/common)와 단독 프로젝트(./common) 모두 지원
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
from common import evalkit  # noqa: E402


def load_target(spec: str):
    file, _, func = spec.rpartition(":")
    if not file or not func:
        raise SystemExit("--target은 '파일.py:함수' 형식이어야 합니다")
    path = Path(file).resolve()
    sys.path.insert(0, str(path.parent))
    m = importlib.util.spec_from_file_location("eval_target", path)
    mod = importlib.util.module_from_spec(m)
    m.loader.exec_module(mod)
    return getattr(mod, func)


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("golden")
    ap.add_argument("--target", required=True)
    ap.add_argument("--min-pass", type=float, default=1.0)
    ap.add_argument("--judge", action="store_true")
    a = ap.parse_args()

    golden = Path(a.golden).resolve()
    os.chdir(ROOT)  # 스타터의 상대경로(DOCS_DIR 등)가 프로젝트 루트 기준이 되도록
    cases = evalkit.load_golden(golden)
    if not cases:
        raise SystemExit(f"케이스가 없습니다: {golden} (주석뿐인 템플릿이면 케이스를 추가하세요)")
    logging.disable(logging.WARNING)  # Streamlit 앱을 모듈로 불러올 때 쏟아지는 bare-mode 경고를 숨긴다
    fn = load_target(a.target)
    rep = evalkit.run_eval(fn, cases, judge=evalkit.make_judge() if a.judge else None)
    print(evalkit.to_markdown(rep))
    out = ROOT / "logs" / "eval_last.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(evalkit.to_json(rep), ensure_ascii=False, indent=1), encoding="utf-8")
    ok = rep.rate >= a.min_pass and bool(rep.graded)
    print(f"\n기준 {a.min_pass:.0%} → {'PASS' if ok else 'FAIL'}  (상세: {out.relative_to(ROOT)})")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
