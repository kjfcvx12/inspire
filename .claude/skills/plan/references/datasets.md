# 데이터셋 탐색 절차 (최대 10분)
- WebSearch로 후보 탐색: Kaggle, Hugging Face Datasets, UCI, 공공데이터포털(data.go.kr), AI Hub, 서울열린데이터광장
- 라이선스·크기·컬럼/타깃 적합성을 보고 상위 1개 + 대안 2개(한 줄씩)
- 가능하면 curl/WebFetch로 `data/`에 저장 → 행·컬럼 수, 타깃 후보 요약
- 다운로드가 막히면 링크와 필요한 컬럼을 알려주고, `data/sample.csv` 합성 데이터로 진행
- 텍스트 문서(RAG)는 `data/`에 .md/.txt로 저장
