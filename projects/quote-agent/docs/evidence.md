# 발표 수치 출처 (재현 방법)
확인 시각 2026-10-17 15:04 안팎. 코드는 다른 세션이 수정 중이므로 동결 후 아래 명령을 다시 실행해 수치를 갱신한다.

| # | 수치 | 재현 명령 | 확인 |
|---|---|---|---|
| ① | 기준안 공급가액 321,418,000 / VAT 32,142,000 / 합계 353,560,000 | `python -c "from quote.engine import baseline_quote as b; q=b(); print(q.supply,q.vat,q.total)"` (일회성 — 발표 전 `scripts/`로 옮길 것) · 골든 e01의 total도 353,560,000 | ✅ |
| ② | 테스트 27개 통과 | `python -m pytest -q` | ✅ |
| ③ | 골든셋 18/18 | `python scripts/eval.py eval/golden.jsonl --target quote/evaltarget.py:engine_case` → `logs/eval_last.json` (열람만 했고 재실행은 안 함) | ✅ 열람 |
| ④ | API 비용 21회 · $0.1584 · 호출당 $0.0075 | `python scripts/cost_report.py` (앱 런타임만. 개발용 AI 사용 비용 아님) | ✅ |
| ⑤ | 공개 입찰 금액 3건 | `docs/reference_bids.md`의 원문 URL | 원문 확인은 작성 세션 기록 — 이 세션에서 재열람 ❓ |

미확인(❓): 실제 API로 데모 문구를 돌린 화면, 에이전트의 요청 해석 정확도, `extra_items` 추정 준수율.
