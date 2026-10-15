# 결정 로그
- (HH:MM) START — 시험 시작 시각 (`/timecheck` 기준, 면접 시작 때 현재 시각으로 교체)
- (시각) 결정 — 이유

---

## 키트 설계 결정과 이유 (2026-10-14 10:40 정리, 10:47 [추정] 항목 실측 반영)

> 키트를 만들며 내린 결정을 사후에 모아 적은 것이다. 당시 시각의 기록이 아니다.
> 근거 표기: **[기록]** history.md·CLAUDE.md에 이유가 적혀 있음 / **[실측]** 측정·실행 결과로 확인함 / **[미확인]** 직접 테스트했지만 이유를 입증하지 못함 / **[판단]** 사용자가 밝힌 설계 판단(수치로 입증하지 않음).
> 처음에 [추정]이던 7건은 10:47에 직접 테스트했고, 결과는 아래 표와 "추정 검증 결과"에 있다.

### 1. 검색·RAG
| 사용 | 쓰지 않은 것 | 이유 |
|---|---|---|
| kiwipiepy + 직접 구현 BM25 (`textsearch`) | 단순 TF-IDF(공백 분리) | [실측] 한국어 조사 때문에 "배송" 질의가 "배송은"을 못 찾아 점수 0. 새 의존성도 늘리지 않음 |
| 하이브리드(BM25 + e5-small, RRF)를 `SEARCH_MODE=hybrid`로 선택 적용 | 기본값 하이브리드 | [실측] 바꿔 말한 질문이 많은 코퍼스에서 hit@3 73% → 100%, 단어가 겹치는 위키 코퍼스에서는 이득 없음. `import sentence_transformers` 11.4초, 모델 로드 약 16초 |
| `multilingual-e5-small` | MiniLM-multilingual | [실측] MiniLM이 더 낮았음 |
| 커버리지 게이트 0.25 | 더 엄격한 0.3~0.5 | [실측] 0.3부터 hit 감소(dev 93%, 0.5에서 67~80%). 최소 필터로만 둠 |
| 검색 후 거절은 LLM 프롬프트가 담당 | 유사도 임계값으로 거절 | [실측] 임베딩 유사도가 0.8~0.9에 몰려 범위 밖 질문을 못 거름 |
| chromadb·faiss·langchain 미설치 | 벡터DB·프레임워크 | [기록] 내부가 불투명(opaque). 2시간 안에 동작을 설명해야 함 |
| PDF OCR은 `PDF_OCR=claude` 옵션 | Tesseract, 항상 OCR | [기록] 이 PC에 Tesseract 없음. [실측] `logs/usage.jsonl`에서 `pdf_ocr` 15회 $0.2018(호출당 약 $0.013)이 전체 52회 $0.42의 48%. 항상 켜면 비용이 가장 큰 항목이 됨 |
| 읽을 수 없는 글자는 `[판독불가]` 표시 | 모델이 추측해 복원 | [실측] 흘림체 편지 스캔에서 정답 없이 그럴듯한 고어체를 생성함 |

### 2. LLM 호출·구조
| 사용 | 쓰지 않은 것 | 이유 |
|---|---|---|
| `common.llm` 경유 호출 | anthropic SDK 직접 호출 | [기록] 재시도·mock 폴백·캐싱·비용 기록을 한 곳에서 처리. API 실패 시 mock 폴백은 CLAUDE.md 규칙 |
| `structured`(pydantic 검증 + 재시도) | 강제 `tool_choice` | [기록] Sonnet 5.5는 강제 `tool_choice`가 400 |
| `usage_log` + `cost_report` | 추정 비용 | [기록] 발표 수치는 재현 가능해야 함. 실제 호출 로그만 근거로 삼음 |
| Langfuse는 쓰지 않음 (2026-10-15 18:21) | LLM 호출 트레이싱 연동 | [판단] 사용자 결정. 비용은 `usage_log`, 품질은 `evalkit`이 이미 맡고, 호출마다 외부 전송하면 실패점·데이터 반출이 늘어남. `.env`의 `LANGFUSE_*`는 비워 둠(`check_services.py`는 SKIP 처리) |
| 가격표 공식 문서 대조 | 기억 기반 단가 | [기록] 2026-10-14 공식 표와 일치 확인 |

### 3. 환경·의존성
| 사용 | 쓰지 않은 것 | 이유 |
|---|---|---|
| conda `work`(3.12) + uv | 시스템 Python 3.14·3.11 | [판단] 신버전은 변경이 많고 정착 기간이 짧아, 사용하던 3.12를 사용함. [실측] 이 판단을 뒷받침하는 차이는 이번 측정에서 관측되지 않았고(반증도 없음), 비교 결과는 다음과 같음: 3.12와 3.14는 해석된 라이브러리 144개 버전이 동일(차이 0). pytest 105개는 3.11.0·3.12·3.14.3 모두 통과, 경고 0건. 실행 시간은 3.12 약 28초, 3.14 약 29초, 3.11.0 46초(각 1회, 3.11은 첫 실행). 면접용 패키지 29종 중 28종이 3.12·3.14 모두 휠 제공(`openai-whisper`만 둘 다 실패). 낮은 버전이 더 오래된 라이브러리를 받는 효과는 3.11에서만 관측: numpy 2.4.6(3.12는 2.5.4), scipy 1.17.1(1.18.1), shap 0.51.0(0.53.0) 등 5/144가 다름. 3.11을 쓰지 않은 이유: 실제 API 호출·브라우저 검증은 3.12 환경에서만 했고 3.11에서는 위 5개 버전이 달라 그 검증이 이어지지 않음. 설치된 3.11은 첫 패치 릴리스(3.11.0)임 |
| torch 등을 `extras`로 분리 | core에 포함 | [실측] torch 497 MB + transformers 60 MB(site-packages). core만 설치한 3.14 가상환경 698 MB, extras 포함 `work` 환경 1.6 GB. `import torch` 3.2초 |
| 프로젝트 폴더별 `.env` 복사, 상위 폴더 탐색 안 함 | 상위 `.env` 자동 탐색 | [기록] 폴더만 옮겨도 단독 실행. 중첩 폴더가 부모 키를 잘못 가져오는 것을 막음 |
| xgboost·optuna·faiss-cpu·duckdb 등 미설치 | 사전 설치 | [기록] 제안만 했고 사용자가 답하지 않음. 필요하면 당일 설치 |
| `kiwipiepy-model`은 sdist 전용 | (해당 없음) | [실측] PyPI에 휠 없이 `kiwipiepy_model-0.24.0.tar.gz`만 있음. 휠 전용(`--only-binary :all:`) 설치는 모든 Python 버전에서 실패하므로 오프라인·휠 전용 환경에서는 사전 설치 필요 |

### 4. 하네스·권한·도구
| 사용 | 쓰지 않은 것 | 이유 |
|---|---|---|
| `verifier` 에이전트(수정 권한 없음) | 구현자 자기 검증 | [실측] 리허설에서 엉터리 입력을 조용히 받아들이는 문제를 찾음 |
| `interviewer` 에이전트 | 대본만 작성 | [실측] 리허설에서 재현 불가능한 발표 수치와 "0원" 비용 주장을 지적함 |
| `check.py`의 린트는 WARN만 | 린트 실패 시 차단 | [기록] 린트가 흐름을 막지 않게 함 |
| `git push`를 허용 목록에서 제거 | 자동 푸시 | [기록] 푸시는 "클리어 푸시"라고 쓴 경우에만 |
| `Read(.env)`·`Read(**/.env)` 거부 + PreToolUse 훅(`.claude/hooks/block_env_read.py`)이 Bash·PowerShell·Read·Grep의 `.env` 접근 차단 | 규칙 없음 / Read 규칙만 | [실측] 10:47 `Read(.env)`만 있을 때 Read 도구는 거부됐지만 Bash(`wc -c < .env`)는 파일에 접근함(내용은 출력하지 않음). 훅 적용 후 같은 Bash 호출과 Grep(path=`.env`)이 모두 차단됨. `tests/test_env_hook.py` 25개 통과, 셸 검사를 일부러 제거하면 8개 실패(변이 확인). `**/.env`는 스캐폴드 폴더(`projects/<이름>/.env`에 키가 복사됨)까지 덮기 위함 |
| 훅의 한계 | (해당 없음) | [기록] 문자열 검사라 `cat .e*`, `python -c "open('.'+'env')"` 같은 우회는 못 잡음. 우발적 노출을 막는 용도이며 보안 경계가 아님. 파이썬 스크립트가 내부에서 `.env`를 읽는 것(`check.py`, `envload`)은 막지 않음 |
| Playwright MCP | 수동 스크린샷 | [기록] 데모 화면 확인용. 마크다운 깨짐(취소선·수식 처리)을 이걸로 발견 |
| context7 MCP | 웹 검색 | [기록] 라이브러리 최신 문서 조회용 |
| Notion·Drive·Canva는 `/share-out`으로만, 게시 전 확인 | 항상 연결해 자동 게시 | [기록] 외부 게시는 되돌리기 어려움. 비밀값 점검 후 사용자 확인 |
| MCP 버전 고정(`@0.0.83`, `@4.4.1`) | `latest` | [실측] 드리프트가 일어날 조건을 확인함. npm 릴리스: context7은 최근 30일 8회(10-07 이후 7회)·90일 19회, playwright는 30일 3회·90일 5회. context7 4.1.1 → 4.4.1에서 MCP SDK(`@modelcontextprotocol/server` 2.0.0 → 2.2.0) 등 의존성 9건이 바뀜. npx 캐시에는 고정한 0.0.83과 4.4.1만 있어 고정이 실제 실행 버전에 적용됨. 한계: 2026-10-14 기준 고정 버전 = `latest`이고, 새 버전 때문에 동작이 깨진 사례는 관측하지 못함 |

### 5. 스택(CLAUDE.md에 고정)
| 사용 | 대안 | 이유 |
|---|---|---|
| Streamlit | FastAPI + 프론트 | [실측] 대화 기록이 있는 챗 UI를 같은 기능으로 만들어 비교: 코드 10줄 대 30줄(비어 있지 않은 줄, FastAPI는 HTML·JS 포함). 두 앱 모두 Chrome(Playwright)에서 질문 → 답변 표시를 확인함. 서버 기동(HTTP 200까지, 3회)은 Streamlit 1.57~1.75초, FastAPI 1.09~1.11초로 FastAPI가 약 0.5초 빠름. Streamlit은 입력창 비우기·말풍선·마크다운이 기본 제공이고, FastAPI 쪽은 입력창이 비워지지 않고 파비콘 404 콘솔 오류가 남음. 한계: 사람이 만드는 데 걸리는 시간과 디자인 품질은 측정하지 않음 |
| SQLite | Supabase | [실측] SQLite는 표준 라이브러리, 계정·네트워크 없이 1000행 삽입 0.009초. Supabase는 `SUPABASE_URL`·`SUPABASE_KEY` 필요하며 무료 플랜은 1주 비활성 시 일시중지([공식 문서](https://supabase.com/docs/guides/platform/free-project-pausing), [가격 페이지](https://supabase.com/pricing)) |
| scikit-learn 위주 | 딥러닝 학습 | [기록] 사전학습 모델 + 가벼운 분류기 또는 API zero-shot 방침 (`docs/setup-summary.md`) |
| Colab 유료 결제 안 함. 무료 T4는 딥러닝 학습이 꼭 필요할 때만 쓰는 비상구 (2026-10-15 16:38 추가) | Colab 유료 사전 결제, 면접 중 외부 GPU 상시 사용 | [실측] 이 PC는 RAM 15.2 GB(여유 약 9 GB), RTX 3050 Ti 4 GB VRAM, torch는 CPU 빌드(`cuda: False`). 무료 Colab에서 `torch 2.11.0+cu130`, `cuda: True`, Tesla T4 연결과 `pip install anthropic`(1.14.0) 성공을 사용자가 직접 확인함. [판단] 데모는 `projects/<이름>/`이 이 PC에서 단독 실행돼야 하고, 업로드·연결·다운로드에 10~20분이 들어 2시간 안에는 이득이 작음. 결제로 줄어드는 것은 GPU 대기·세션 제한뿐이라 미리 결제할 이유가 없음. [실측] 16:38 이후 같은 노트북에서 보안 비밀(`userdata`)로 키를 읽어 `claude-haiku-5-5` 호출 성공(응답 "OK", input 17·output 4 토큰). 세션이 재시작되면 pip 설치가 사라져 `ModuleNotFoundError`가 났음 → 매 세션 시작 시 `!pip -q install anthropic`을 먼저 실행하고 결과는 즉시 다운로드해야 함. Colab 쪽 호출은 `logs/usage.jsonl`에 기록되지 않아 발표 비용 수치에 쓰지 않음. [실측] 파일 업로드(`files.upload`, 이 PC → Colab)와 다운로드(`files.download`, Colab → 이 PC) 모두 통과(사용자 확인, 파일 크기·형식은 미기록). **[미확인]** 면접 당일 무료 GPU 쿼터(유동적이라 보장 없음) |
| Colab 무료 GPU 쿼터는 잔량을 볼 수 없어 당일 연결 점검으로 대체 (2026-10-15 17:58 추가) | 사전에 쿼터 잔량 확인 | [판단] 무료 플랜 UI에 남은 시간이 표시되지 않는 것으로 알고 있음(공식 문서는 이번에 재확인하지 않음). 오늘 T4 할당 성공은 오늘 쿼터가 있었다는 사실만 보여줌. 면접 전 `torch.cuda.is_available()`를 1분 점검하고, 안 되면 API·CPU 경로로 진행. 연결만 해 둬도 GPU 시간이 소모되므로 쓰지 않을 때는 세션을 종료 |

---

## 추정 검증 결과 (2026-10-14 10:47)

처음 [추정]으로 적었던 7건을 직접 테스트한 결과다. 결과가 추정과 다른 것은 굵게 표시했다.

| # | 추정 | 테스트 | 결과 |
|---|---|---|---|
| 1 | PDF OCR은 비용 때문에 옵션 | `scripts/cost_report.py`로 실제 로그 집계 | 확인됨. OCR 15회 $0.2018 = 전체의 48% |
| 2 | 3.14는 호환성 불확실 | 3.11·3.12·3.14로 의존성 해석, 빈 3.12·3.14 venv에 휠 전용 드라이런, 3.14.3에 core 설치 후 pytest | **반박됨.** 해석 모두 통과, 고정된 143개 패키지 휠 모두 존재(`kiwipiepy-model` 제외, 아래 참고), 3.14.3에서 pytest 80 passed·형태소 분석 정상. extras 중 torch 등을 3.14에 실제 설치·실행하지는 않았음 |
| 3 | torch가 커서 extras 분리 | site-packages 크기, import 시간 측정 | 확인됨. torch 497 MB, core 환경 698 MB vs 전체 1.6 GB |
| 4 | `.env` 읽기 거부로 키 노출 방지 | Read 도구로 `.env` 읽기 시도(범위를 파일 끝 밖으로 지정해 내용 노출 방지), Bash로 크기만 조회 | 부분 확인. **Read 도구는 거부되지만 Bash로는 접근 가능** → 10:53 훅으로 보강해 Bash·PowerShell·Read·Grep 모두 차단 확인(위 4번 표) |
| 5 | MCP 버전 고정으로 드리프트 방지 | `npm view`로 릴리스 이력·의존성 비교, npx 캐시의 설치 버전 확인 | **조건 한정 확인.** 릴리스 빈도(context7 30일 8회)와 의존성 변경은 확인했고 고정이 실제 적용됨. 동작 파손 사례는 관측하지 못함 |
| 6 | Streamlit이 데모에 가장 빠름 | 같은 기능의 챗 UI를 두 프레임워크로 구현해 줄 수·기동 시간 비교, 브라우저로 동작 확인 | **코드량은 확인, 기동 시간은 반대.** 코드 10줄 대 30줄이고 둘 다 동작함. 기동은 FastAPI가 약 0.5초 빠름. 사람 작업 시간은 미측정 |
| 7 | SQLite가 계정·네트워크 없이 로컬 동작 | 임시 DB 쓰기, `.env.example` 변수 확인, 공식 문서 확인 | 확인됨 |

### 재현 방법 (테스트는 저장소 밖 임시 폴더에서 실행했고, 저장소에는 스크립트를 추가하지 않음. `.env` 훅만 `tests/test_env_hook.py`로 커밋됨)
- 휠 가용성 29종: 빈 3.12·3.14 venv에서 패키지별 `uv pip install --dry-run --only-binary :all: <패키지>` (xgboost, lightgbm, catboost, optuna, shap, faiss-cpu, chromadb, duckdb, tensorflow, opencv-python, onnxruntime, prophet, gradio, langchain, librosa, scikit-surprise, statsmodels, spacy, nltk, imbalanced-learn, mediapipe, ultralytics, umap-learn, hdbscan, networkx, ipykernel, python-multipart, pycaret, openai-whisper)
- 실행 시간: 3.12(`work`)와 3.14 venv에서 `python -m pytest -q`를 번갈아 2회씩
- MCP 릴리스 이력: `npm view <패키지> time --json`으로 날짜별 버전 수, `npm view <패키지>@<버전> --json`으로 의존성 비교, `npm config get cache`의 `_npx/*/node_modules`에서 실행 버전 확인
- 챗 UI 비교: Streamlit(`st.chat_input`·`st.chat_message`·`st.session_state`, 10줄)과 FastAPI(HTML·JS 페이지 + `/ask` 엔드포인트, 30줄)를 만들어 서버 기동 3회 측정, Playwright MCP로 입력 → 응답 표시 확인
- 비용: `python scripts/cost_report.py`
- 3.14 호환성: `uv pip compile pyproject.toml --extra extras --python-version 3.14 -o req.txt` → 빈 venv에서 `uv pip install --dry-run --no-deps --only-binary :all: -r req.txt`(`kiwipiepy-model` 줄 제외) → `uv pip install -r pyproject.toml` 후 `python -m pytest -q`
- 크기: site-packages의 `torch` 등 폴더 합계, `python -c "import torch"` 시간
- `.env` 접근: Read 도구는 권한 거부, Bash는 `wc -c < .env`로 파일 크기만 확인(내용 미출력)
- MCP: `npm view @playwright/mcp dist-tags.latest`, `npm view @upstash/context7-mcp dist-tags.latest`
- Streamlit·SQLite: 4줄 `st.text_input` 예제를 `streamlit run`으로 띄워 `/_stcore/health` 응답까지 시간 측정, `sqlite3`로 1000행 삽입

### 남은 일
- (해소 10:53) `.env` Bash 접근은 PreToolUse 훅으로 차단함. 남은 한계는 위 "훅의 한계" 행 참고.
- 3.14에서 extras(torch 등)를 실제로 설치·실행하는 테스트는 하지 않았다.
- 3.11에서는 core 테스트(pytest)만 확인했다. 실제 API 호출, Streamlit 실행, extras는 3.12에서만 검증됐다.
- 사람이 직접 만드는 데 걸리는 시간은 측정하지 않았다(코드 줄 수만 비교).
- MCP 고정이 막아 준 실제 장애 사례는 없다. 릴리스 빈도와 의존성 변경만 확인했다.
