# 바이브코딩 면접 (2시간, 주제 당일 공개, 마지막 발표)

## 스택
Python 3.11 · uv · FastAPI/Streamlit · scikit-learn · SQLite(또는 Supabase) · Anthropic API · (선택) Langfuse

## 규칙
- 코딩 전 반드시 계획(MVP 범위, 시간 배분)을 먼저 제시한다.
- 핵심 기능 하나를 end-to-end로 먼저 동작시키고 확장한다.
- 항상 실행 가능한 상태 유지, 작은 단위로 커밋한다.
- 2시간 안에 끝낼 수 있는 범위만 한다. 완성도보다 동작하는 데모 우선.
- 중요한 설계 결정은 이유를 한 줄로 설명한다(발표용). 결정 로그는 docs/decisions.md에 적는다.
- 샘플 입력으로 테스트 1~2개 + 엣지 케이스 확인.
- API 키는 .env 사용, 커밋 금지. API 실패 시 mock 폴백.
- 작업 내역은 docs/history.md에 영어로 기록하고, 사용자에게는 한글로 보여준다. 읽을 때는 상단 `Current State`만 읽으면 전체를 파악할 수 있고, 갱신 때마다 이를 최신 누적 요약으로 다시 쓴다.
- 발표에 쓸 수치는 커밋된 스크립트·테스트로 재현 가능해야 한다. `decisions.md`의 시각은 추측하지 말고 실제 시각으로 적는다.
- 사용자가 "클리어"라고 쓰면 정상 종료 절차를 진행한다: ① `docs/history.md`에 이번 작업의 Entry 추가와 `Current State` 갱신 ② `python scripts/check.py` 실행 ③ 변경 사항 커밋(비밀값·`.env` 제외) ④ 작업 트리·미푸시 개수를 보고하고 `/clear`를 안내한다. 푸시는 "클리어 푸시"라고 쓴 경우에만 한다.
- 사용자에게 묻는 것은 방향성과 정말 중요한 것(되돌리기 어려운 결정, 요구사항 해석)만이다. 그 외에는 합리적 기본값으로 진행하고 한 줄로 알린다.

## 명령어
활성화된 환경(conda `work` 또는 uv `.venv`)에서 실행한다. uv를 쓰면 앞에 `uv run`을 붙인다.
- 설치: `uv sync` (conda는 `conda activate work`, 선택 패키지는 `uv sync --extra extras`)
- 시작 시각 기록: `python scripts/start.py` (결정 로그 파일은 Edit/Write 도구나 파이썬으로만 수정한다. PowerShell `Get-Content`/`Set-Content`는 한글이 깨질 수 있다)
- 하네스(한 번에 검사): `python scripts/check.py` (`--api`를 붙이면 API 실호출까지 확인)
- 예측 스타터: `python starters/predict/train.py data.csv target_col`
- RAG/Agent 스타터: `streamlit run starters/rag_agent/app.py`
- 테스트: `pytest -q`
- 실제 API 비용 리포트(발표용): `python scripts/cost_report.py` (호출마다 `logs/usage.jsonl`에 자동 기록. 새 API 호출 코드는 `starters/common/usage_log.py`의 `record()`를 붙인다)

## 시간 배분(120분)
분석 10 · 설계 10 · 구현 65 · 검증 10 · 발표 준비 15 · 여유 10 (기능 동결 85분)

## 루프·하네스·에이전트
- 흐름: `/plan` → `/harness`(설계 단계) → `/build-loop`(구현 반복) → `/checkpoint`(20분마다) → `/timecheck`(수시) → `/present` → `/demo-ready`
- 루프 엔지니어링: 완료 조건(실행 가능한 검사) → 작게 구현 → 실행 → 검증 → 수정. 같은 증상 3회 실패 또는 15분이면 접근을 바꾼다.
- 하네스 엔지니어링: 모델 바깥의 안전장치(`scripts/check.py`, `tests/`, 골든 입력, mock 폴백, 반복 한도, 권한)를 먼저 만든다.
- 에이전트(`.claude/agents/`): `verifier`(독립 검증, 코드 수정 안 함), `interviewer`(면접관 역할 예상 질문)

## 검증·분할 원칙
- AI 결과(코드, 데이터, 수치)는 그대로 믿지 않고 직접 실행·열람해 확인한다. 확인 못 한 것은 "미확인"으로 말한다.
- 큰 요청은 단계별로 나눠 실행하고 단계마다 동작을 확인한다(한도·중단 대비).
- 스킬은 목적·순서·출력 형식을 명시한다.
