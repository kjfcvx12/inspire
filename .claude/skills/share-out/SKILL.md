---
name: share-out
description: 작업 산출물(결정 로그, 발표 대본, README, 평가 리포트)을 연결된 Notion·Google Drive·Canva로 내보낸다. 사용자가 "노션에 올려줘/드라이브에 저장/캔바로 발표자료"처럼 요청했을 때만 사용.
---

내보내기는 외부 서비스에 내용을 게시하는 일이라 되돌리기 어렵다. **사용자가 요청한 대상에만, 실행 전 확인을 받고** 진행한다.

0. 내보낼 파일을 정한다: `projects/<이름>/docs/decisions.md`, `docs/presentation.md`(`/present` 결과), `README.md`, `logs/eval_last.json`의 요약 등.
1. 게시 전 점검: 파일을 직접 열어 `ANTHROPIC_API_KEY`·토큰·`.env` 내용·개인 경로가 없는지 확인한다. 없애지 못하면 중단한다. `logs/usage.jsonl` 원본은 올리지 않고 `cost_report.py` 요약만 쓴다.
2. 확인: 대상 서비스 · 위치(공개 범위 포함) · 올릴 내용의 한 줄 요약을 보여주고 승인을 받는다.
3. 대상별 도구(연결 상태는 위에서 확인됨):
   - **Notion**: `mcp__claude_ai_Notion__notion-create-pages`. 위치를 말하지 않으면 개인(private) 초안으로 만들고 그렇다고 알린다.
   - **Google Drive**: `mcp__claude_ai_Google_Drive__create_file`. 같은 이름의 파일을 덮어쓰지 않는다.
   - **Canva**: `mcp__claude_ai_Canva__generate-design`에 발표 대본의 슬라이드 개요(제목 + 핵심 문장)를 넘긴다. 결과는 초안이므로 사용자가 확인한다.
4. 결과 보고: 만든 항목의 링크 · 공개 범위 · 올린 파일 목록. 실패하면 이유와 로컬 파일 경로를 알려준다.

주의: 서비스별 쓰기 도구는 한 번에 한 대상씩 호출하고, 같은 내용을 여러 곳에 자동으로 중복 게시하지 않는다.
