---
name: present
description: 구현이 끝나갈 때 코드, git log, docs/decisions.md를 읽어 3분 발표 대본, 구조도, 데모 시나리오를 만든다. 면접 마지막 발표 준비에 사용.
---

1. 코드, `git log`, `docs/decisions.md`를 읽는다.
2. `templates/presentation.md` 구조에 맞춰 `docs/presentation.md`를 갱신한다(구조도는 Mermaid).
3. 내가 내린 판단(선택, 버린 것)을 강조하고, 못 한 부분은 한계와 개선안으로 정직하게 쓴다.
4. 3분 대본을 마지막에 붙인다.

## 출력 형식 (고정)
`docs/presentation.md`에 `문제 / 접근·구조도 / 데모 시나리오 / 결과·한계 / 다음 단계 / 3분 대본` 6개 섹션.

## 검증
- 대본의 모든 주장(지표, 기능)은 코드나 실행 결과로 확인된 것만 쓴다. 안 돌려 본 기능은 "계획"으로 표기한다.
- 구조도의 모듈명이 실제 파일과 일치하는지 대조한다.
