---
name: checkpoint
description: 작업 중간 저장점. 20분마다 또는 기능 하나가 끝날 때 하네스 검사 → 커밋 → decisions.md 기록을 한 번에 한다. 구현 단계에서 사용.
---

이 스킬을 호출한 것이 커밋 요청이다. 푸시는 하지 않는다(요청 시에만).

1. `python scripts/check.py` 실행. FAIL이면 커밋하지 말고 `/build-loop`로 원인부터 고친다.
2. `git status`, `git diff --stat`으로 변경을 확인한다. `.env`·키·`.venv`가 스테이징되지 않았는지 본다.
3. 작은 단위로 커밋한다. 메시지는 한 줄(무엇을 + 왜).
4. `docs/decisions.md`에 `- (HH:MM) 결정 — 이유`를 추가한다. 결정이 없었으면 `- (HH:MM) 진행 — 한 일`.
5. 큰 마일스톤(핵심 기능 E2E 완료, 구현 동결)일 때만 `docs/history.md`의 Entry 추가와 Current State 갱신.

## 출력 형식 (고정)
`## 체크 / ## 커밋 / ## 기록 / ## 다음` 4개 헤더, 전체 10줄 이내. 체크는 PASS/WARN/FAIL 개수와 FAIL 항목만.

## 검증
- 체크 결과는 실제 실행 출력만 근거로 쓴다. 실행하지 않고 PASS로 적지 않는다.
- 커밋 후 `git status`로 작업 트리가 깨끗한지 확인한다.
