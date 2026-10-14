---
name: new-project
description: 면접 작업용 폴더(projects/<이름>/)를 만든다. 주제가 정해진 직후, 코딩 전에 사용. 그 폴더만 옮겨도 단독 실행·검사되는 구조로 스타터·하네스·테스트·결정 로그를 넣어준다.
---

목적: 모든 면접 작업을 한 폴더에 가두어, 제출·이동 때 그 폴더만 가져가면 되게 한다.

1. 이름(영문/숫자/-/_)과 유형을 정한다. 주제에서 합리적으로 정해지면 묻지 않는다.
   - `rag`: 문서 검색 + Claude 답변/에이전트 (Streamlit)
   - `predict`: CSV → 예측 모델 (`train.py`)
   - `blank`: 그 외 (빈 Streamlit 앱)
2. `python scripts/new_project.py <이름> --type <유형>` 실행. 이미 있으면 덮어쓰지 않으므로 이름을 바꾼다.
3. `python projects/<이름>/scripts/start.py`로 시작 시각을 그 폴더의 `docs/decisions.md`에 기록한다.
4. `python projects/<이름>/scripts/check.py`로 초록불을 확인한다(처음부터 PASS여야 정상).
5. 보고 형식(한 줄씩): 만든 경로 · 유형 · check 결과 · "이후 작업은 이 폴더 안에서만" · `.env` 복사 여부(키 값은 출력하지 않는다; 키트에 `.env`가 없으면 `.env.example`을 복사해 키를 넣도록 안내).

이후 규칙
- 파일 경로는 항상 `projects/<이름>/...`. 다른 폴더의 스타터·문서를 직접 고치지 않는다.
- 커밋은 `git add projects/<이름>`처럼 폴더 단위로 한다. `.env`·`logs/`는 폴더의 `.gitignore`가 막는다.
- 폴더를 옮기면: `.env`가 폴더 안에 있어 함께 따라간다. 새 환경에서는 `pip install -r requirements.txt`만 하면 된다. 압축·공유할 때는 `.env`를 빼고 보낸다.
