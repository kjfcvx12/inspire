"""RAG + tool-calling Agent 스타터 (Streamlit). docs/ 폴더의 .txt/.md를 검색 소스로 사용."""
import glob, os
import streamlit as st
from dotenv import load_dotenv
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

load_dotenv()
MODEL = "claude-sonnet-5-5"
DOCS_DIR = os.environ.get("DOCS_DIR", "data")


def load_chunks(size=500):
    chunks = []
    for p in glob.glob(f"{DOCS_DIR}/**/*.*", recursive=True):
        if p.endswith((".txt", ".md")):
            t = open(p, encoding="utf-8").read()
            chunks += [(p, t[i:i + size]) for i in range(0, len(t), size)]
    return chunks


CHUNKS = load_chunks()
VEC = TfidfVectorizer().fit([c for _, c in CHUNKS]) if CHUNKS else None


def search(query: str, k: int = 3) -> str:
    if not VEC:
        return "문서 없음"
    sims = cosine_similarity(VEC.transform([query]), VEC.transform([c for _, c in CHUNKS]))[0]
    top = sims.argsort()[::-1][:k]
    return "\n---\n".join(f"[{CHUNKS[i][0]}] {CHUNKS[i][1]}" for i in top)


TOOLS = [{"name": "search", "description": "문서 검색",
          "input_schema": {"type": "object", "properties": {"query": {"type": "string"}}, "required": ["query"]}}]


def ask(question: str) -> str:
    try:
        import anthropic
        client = anthropic.Anthropic()
        msgs = [{"role": "user", "content": question}]
        for _ in range(5):  # agent loop
            r = client.messages.create(model=MODEL, max_tokens=1024, tools=TOOLS, messages=msgs)
            if r.stop_reason != "tool_use":
                return "".join(b.text for b in r.content if b.type == "text")
            msgs.append({"role": "assistant", "content": r.content})
            results = [{"type": "tool_result", "tool_use_id": b.id, "content": search(**b.input)}
                       for b in r.content if b.type == "tool_use"]
            msgs.append({"role": "user", "content": results})
    except Exception as e:  # mock 폴백
        return f"(mock) API 실패: {e}\n\n검색 결과:\n{search(question)}"
    return "반복 한도 초과"


st.title("RAG Agent Starter")
q = st.text_input("질문")
if q:
    st.write(ask(q))
