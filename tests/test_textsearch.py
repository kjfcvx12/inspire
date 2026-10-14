"""common.textsearch: 한국어 질의가 조사·어미가 붙어도 검색되는지, 무관한 질의는 억지로 채우지 않는지 확인한다."""
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "starters"))
from common import textsearch  # noqa: E402

DOCS = [
    ("refund.md", "환불은 구매 후 7일 이내에 가능합니다. 환불 신청은 마이페이지에서 합니다."),
    ("ship.md", "배송은 영업일 기준 3일이 걸립니다. 제주도는 하루 더 걸립니다."),
    ("member.md", "회원 탈퇴는 고객센터로 문의해 주세요."),
]


@pytest.fixture(params=["kiwi", "bigram"])
def mode(request, monkeypatch):
    if request.param == "bigram":  # kiwipiepy 없는 환경(폴백 경로)을 강제
        monkeypatch.setattr(textsearch, "_kiwi", None)
        monkeypatch.setattr(textsearch, "_kiwi_tried", True)
    elif textsearch._get_kiwi() is None:
        pytest.skip("kiwipiepy 미설치")
    return request.param


def top_source(query, mode):
    hits = textsearch.Index(DOCS).search(query, k=1)
    return DOCS[hits[0][0]][0] if hits else None


def test_korean_query_with_particles_hits(mode):
    assert top_source("환불 기간이 어떻게 되나요?", mode) == "refund.md"
    assert top_source("배송은 며칠 걸려요", mode) == "ship.md"
    assert top_source("탈퇴하고 싶어요", mode) == "member.md"


def test_unrelated_query_returns_nothing(mode):
    assert textsearch.Index(DOCS).search("quantum chromodynamics", k=3) == []


def test_empty_and_symbol_only_do_not_crash(mode):
    assert textsearch.Index([]).search("환불") == []
    assert textsearch.Index(DOCS).search("???!!!") == []
    assert textsearch.Index(DOCS).search("") == []


def test_plain_tfidf_baseline_fails_on_korean():
    """회귀 근거: 문서엔 '배송은'만 있고 질의는 '배송'이면 기존 공백 TF-IDF는 0점이다."""
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.metrics.pairwise import cosine_similarity
    texts = [t for _, t in DOCS]
    v = TfidfVectorizer().fit(texts)
    assert cosine_similarity(v.transform(["배송 며칠 걸려요"]), v.transform(texts))[0].max() == 0


def test_common_word_alone_does_not_pull_unrelated_doc(mode):
    """'신청' 같은 흔한 단어 하나만 겹치는 무관한 질의가 문서를 끌어오지 않는다(커버리지 게이트)."""
    docs = [
        ("refund.md", "상품 수령 후 7일 이내에 환불을 신청할 수 있습니다."),
        ("ship.md", "결제 완료 후 영업일 기준 2일 내에 택배가 도착합니다."),
        ("member.md", "마이페이지에서 회원 탈퇴를 신청할 수 있습니다."),
    ]
    idx = textsearch.Index(docs)
    q = "화성 이주 신청은 어디서 하나요"
    assert idx.search(q, 3, min_coverage=0.0)                  # 게이트를 끄면 오탐이 재현된다
    assert idx.search("환불 신청 기간", 3)[0][0] == 0           # 정상 질의는 두 모드 모두 그대로 찾는다
    if mode == "kiwi":                                          # 형태소 모드 기본값(0.25)에서 오탐이 사라진다
        assert idx.search(q, 3) == []
