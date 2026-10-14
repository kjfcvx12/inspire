"""RAG + tool-calling Agent 스타터 (Streamlit). data/ 폴더의 .txt/.md를 검색 소스로 사용.
호출은 common.llm(재시도·mock 폴백·캐싱·비용 기록), 질문 기록은 common.db(SQLite)를 쓴다."""
import os
import sys
from pathlib import Path

import streamlit as st

HERE = Path(__file__).resolve().parent
sys.path[:0] = [str(HERE), str(HERE.parent)]  # starters/ 안에서도, projects/<이름>/ 단독으로도 common을 찾는다
from common import llm  # noqa: E402
from common.db import Store  # noqa: E402
from common.docloader import load_chunks  # noqa: E402  문서 로더(txt·md·pdf를 청크로)
from common.embedsearch import build_index  # noqa: E402  검색 색인(기본 키워드, SEARCH_MODE=hybrid면 임베딩 결합)
from common.envload import load_env  # noqa: E402  이 폴더의 .env만 읽는다
from common.ui import md_safe  # noqa: E402  '3~5일'·'$' 가 취소선·수식으로 깨지지 않게
from common.usage_log import summary  # noqa: E402  호출별 토큰·비용 기록(logs/usage.jsonl)

load_env()
MODEL = llm.MODEL
DOCS_DIR = os.environ.get("DOCS_DIR", "data")
MAX_STEPS = 5
SYSTEM = ("당신은 제공된 문서 검색 결과만 근거로 답하는 도우미입니다. 근거가 없으면 모른다고 답하고, "
          "답변 끝에 근거로 쓴 출처 파일 경로를 적습니다.")


def _docs_signature(docs_dir):
    """문서가 바뀌면 색인을 다시 만들도록 (경로, 수정시각) 목록을 캐시 키로 쓴다."""
    return tuple((str(p), p.stat().st_mtime_ns) for p in sorted(Path(docs_dir).rglob("*")) if p.is_file())


@st.cache_resource(show_spinner="문서 색인 중…")  # 입력마다 스크립트가 다시 도므로 모델 재로딩을 막는다
def _build(docs_dir, mode, signature):  # signature는 캐시 키 전용(앞에 _를 붙이면 키에서 빠진다)
    chunks, skipped = load_chunks(docs_dir)  # skipped: 읽지 못한 파일과 사유
    return chunks, skipped, (build_index(chunks, mode) if chunks else None)


CHUNKS, SKIPPED, INDEX = _build(DOCS_DIR, os.environ.get("SEARCH_MODE", "bm25"), _docs_signature(DOCS_DIR))


def search(query: str, k: int = 3) -> str:
    if not INDEX:
        return "문서 없음"
    hits = INDEX.search(query, k)
    if not hits:  # 점수 0이면 억지로 채우지 않는다 → 모델이 '근거 없음'으로 답하게 한다
        return "관련 문서 없음"
    return "\n---\n".join(f"[{CHUNKS[i][0]}] {CHUNKS[i][1]}" for i, _ in hits)


TOOLS = [{"name": "search", "description": "문서 검색",
          "input_schema": {"type": "object", "properties": {"query": {"type": "string"}}, "required": ["query"]}}]


def ask(question: str) -> str:
    msgs = [{"role": "user", "content": question}]
    try:
        for _ in range(MAX_STEPS):  # agent loop
            r = llm.create(model=MODEL, max_tokens=2048, system=SYSTEM, tools=TOOLS, messages=msgs,
                           tag="rag_agent")
            if r.stop_reason != "tool_use":
                return llm.text_of(r)
            msgs.append({"role": "assistant", "content": r.content})
            results = [{"type": "tool_result", "tool_use_id": b.id,
                        "content": search(str((b.input or {}).get("query", "")))}  # 모델이 준 입력은 믿지 않는다
                       for b in r.content if b.type == "tool_use"]
            msgs.append({"role": "user", "content": results})
    except llm.LLMUnavailable as e:  # mock 폴백
        return f"(mock) API 실패: {e}\n\n검색 결과:\n{search(question)}"
    return "반복 한도 초과"


st.title("RAG Agent Starter")
store = Store()
q = st.text_input("질문")
if q and q != st.session_state.get("last_q"):  # 화면이 다시 그려질 때마다 API를 또 부르지 않는다
    before = summary()["usd"]
    answer = ask(q)
    s = summary()
    st.session_state.update(last_q=q, last_a=answer,
                            last_cost=f"이번 질문 ≈ ${s['usd'] - before:.4f} · 누적 ${s['usd']:.4f} "
                                      f"({s['calls']}회 호출, 캐시 읽기 {s['cache_read']:,} 토큰)")
    store.add("qa", {"q": q, "a": answer, "usd": round(s["usd"] - before, 6)})
if st.session_state.get("last_q") == q and q:
    st.write(md_safe(st.session_state.get("last_a")))
    st.caption(md_safe(st.session_state.get("last_cost")))
with st.sidebar:
    st.caption(f"문서 청크 {len(CHUNKS)}개 · 검색 {INDEX.mode if INDEX else '문서 없음'}")
    if INDEX and getattr(INDEX, "error", None):
        st.warning(f"임베딩을 쓰지 못해 BM25로 동작 중: {md_safe(INDEX.error)}")
    for path, why in SKIPPED:
        st.warning(f"건너뜀: {md_safe(path)} — {md_safe(why)}")
    st.subheader("최근 질문")
    for row in store.list("qa", 10):
        st.caption(md_safe(f"{row['ts']} · {row['data']['q'][:40]}"))
