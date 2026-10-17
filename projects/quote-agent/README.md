# 용역 견적 에이전트 (quote-agent)

서울대 연구행정시스템 PI 용역을 기준으로, 다른 대학(고려대·연세대 등)이 기한·인원·범위·산출물·옵션을 다르게 요청해도 견적을 비교해서 보여주는 웹서비스.
**단가·기준안은 공개 정보가 없어 모두 가정값이다**(화면 사이드바와 `data/assumptions.json`에 표시). 견적은 담당자 검토 전 초안이다.

## 실행
```
pip install -r requirements.txt            # .env는 생성 시 복사돼 있다(없으면 .env.example 복사, 키 값은 커밋 금지)
streamlit run app.py                       # 또는 powershell -ExecutionPolicy Bypass -File scripts\demo_start.ps1
python scripts/check.py                    # 컴파일 + ruff + pytest + 환경 검사 (--api: API 실호출)
python -m pytest -q                        # 테스트(엔진·에이전트·검증기·내보내기·가정값)
python scripts/eval.py eval/golden.jsonl --target quote/evaltarget.py:engine_case                 # 엔진 골든셋(오프라인)
python scripts/eval.py eval/answers.jsonl --target quote/evaltarget.py:agent_case --min-pass 0.8  # 에이전트 골든셋(API 호출, 비용 발생)
python scripts/cost_report.py              # 실제 API 비용 리포트(logs/usage.jsonl 기준)
```
API가 안 되거나 사이드바에서 "AI 해석 사용"을 끄면 규칙 기반 mock으로 동작한다(정확도 낮음, 화면에 mock 표시).

## 어떻게 동작하나
1. 요청 문장 → 에이전트(`quote/agent.py`)가 도구를 골라 호출한다(최대 8회): `get_baseline`, `calculate_quote`, `right_size_team`(범위에 맞게 팀 재설계), `fit_to_budget`(예산 안의 안 탐색).
2. **금액은 LLM이 아니라 엔진(`quote/engine.py`)이 계산**한다. 에이전트는 해석·시나리오 선택·설명만 맡는다.
3. 설명 속 금액은 `quote/verify.py`가 엔진 결과와 대조해, 엔진이 낸 적 없는 금액은 화면에 '미검증'으로 표시한다.
4. 화면(`app.py`)은 결과를 탭으로 나눈다. 숫자에는 한글 읽기가 함께 나온다(`quote/korean.py`).
   - **요약**: 공급가액·부가세·합계(기준안 대비) → 경고 → AI 설명 문장 · **견적서**: 다운로드 없이 화면에서 보는 견적서(`quote/document.py`), 엑셀 내려받기(`quote/export.py`), 이력 저장
   - **비교**: 시나리오 비교표, 단계×산출물 배분표 · **근거·민감도**: 계산 산식(`quote/explain.py`), 인원·기간을 하나씩 바꿀 때의 변화
   - **조건 확인·수정**: AI가 이해한 조건을 고쳐 다시 계산 · **이력**: 저장한 견적과 수주·탈락·보류 기록(`quote/history.py`, 내부용) · **기록**: 에이전트 도구 호출 기록
   - 사이드바: 가정값 표시와 편집(`quote/assumptions_io.py`), AI 해석 끄기, **시연 저장본 우선 사용**(`quote/replay.py`, `data/demo_cache.json`: 예시 5개의 실제 결과), 예시 클릭 즉시 실행
   - 입력창은 폼이라 '견적 만들기'를 눌러야 실행된다(계산 중에 입력을 바꿔도 결과가 사라지지 않는다). 대학명 줄임말(고대·연대·카이스트)은 `data/assumptions.json`의 `client_aliases`로 정규화한다.

## 가정값 바꾸기
`data/assumptions.json`의 단가·단계/산출물 비중·가산율·경고 임계값을 고치고 `version`/`as_of`/`status`를 갱신한다. 파일이 없거나 잘못되면 코드의 기본값(`quote/assumptions.py`)을 쓰고 사유를 표시한다.
견적마다 계산에 쓴 가정값 버전이 기록된다. VAT 10%는 법정 세율이라 파일이 아니라 코드의 고정값이다.

## 구조
- `app.py` — Streamlit 화면
- `quote/engine.py` — 견적 계산, 민감도, 팀 재설계, 예산 맞추기 · `quote/assumptions.py` — 가정값 로더
- `quote/agent.py` — 도구 호출 루프 + mock 폴백 · `quote/verify.py` — 금액 대조 · `quote/export.py` — 엑셀
- `quote/evaltarget.py` — 골든셋 평가용 어댑터 · `eval/golden.jsonl`(엔진), `eval/answers.jsonl`(에이전트)
- `common/` — 호출 래퍼(재시도·mock 폴백·비용 기록), 구조화 출력, 평가 도구 등 공통 모듈
- `docs/decisions.md` — 결정 로그 · `docs/reference_bids.md` — 공개 입찰 규모 대조(원문 확인분만)

## 한계
- 단가·비중은 가정이다. 공개 입찰 3건과는 총액 규모만 대조했다(단가의 근거는 아님).
- 에이전트의 해석·설명은 실행마다 달라질 수 있다. 금액은 엔진이 정하지만, 평가 통과가 항상 보장되지는 않는다.
- 규칙 기반 mock은 폴백이라 지원하는 표현이 좁다('PMO', '프로젝트 매니저' 같은 별칭 미지원). 모호하거나 모순된 입력은 거부한다.
- 수행주체(파트너사) 분리, 사용자별 이력 분리(로그인), 실제 발주처 양식 출력, 계산 중 취소 버튼은 아직 없다(계산 취소는 이미 나간 API 호출을 끊을 수 없어 별도 작업이 필요하다).
- 시연 전에는 서버를 새로 띄운다. 오래 떠 있던 서버는 코드가 바뀐 뒤 모듈 캐시 때문에 깨질 수 있다(`scripts\demo_start.ps1 -Stop` 후 다시 실행).

## 실행 옵션(환경변수)
- `QUOTE_DEMO_MODE=0`: 실제 서비스용. 예시 요청과 "시연 저장본" 체크박스가 사라지고, 예시 문장을 그대로 넣어도 저장본을 쓰지 않는다(기본은 켜짐).
- `QUOTE_SHOW_LOG=1`: 개발자용 "기록" 탭(에이전트 도구 호출 기록)을 항상 보인다. 기본은 숨김이고, 설명 속 금액이 엔진과 다르거나 AI 없이 규칙 기반으로 동작했을 때만 자동으로 나타난다.
- `QUOTE_ASSUMPTIONS`, `QUOTE_DB_PATH`, `QUOTE_DEMO_CACHE`: 가정값 파일, 이력 DB, 시연 저장본의 경로를 바꾼다.
- 화면은 1024×768부터 휴대폰 폭(390px)까지 가로로 넘치지 않는 것을 확인했다(실제 브라우저 측정).

## 메모
- `.env`는 이 폴더 안의 것만 읽고 `.gitignore`로 커밋되지 않는다. 폴더를 압축·공유할 때는 `.env`를 뺀다.
- 커밋 금지: `.env`, `logs/`, `.venv/`, `*.db`.
