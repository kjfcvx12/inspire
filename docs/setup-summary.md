# 바이브코딩 세팅 요약 (2시간 면접 + 발표)

> 최종 갱신 2026-10-14. 상세 작업 이력은 `docs/history.md`(영문, 상단 `Current State`만 읽으면 전체 파악), 규칙은 `CLAUDE.md`.

## 1. 한눈에 보기
- 목적: 주제 당일 공개 → 120분 구현 → 3분 발표. "계획 → 하네스 → 반복 구현 → 저장점 → 발표" 흐름을 스킬·에이전트·스크립트로 고정해 둔 키트.
- 저장소: `https://github.com/kjfcvx12/inspire` (브랜치 `claude/wizardly-gates-yc1p6c`, `main` 없음). 변경 사항은 로컬에 커밋됨(미푸시).
- Claude Code 기본값: 모델 Sonnet 5.5, effort `high` (`/model`, `/effort`로 변경).

## 2. 환경
| 항목 | 상태 |
|---|---|
| Python 환경 | conda `work` — Python 3.12.15 (`conda activate work`), 위치 `C:\ProgramData\anaconda3\envs\work` |
| 프로젝트 의존성 | anthropic, scikit-learn, pandas, streamlit, fastapi, uvicorn, python-dotenv, pytest 설치됨 |
| 추가 설치 | uv 0.13.0, langfuse, supabase, matplotlib (`pyproject.toml`의 `extras`), gh CLI(전역, 로그인 안 함) |
| 미설치 | torch/torchvision (이미지 딥러닝 주제 대비 시 사전 설치 권장) |
| 실행 방식 | 평문 `python`/`streamlit`/`pytest`. uv를 쓰면 앞에 `uv run` |
| 키 | `.env.example`을 `.env`로 복사 후 `ANTHROPIC_API_KEY` 입력(필수). Langfuse·Supabase는 선택 |

## 3. 파일 지도
| 경로 | 역할 |
|---|---|
| `CLAUDE.md` | 면접 규칙·명령어·시간 배분·흐름 (매 세션 자동 로드) |
| `.claude/skills/` | `plan`, `harness`, `build-loop`, `checkpoint`, `timecheck`, `present`, `demo-ready` |
| `.claude/agents/` | `verifier`(독립 검증, 수정 안 함), `interviewer`(예상 질문) |
| `.claude/settings.json` | 권한 허용 목록, `PYTHONUTF8=1`, `.env` 읽기 차단 |
| `scripts/check.py` | 하네스: 컴파일 + pytest + 키/`.env` 커밋 검사 (`--api`로 실호출 확인) |
| `scripts/cost_report.py` | 실제 API 비용 리포트(발표용) |
| `scripts/start.py` | START 시각을 `decisions.md`에 기록 (인코딩 안전) |
| `starters/predict/`, `starters/rag_agent/` | 예측(scikit-learn), RAG/에이전트(Streamlit) 스타터 |
| `starters/common/usage_log.py` | 호출별 토큰·비용 기록 → `logs/usage.jsonl`(gitignore) |
| `tests/` | 스모크·비용 계산 테스트 5개 |
| `docs/` | `decisions.md`(결정 로그), `presentation.md`(발표), `history.md`(작업 이력), 이 문서 |

## 4. 작업 흐름 (120분)
| 누적 분 | 단계 | 사용 |
|---|---|---|
| 0~10 | 분석 | `/plan` (START 시각 기록) |
| 10~20 | 설계 | `/harness` (검사·골든 케이스 먼저) |
| 20~85 | 구현 | `/build-loop` 반복, 20분마다 `/checkpoint`, 수시로 `/timecheck` |
| 85 | **기능 동결** | 이후 버그 수정만 |
| 85~95 | 검증 | `verifier` 에이전트, `/demo-ready` |
| 95~110 | 발표 준비 | `/present`, `interviewer` 에이전트, `cost_report.py` |
| 110~120 | 여유 | 리허설, 데모 실패 대비 확인 |

핵심 원칙: E2E를 얇게 먼저 → 완료 조건은 실행 가능한 검사로 → 같은 증상 3회/15분이면 접근 변경 → AI 결과는 직접 실행해 확인.

## 5. 토큰·시간 줄이고 성능 높이는 방법 (우선순위 순)

효과는 방향만 표시했고, 수치로 측정한 값은 아닙니다.

### A. Claude Code 세션 토큰 줄이기
| 방법 | 효과 | 비고 |
|---|---|---|
| **effort를 `medium` 기본으로, 설계·어려운 디버깅만 `high`** | 토큰·시간 큼 | 현재 저장된 기본값이 `high`. 루틴 구현에는 과함 |
| 단계가 바뀔 때 `/clear` (분석→설계→구현→발표) | 큼 | 이어받을 내용은 `history.md`의 `Current State`와 `decisions.md`가 담당 |
| 긴 세션은 `/compact` | 중간 | 구현 중반 이후 |
| 탐색·검증·대량 읽기는 서브에이전트(`verifier`, Explore)에 위임 | 중간 | 메인 컨텍스트에는 결론만 남음 |
| Grep으로 찾은 뒤 필요한 줄만 읽기, 데이터는 `head`/요약만 | 중간 | CSV 전체를 컨텍스트에 넣지 않기 |
| 요청에 완료 조건까지 한 번에 명시 | 중간 | 왕복 횟수 감소 (`/build-loop` 0단계) |
| `settings.json` deny에 `.venv`, `logs`, 대용량 데이터 읽기 차단 추가 (선택) | 작음 | 실수로 큰 파일을 읽는 것 방지. 아직 미적용 |

### B. 앱(API) 토큰·비용 줄이기
| 방법 | 효과 | 비고 |
|---|---|---|
| 호출에 `output_config={"effort": "low"}` + 적정 `max_tokens` | 큼 | Sonnet 5.5는 thinking이 기본 on. 현재 스타터는 `max_tokens=1024`라 잘림 가능성 있음(실측 전) |
| 반복 테스트는 Haiku 5.5, 최종 시연만 Sonnet 5.5 | 큼 | 단가 약 1/20 |
| 검색 top-k·청크 크기 줄이기, 에이전트 루프 한도 5→3 | 중간 | `starters/rag_agent/app.py` |
| 같은 질문은 결과 캐시(`st.cache_data`), 데모용 답변 미리 저장 | 중간 | 시간·비용·안정성 동시 개선 |
| 프롬프트 캐싱 | 작음 | 프롬프트가 짧으면 캐시 대상 최소 길이 미달이라 효과 없음. 긴 고정 문서가 있을 때만 |
| 호출마다 `record()` 로그 확인 | 관측 | `python scripts/cost_report.py`로 질문당 비용·잘림 확인 |

### C. 시간 줄이기
| 방법 | 비고 |
|---|---|
| 시험 전 사전 점검 | `.env`와 키 검증(`check.py --api`), 필요한 패키지(torch 등) 선설치, Supabase 프로젝트 일시중지 여부 확인 |
| 더미 주제로 120분 리허설 1회 | 병목은 환경·발표 준비에서 드러남 |
| 시작 5분에 `/plan` + `/harness`, 골든 케이스 먼저 | 이후 회귀를 바로 감지 |
| 독립 작업은 병렬 (코드 작성 + `verifier`, 독립 도구 호출) | |
| 결정이 생길 때마다 `decisions.md`에 한 줄 | `/present`가 몇 분 만에 끝남 |
| `/fast`(빠른 출력 모드) | 속도는 빠르지만 비용이 늘 수 있음. 플랜별 영향은 미확인 |

### D. 성능(품질) 높이기
- 완료 조건과 골든 테스트를 구현보다 먼저 만든다.
- 구현자와 분리된 `verifier`로 독립 검증한다(엣지 케이스, API 실패 시 mock).
- 딥러닝 학습은 피하고 사전학습 모델 + 가벼운 분류기, 또는 API zero-shot을 쓴다.
- 베이스라인 → 개선 1회 → 오류 분석 순서로, 지표는 1~2개만 명확히 둔다.
- 못 한 것은 한계와 다음 단계로 정직하게 발표한다(대본의 모든 주장은 실행 결과로 확인된 것만).

## 6. 시험 당일 체크리스트
1. `conda activate work` → `python scripts/check.py --api` (키·하네스 확인)
2. `docs/decisions.md`의 START 줄을 현재 시각으로 교체
3. `/plan <주제>` → `/harness` → 구현 시작
4. 20분마다 `/checkpoint`, 막히면 `/timecheck`
5. 85분 기능 동결 → `/demo-ready` → `/present` → `python scripts/cost_report.py`

## 7. 현재 미해결·주의
- `.env` 미생성, API 키 실호출·비용 실측 미수행(비용 기록 기능은 가짜 클라이언트로만 검증)
- 새 스킬·에이전트는 아직 한 번도 호출해 보지 않음
- 단가표는 2026-10-06 자료 기준 — 발표 전 콘솔에서 재확인
- 변경 사항은 로컬에 커밋됨(미푸시), `.vscode/`는 untracked
- Anthropic API는 유일한 유료 요소. Langfuse·Supabase는 무료 플랜(Supabase는 7일 미사용 시 일시중지)
