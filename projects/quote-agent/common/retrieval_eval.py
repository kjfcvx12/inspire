"""검색 적중률 평가(생성 답변이 아니라 '근거 문서를 찾았는가'만 본다). 발표용 수치: hit@k, MRR.

케이스 파일(JSONL, 한 줄 = 한 케이스, '#'로 시작하는 줄은 주석):
    {"q": "환불은 언제까지 되나요?", "expect_source": "faq.md"}
    {"q": "제주 배송", "expect_source": "faq.md", "expect_contains": "제주"}
    {"q": "화성 이주 정책", "expect_none": true}          # 근거가 없어야 정상인 질문(오탐 검사)
expect_source는 청크 출처의 부분 문자열(페이지 번호와 무관), expect_contains는 청크 본문의 부분 문자열.
둘 다 있으면 같은 청크가 둘을 모두 만족해야 적중이다. expect_none은 상위 k에 아무것도 없어야 통과.
BM25는 가능하지만 임베딩 검색은 항상 무언가를 돌려주므로 hybrid에서는 참고 수치로만 본다."""
import json
from pathlib import Path


def load_cases(path) -> list[dict]:
    cases = []
    for n, line in enumerate(Path(path).read_text(encoding="utf-8").splitlines(), 1):
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        try:
            c = json.loads(line)
        except json.JSONDecodeError as e:
            raise ValueError(f"{path}:{n} JSON 오류: {e}") from e
        if "q" not in c or not (c.get("expect_source") or c.get("expect_contains") or c.get("expect_none")):
            raise ValueError(f"{path}:{n} q와 expect_source/expect_contains/expect_none 중 하나가 필요합니다")
        cases.append(c)
    return cases


def _matches(case: dict, chunk) -> bool:
    src, text = chunk
    ok = True
    if case.get("expect_source"):
        ok &= case["expect_source"] in src
    if case.get("expect_contains"):
        ok &= case["expect_contains"] in text
    return ok


def evaluate(index, cases: list[dict], k: int = 3) -> dict:
    """index는 .search(q, k)와 .chunks를 가진 객체. 결과: hit_at_k, mrr(근거 있는 케이스 기준), none_ok, rows."""
    rows, rr, hits, pos = [], [], 0, 0
    none_total = none_ok = 0
    for c in cases:
        found = index.search(c["q"], k)
        chunks = [index.chunks[i] for i, _ in found]
        if c.get("expect_none"):
            none_total += 1
            ok = not chunks
            none_ok += ok
            rows.append({"q": c["q"], "ok": ok, "rank": None, "top": [s for s, _ in chunks]})
            continue
        pos += 1
        rank = next((r for r, ch in enumerate(chunks, 1) if _matches(c, ch)), None)
        hits += rank is not None
        rr.append(1 / rank if rank else 0.0)
        rows.append({"q": c["q"], "ok": rank is not None, "rank": rank, "top": [s for s, _ in chunks]})
    return {
        "k": k, "n": len(cases), "positive": pos,
        "hit_at_k": hits / pos if pos else None,
        "mrr": sum(rr) / pos if pos else None,
        "none_total": none_total, "none_ok": none_ok,
        "rows": rows,
    }
