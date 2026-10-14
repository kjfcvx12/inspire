"""분리형(NFD) 한글 입력이 조합형으로 정규화돼 검색에 잡히는지. macOS 파일·일부 PDF 대응."""
import sys
import unicodedata
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "starters"))
from common import docloader, textsearch  # noqa: E402


def test_nfc_composes_decomposed_hangul():
    composed = "환불은 7일 이내"
    decomposed = unicodedata.normalize("NFD", composed)
    assert decomposed != composed and len(decomposed) > len(composed)
    assert docloader.nfc(decomposed) == composed


def test_text_file_in_nfd_is_loaded_composed_and_searchable(tmp_path, monkeypatch):
    monkeypatch.setattr(textsearch, "_kiwi", None)       # 형태소 분석기 유무와 무관하게 bigram 경로로 고정
    monkeypatch.setattr(textsearch, "_kiwi_tried", True)
    text = "환불은 구매 후 7일 이내에 가능합니다."
    (tmp_path / "a.txt").write_text(unicodedata.normalize("NFD", text), encoding="utf-8")
    chunks, skipped = docloader.load_chunks(str(tmp_path))
    assert skipped == [] and chunks[0][1] == text
    hits = textsearch.Index(chunks).search("환불 7일", 1)
    assert hits and hits[0][0] == 0


def test_index_built_from_nfd_text_matches_composed_query(monkeypatch):
    """로더를 거치지 않고 NFD 문자열을 바로 색인해도 토크나이저가 정규화하므로 조합형 질의가 잡힌다."""
    monkeypatch.setattr(textsearch, "_kiwi", None)
    monkeypatch.setattr(textsearch, "_kiwi_tried", True)
    nfd = unicodedata.normalize("NFD", "환불은 구매 후 7일 이내에 가능합니다.")
    hits = textsearch.Index([("a", nfd)]).search("환불", 1)
    assert hits and hits[0][0] == 0


def test_nfd_query_matches_composed_documents(monkeypatch):
    monkeypatch.setattr(textsearch, "_kiwi", None)
    monkeypatch.setattr(textsearch, "_kiwi_tried", True)
    idx = textsearch.Index([("a", "환불은 구매 후 7일 이내에 가능합니다.")])
    q = unicodedata.normalize("NFD", "환불 7일")
    assert idx.search(q, 1) and idx.search(q, 1)[0][0] == 0
