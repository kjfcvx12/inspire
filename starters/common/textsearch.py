"""한국어 대응 키워드 검색(BM25). 외부 필수 의존성 없음 — kiwipiepy가 있으면 형태소, 없으면 글자 bigram으로 폴백.

기본 TF-IDF(공백 토큰)는 '환불은' ≠ '환불'이라 한국어 질의가 전부 0점이 된다. 조사·어미가 붙어도 매칭되도록
토큰화를 바꾼 것이 핵심이다.

    idx = Index([("a.md", "환불은 7일 이내에 가능합니다."), ...])
    idx.search("환불 기간이 어떻게 되나요?", k=3)   # [(chunk_index, score), ...] 점수 0인 항목은 제외
"""
import math
import re
from collections import Counter

_CONTENT_TAGS = ("NN", "NR", "NP", "VV", "VA", "XR", "SL", "SN", "SH")  # 체언·용언 어간·어근·외국어·숫자·한자
_STOP = {"하", "되", "있", "않", "이", "그", "수", "것", "어떻"}  # 의미 없는 용언 어간
_kiwi = None
_kiwi_tried = False


def _get_kiwi():
    global _kiwi, _kiwi_tried
    if not _kiwi_tried:
        _kiwi_tried = True
        try:
            from kiwipiepy import Kiwi
            _kiwi = Kiwi()
        except Exception:  # 미설치·모델 로드 실패 → bigram 폴백
            _kiwi = None
    return _kiwi


def _bigrams(text: str) -> list[str]:
    toks = []
    for run in re.findall(r"[0-9A-Za-z가-힣]+", text.lower()):
        toks += [run[i:i + 2] for i in range(len(run) - 1)] if len(run) > 1 else [run]
    return toks


def tokenize(text: str) -> list[str]:
    kiwi = _get_kiwi()
    if kiwi is None:
        return _bigrams(text)
    toks = [t.form.lower() for t in kiwi.tokenize(text) if t.tag.startswith(_CONTENT_TAGS) and t.form not in _STOP]
    return toks or _bigrams(text)  # 형태소가 하나도 안 나오면(기호만 등) 폴백


class Index:
    """청크 목록 [(출처, 텍스트)]에 대한 BM25 인덱스."""

    def __init__(self, chunks, k1: float = 1.5, b: float = 0.75):
        self.chunks = list(chunks)
        self.k1, self.b = k1, b
        self.docs = [Counter(tokenize(text)) for _, text in self.chunks]
        self.lens = [sum(d.values()) for d in self.docs]
        self.avg = (sum(self.lens) / len(self.lens)) if self.lens else 0.0
        df = Counter(t for d in self.docs for t in d)
        n = len(self.docs)
        self.idf = {t: math.log(1 + (n - f + 0.5) / (f + 0.5)) for t, f in df.items()}

    def search(self, query: str, k: int = 3) -> list[tuple[int, float]]:
        q = set(tokenize(query))
        scored = []
        for i, d in enumerate(self.docs):
            norm = self.k1 * (1 - self.b + self.b * self.lens[i] / self.avg) if self.avg else self.k1
            s = sum(self.idf[t] * d[t] * (self.k1 + 1) / (d[t] + norm) for t in q if t in d)
            if s > 0:
                scored.append((i, s))
        return sorted(scored, key=lambda x: -x[1])[:k]
