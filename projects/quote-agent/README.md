# quote-agent

면접 작업 폴더(유형: blank). 이 폴더만 있으면 실행·검사가 된다. 다른 곳으로 옮겨도 그대로 동작한다.

## 실행
```
pip install -r requirements.txt     # (uv: uv pip install -r requirements.txt)
                                    # .env는 생성 시 키트의 것이 복사돼 이미 있다(없으면 .env.example 복사)
streamlit run app.py
python scripts/check.py             # 컴파일 + ruff + pytest + 환경 검사 (--api: API 실호출)
python scripts/eval.py eval/golden.jsonl --target app.py:함수   # 골든셋 평가(발표 수치의 출처)
python scripts/cost_report.py       # 실제 API 비용 리포트(logs/usage.jsonl 기준)
python scripts/eval_retrieval.py eval/retrieval.jsonl   # (rag) 검색 적중률 hit@k·MRR, bm25 vs hybrid 비교
```

## 구조
- `app.py` — 핵심 코드
- `common/llm.py` — 호출 래퍼: 재시도·mock 폴백·프롬프트 캐싱·스트리밍·비용 기록. `llm.ask()`, `llm.stream_text()`
- `common/structured.py` — 구조화 출력(pydantic 스키마 검증, 실패 시 재질문·폴백). `ask_structured()`
- `common/db.py` — SQLite 저장(`Store.add/list/kv_set`). 파일: `data/app.db`
- `common/evalkit.py`, `eval/golden.jsonl` — 골든셋 평가. `common/edgecases.py` — 엣지 입력 모음
- `common/usage_log.py` — 호출별 토큰·비용 기록(`logs/usage.jsonl`)
- `common/ui.py` — Streamlit 출력용 `md_safe()` (답변의 `~`·`$`가 취소선·수식으로 깨지는 것을 막는다)
- `common/textsearch.py` — 한국어 키워드 검색(형태소+BM25, kiwipiepy 없으면 bigram 폴백). `Index(chunks).search(q, k)`
- `common/docloader.py` — `.txt .md .pdf` → 청크(겹침, PDF는 `경로#p페이지`). 못 읽은 파일은 사유와 함께 `skipped`
- `common/embedsearch.py` — 하이브리드 검색(BM25+임베딩, RRF). `SEARCH_MODE=hybrid`로 켠다. 모델을 못 올리면 BM25로 폴백
- `common/retrieval_eval.py`, `eval/retrieval.jsonl` — 검색 적중률(hit@k·MRR)·"근거 없음" 오탐 평가
- `common/envload.py` — 이 폴더의 `.env`만 읽는다(상위 폴더를 탐색하지 않음)
- `scripts/` — `check.py`(하네스), `eval.py`, `eval_retrieval.py`, `cost_report.py`, `start.py`(시작 시각 기록)
- `tests/` — 스모크·엣지·골든 테스트부터 시작해 핵심 기능 테스트를 추가한다
- `docs/decisions.md` — 결정 로그(시각 · 결정 · 이유)

## 메모
- `.env`는 이 폴더 안의 것만 읽는다. 생성 시 키트의 `.env`가 복사됐다(키 값은 출력 안 함). 폴더째 옮겨도 따라간다.
- `.env`는 `.gitignore`에 있어 커밋되지 않는다. 폴더를 압축·공유할 때는 `.env`를 빼고 보낸다.
- 커밋 금지: `.env`, `logs/`, `.venv/`, `*.db` (`.gitignore`에 포함됨).
