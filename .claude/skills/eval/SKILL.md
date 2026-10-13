---
name: eval
description: 골든셋 평가를 만들고 실행해 통과율을 재현 가능한 수치로 남긴다. 핵심 기능이 E2E로 동작한 직후, 프롬프트·모델·검색 방식을 바꾸기 전후, 발표 수치가 필요할 때 사용.
---

목적: "잘 됩니다"가 아니라 `N건 중 M건 통과`를 명령어 한 줄로 재현하게 한다. 작업 폴더는 `projects/<이름>/`.

1. 평가할 함수를 정한다. 입력 하나(또는 dict/list)를 받아 값을 돌려주는 순수한 함수여야 한다.
   - rag: `app.py:search`(검색 품질), 필요하면 `ask`
   - predict: `train.py:fit_and_score` (입력 `{"path":..., "target":...}`, 출력 dict의 `score`)
2. `eval/golden.jsonl`에 케이스를 쓴다. 최소 구성: 정상 5건 이상 + 엣지 3건 이상 + "답이 없어야 하는" 질문 1건 이상.
   - 형식·검사 종류는 `starters/common/evalkit.py` 상단 설명을 따른다(contains / regex / range / approx / judge).
   - **정답을 코드나 문서에서 그대로 복사해 만들지 않는다**(채점 오염). 도메인 기준으로 직접 쓴다.
3. 실행: `python projects/<이름>/scripts/eval.py projects/<이름>/eval/golden.jsonl --target <파일>:<함수> --min-pass 0.8`
   - `judge` 케이스는 `--judge`를 붙일 때만 LLM으로 채점한다. **API 비용이 드니 먼저 사용자에게 알린다.**
4. 실패를 두 종류로 나눈다: ① 코드가 틀림 → 고친다 ② 케이스가 틀림 → 케이스를 고치되 이유를 `docs/decisions.md`에 남긴다. 통과시키려고 기준을 느슨하게 하지 않는다.
5. 수정 후 같은 명령을 다시 돌려 전후를 비교한다(`logs/eval_last.json`이 마지막 결과).
6. 발표용 한 줄: `골든셋 N건 · 통과 M건(P%) · 재현: <명령어>` + 한계(표본 크기, 직접 만든 케이스라는 점)를 함께 적는다.

보고 형식: 명령어 · 통과/전체 · 실패 케이스 id와 원인 한 줄 · 조치.
