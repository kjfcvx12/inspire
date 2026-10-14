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
# 실측(데모 코퍼스 8문서, 양성 17·근거없음 4 질의, scripts 아래 eval 케이스 기준):
#  형태소 모드: 0~0.1 오탐 2/4 · 0.2~0.3 적중률 82% 유지·오탐 0/4 · 0.4부터 하락 → 0.25
#  bigram 모드(kiwipiepy 없음): 조사 변형 bigram이 많아 0.2부터 적중률이 53%로 급락 → 0.1(적중률 82%, 오탐 1/4)
# 재검증(해커톤식 한식 주제, 위키백과 9문서 82청크, dev 18·test 18 질의, eval/retrieval_hackathon_food.jsonl):
#  형태소 모드 0.25 → test 적중률 100% 유지(손실 없음). 0.3부터 dev 적중률 93%로 하락, 0.5는 67~80%.
#  다만 검색 단계 단독의 '근거 없음' 거르기는 코퍼스마다 편차가 크다(0.25에서 dev 1/3, test 0/3; 0.3에서 test 3/3).
#  → 이 게이트는 '적중률을 해치지 않는 안전한 최소 필터'로만 쓰고, 근거 부족 판단은 LLM 답변 단계에 맡긴다
#    (같은 코퍼스 답변 단계 실측: 근거 없는 질문 6/6 거절, 정상 질문 5/5 답변).
# 표본이 작아 새 주제에서는 eval_retrieval.py로 다시 확인할 것.
MIN_COVERAGE_MORPH = 0.25
MIN_COVERAGE_BIGRAM = 0.1
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

    def search(self, query: str, k: int = 3, min_coverage: float = None) -> list[tuple[int, float]]:
        """min_coverage: 질의어(idf 가중) 중 문서가 맞힌 비율의 하한. '신청' 같은 흔한 단어 하나만 겹쳐
        엉뚱한 문서가 올라오는 것을 막는다. 코퍼스에 없는 질의어는 가장 희귀한 단어 취급(= 못 맞힌 것으로 센다)."""
        if min_coverage is None:
            min_coverage = MIN_COVERAGE_MORPH if _get_kiwi() is not None else MIN_COVERAGE_BIGRAM
        mc = min_coverage
        q = set(tokenize(query))
        if not q:
            return []
        top_idf = max(self.idf.values(), default=1.0)
        weight = {t: self.idf.get(t, top_idf) for t in q}
        total = sum(weight.values())
        scored = []
        for i, d in enumerate(self.docs):
            norm = self.k1 * (1 - self.b + self.b * self.lens[i] / self.avg) if self.avg else self.k1
            s = sum(self.idf[t] * d[t] * (self.k1 + 1) / (d[t] + norm) for t in q if t in d)
            covered = sum(weight[t] for t in q if t in d)
            if s > 0 and covered / total >= mc:
                scored.append((i, s))
        return sorted(scored, key=lambda x: -x[1])[:k]
