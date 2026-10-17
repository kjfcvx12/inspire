# 발표 수치 출처 (재현 방법)
확인 시각 2026-10-17: ①③⑤는 15:04 안팎, ②④는 18:57. 코드는 다른 세션이 수정 중이므로 동결 후 아래 명령을 다시 실행해 수치를 갱신한다.

| # | 수치 | 재현 명령 | 확인 |
|---|---|---|---|
| ① | 기준안 공급가액 321,418,000 / VAT 32,142,000 / 합계 353,560,000 | `python -c "from quote.engine import baseline_quote as b; q=b(); print(q.supply,q.vat,q.total)"` (일회성 — 발표 전 `scripts/`로 옮길 것) · 골든 e01의 total도 353,560,000 | ✅ |
| ② | 테스트 136개 통과 | `python -m pytest -q` (18:57) | ✅ |
| ③ | 엔진 골든셋 18/18 | `python scripts/eval.py eval/golden.jsonl --target quote/evaltarget.py:engine_case` (`0-96` 보고, 이 세션 재실행 안 함 — 실행하면 `logs/eval_last.json`을 덮어써서 보류) | 보고값 |
| ③b | 에이전트 골든셋 18/18, 직전 17/18(a08b, 4회 중 1회 재현) | `python scripts/eval.py eval/answers.jsonl --target quote/evaltarget.py:agent_case` (API 호출, `0-96` 보고, 재실행 안 함) | 보고값(`logs/answers_run3.txt` 열람) · 변동 있음 |
| ④ | API 비용 307회 · $2.1529 · 호출당 $0.0070 | `python scripts/cost_report.py` (18:57 직접 실행. 앱 런타임+평가+시연 저장본 생성 호출. 개발용 AI 사용 비용 아님) | ✅ |
| ⑤ | 공개 입찰 금액 3건 | `docs/reference_bids.md`의 원문 URL | 원문 확인은 작성 세션 기록 — 이 세션에서 재열람 ❓ |

미확인(❓): 실제 API로 데모 문구를 돌린 화면, `extra_items` 추정 준수율, 에이전트 골든셋 통과율의 실행 간 분산(4회 중 1회 실패가 유일한 관측).

## 예상 Q&A 직접 확인 (7번 섹션)
재현: 아래를 `python`으로 실행 — 단계 제외 총액=기준안 총액(True)·재설계 220,333,000원, 할인 15% 이윤율 -0.065, mock '상주 없음'→onsite True(수정 전; 수정 후 False 확인), 기준안 범위 재설계 총액 -20,497,000원. (일회성 실행. 발표에 쓰려면 `scripts/`로 옮길 것)
