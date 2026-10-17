"""하이브리드 검색: BM25(키워드) + 임베딩(의미)을 RRF로 합친다. common.textsearch.Index와 같은 search() 규격.

키워드 검색은 동의어('돈 돌려받기' ↔ '환불')를 못 잡고, 임베딩만 쓰면 고유명사·숫자가 흐려진다. 둘을 섞는다.
임베딩 모델을 못 불러오면(미설치·오프라인·메모리) 조용히 BM25만으로 동작하고 mode == "bm25"로 알린다.
실측(8문서·13질문, eval/retrieval_demo.jsonl): BM25 hit@3 73% / MRR 0.73 → 하이브리드(e5-small) 100% / 0.88.
한계: 의미 검색은 '문서에 없음'을 스스로 거르지 못한다(근거 없는 질문 0/2 — 유사도가 0.8~0.9로 몰려 임계값이 무의미).
그래서 min_sim 기본은 0(비활성)이고, 근거 부족 판단은 LLM 프롬프트('근거가 없으면 모른다고 답하라')가 맡는다.

    idx = build_index(chunks)                 # SEARCH_MODE=hybrid 이면 하이브리드, 기본은 bm25
    idx.search("돈 돌려받으려면?", k=3)        # [(chunk_index, score), ...]
환경변수: SEARCH_MODE(bm25|hybrid), EMBED_MODEL(기본 intfloat/multilingual-e5-small), EMBED_MIN_SIM(기본 0 = 끔)"""
import os
from typing import Callable, Optional

from .textsearch import Index

DEFAULT_MODEL = "intfloat/multilingual-e5-small"  # 같은 코퍼스에서 MiniLM-L12(multilingual)보다 순위가 정확했다
Embedder = Callable[..., "object"]  # (texts, query=False) → (n, d) numpy 배열(행이 L2 정규화돼 있어야 한다)


def sentence_transformer_embedder(model: Optional[str] = None) -> Embedder:
    from sentence_transformers import SentenceTransformer
    name = model or os.environ.get("EMBED_MODEL", DEFAULT_MODEL)
    try:
        m = SentenceTransformer(name, local_files_only=True)  # 캐시에 있으면 네트워크 없이 바로
    except Exception:
        m = SentenceTransformer(name)                          # 없으면 내려받는다(오프라인이면 여기서 실패 → BM25 폴백)
    e5 = "e5" in name.lower()  # E5 계열은 질의/문서 접두어가 없으면 품질이 떨어진다

    def embed(texts, query=False):
        pre = ("query: " if query else "passage: ") if e5 else ""
        return m.encode([pre + t for t in texts], normalize_embeddings=True, show_progress_bar=False)
    return embed


class HybridIndex:
    def __init__(self, chunks, embedder: Optional[Embedder] = None, *, min_sim: Optional[float] = None,
                 rrf_k: int = 60, pool: int = 20):
        self.chunks = list(chunks)
        self.bm25 = Index(self.chunks)
        self.rrf_k, self.pool = rrf_k, pool
        self.min_sim = float(os.environ.get("EMBED_MIN_SIM", 0.0)) if min_sim is None else min_sim
        self.error: Optional[str] = None
        self._embed, self._vecs = None, None
        if embedder is None:
            try:
                embedder = sentence_transformer_embedder()
            except Exception as e:  # 미설치·다운로드 실패·메모리 부족
                self.error = f"{type(e).__name__}: {str(e)[:100]}"
        if embedder is not None and self.chunks:
            try:
                self._vecs = embedder([t for _, t in self.chunks])
                self._embed = embedder
            except Exception as e:
                self.error = f"{type(e).__name__}: {str(e)[:100]}"

    @property
    def mode(self) -> str:
        return "hybrid" if self._vecs is not None else "bm25"

    def _dense(self, query: str):
        import numpy as np
        qv = np.asarray(self._embed([query], query=True))[0]
        sims = np.asarray(self._vecs) @ qv
        order = np.argsort(-sims)[: self.pool]
        return [(int(i), float(sims[i])) for i in order if sims[i] >= self.min_sim]

    def search(self, query: str, k: int = 3) -> list[tuple[int, float]]:
        sparse = self.bm25.search(query, self.pool)
        if self._vecs is None:
            return sparse[:k]
        fused: dict[int, float] = {}
        for ranking in (sparse, self._dense(query)):
            for rank, (i, _) in enumerate(ranking):
                fused[i] = fused.get(i, 0.0) + 1.0 / (self.rrf_k + rank + 1)
        return sorted(fused.items(), key=lambda x: -x[1])[:k]


def build_index(chunks, mode: Optional[str] = None, embedder: Optional[Embedder] = None):
    """mode: 'bm25' | 'hybrid' | None(환경변수 SEARCH_MODE, 기본 bm25). 반환 객체는 .search(q, k)와 .mode를 가진다."""
    mode = (mode or os.environ.get("SEARCH_MODE", "bm25")).lower()
    if mode == "hybrid":
        return HybridIndex(chunks, embedder)
    idx = Index(chunks)
    idx.mode = "bm25"
    idx.error = None
    return idx
