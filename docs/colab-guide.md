# Colab 사용법 (비상구 — 딥러닝 학습이 정말 필요한 주제에서만)

기본 경로는 로컬 + Anthropic API다(`docs/decisions.md` 5절). Colab은 이 PC(CPU torch, 4GB GPU)로 불가능한 학습·대량 이미지/음성 주제에서만 쓴다.
Colab은 브라우저에서 직접 쓴다. Claude Code와 MCP로 연결돼 있지 않다(미구성·미확인). "MCP로 Colab 제어"에 의존하는 계획은 세우지 않는다.

## 면접 전날 1분 점검 (필수)
1. colab.research.google.com → 새 노트북
2. 런타임 → 런타임 유형 변경 → **T4 GPU** → 저장
3. 첫 셀 실행:
```python
import torch; print(torch.cuda.is_available(), torch.cuda.get_device_name(0) if torch.cuda.is_available() else "")
```
4. `True`가 아니면(쿼터 소진) → 당일 API/CPU 경로로 간다. 확인 후 **런타임 → 세션 종료** (연결만 해도 GPU 시간이 소모됨).

## 세션 시작 셀 (세션이 새로 열릴 때마다 실행 — 설치가 초기화됨)
```python
!pip -q install anthropic
import os
from google.colab import userdata          # 왼쪽 🔑 Secrets에 ANTHROPIC_API_KEY 등록 + "노트북 액세스" 켜기
os.environ["ANTHROPIC_API_KEY"] = userdata.get("ANTHROPIC_API_KEY")
```
- 키를 셀 코드에 직접 쓰지 않는다(노트북 공유·저장 시 유출).
- torch, torchvision, pandas, scikit-learn은 Colab에 이미 설치돼 있다.

## 파일 주고받기
```python
from google.colab import files
files.upload()                              # 데이터 올리기(창이 뜸)
files.download("model.pt")                  # 결과 즉시 내려받기 — 세션이 끊기면 파일이 사라진다
```
- 큰 데이터는 Drive 마운트(`from google.colab import drive; drive.mount("/content/drive")`)가 낫지만 인증 창이 한 번 뜬다.
- 학습 결과(가중치, 지표 JSON)는 **학습 직후** 내려받는다. 로컬 `projects/<이름>/`에 넣어 평가·데모는 로컬에서 한다.

## 운영 규칙 (면접 중)
- 학습 코드는 작은 데이터·1~2 epoch로 먼저 돌려 끝까지 도는지 확인한 뒤 키운다(루프 규칙: 같은 증상 3회/15분이면 접근 변경).
- 유휴 시 자동 연결 해제되므로 돌려놓고 멀리 떠나지 않는다. 한 셀이 길면 진행 로그를 출력한다.
- Colab에서의 API 호출은 `logs/usage.jsonl`에 기록되지 않는다. 발표에 비용을 쓸 땐 "Colab 호출분 제외"라고 말한다.
- 학습 수치는 발표용으로 쓰려면 노트북이 아니라 로컬 스크립트(재현 가능)로 옮겨 기록한다. 못 옮기면 "Colab 1회 실행, 재현 스크립트 없음"이라고 밝힌다.
- 회선이 불안하면 핫스팟을 준비한다(1.md).

## 판단 기준: Colab을 쓰나?
| 상황 | 선택 |
|---|---|
| 표 데이터 예측, 텍스트 분류/RAG/요약 | Colab 안 씀 (로컬 sklearn / API) |
| 사전학습 모델 추론만(이미지 분류 등 소량) | 로컬 CPU 또는 API 비전 |
| 이미지·음성 모델 **파인튜닝/학습**이 요구사항 | Colab T4 |
