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

## 명령어
- 설치: `uv sync`
- 예측 스타터: `uv run python starters/predict/train.py data.csv target_col`
- RAG/Agent 스타터: `uv run streamlit run starters/rag_agent/app.py`
- 테스트: `uv run pytest -q`

## 시간 배분(120분)
분석 10 · 설계 10 · 구현 65 · 검증 10 · 발표 준비 15 · 여유 10
