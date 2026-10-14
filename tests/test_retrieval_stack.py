"""docloader · embedsearch · retrieval_eval · envload. 임베딩은 가짜 임베더로 대체해 모델 다운로드 없이 검증한다."""
import sys
from pathlib import Path

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "starters"))
from common import docloader, embedsearch, envload, retrieval_eval, textsearch  # noqa: E402


@pytest.fixture(autouse=True)
def bigram_only(monkeypatch):
    """kiwipiepy 유무와 무관하게 같은 결과가 나오도록 BM25는 bigram 경로로 고정한다."""
    monkeypatch.setattr(textsearch, "_kiwi", None)
    monkeypatch.setattr(textsearch, "_kiwi_tried", True)


# ---------- docloader ----------

def make_pdf(path: Path, pages: list[str]):
    """텍스트 레이어가 있는 최소 PDF(Helvetica, ASCII). xref 오프셋을 직접 계산한다."""
    objs = ["<< /Type /Catalog /Pages 2 0 R >>"]
    kids = " ".join(f"{3 + 2 * i} 0 R" for i in range(len(pages)))
    objs.append(f"<< /Type /Pages /Kids [{kids}] /Count {len(pages)} >>")
    for i, text in enumerate(pages):
        content = f"BT /F1 12 Tf 20 100 Td ({text}) Tj ET"
        objs.append(f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 300 200] /Contents {4 + 2 * i} 0 R "
                    f"/Resources << /Font << /F1 << /Type /Font /Subtype /Type1 /BaseFont /Helvetica >> >> >> >>")
        objs.append(f"<< /Length {len(content)} >>\nstream\n{content}\nendstream")
    out, offsets = b"%PDF-1.4\n", []
    for n, body in enumerate(objs, 1):
        offsets.append(len(out))
        out += f"{n} 0 obj\n{body}\nendobj\n".encode()
    xref = len(out)
    out += f"xref\n0 {len(objs) + 1}\n0000000000 65535 f \n".encode()
    out += b"".join(f"{o:010d} 00000 n \n".encode() for o in offsets)
    out += f"trailer\n<< /Size {len(objs) + 1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n".encode()
    path.write_bytes(out)


def test_split_text_overlap_and_guards():
    chunks = docloader.split_text("a" * 100, size=40, overlap=10)
    assert [len(c) for c in chunks] == [40, 40, 40, 10]  # step 30 → 0,30,60,90
    assert chunks[0][-10:] == chunks[1][:10]
    assert docloader.split_text("   \n ") == []
    with pytest.raises(ValueError):
        docloader.split_text("x", size=10, overlap=10)


def test_load_chunks_txt_md_pdf_with_page_and_skips(tmp_path):
    (tmp_path / "a.md").write_text("환불은 7일 이내", encoding="utf-8")
    (tmp_path / "b.txt").write_bytes("한글".encode("cp949"))      # UTF-8 아님
    (tmp_path / "empty.md").write_text("  \n", encoding="utf-8")
    (tmp_path / "ignore.csv").write_text("x,y", encoding="utf-8")  # 지원 안 하는 확장자는 조용히 무시
    make_pdf(tmp_path / "g.pdf", ["Page one refund", "Page two shipping"])
    (tmp_path / "bad.pdf").write_bytes(b"not a pdf")
    chunks, skipped = docloader.load_chunks(str(tmp_path))
    srcs = [s for s, _ in chunks]
    assert any(s.endswith("a.md") for s in srcs)
    assert any(s.endswith("g.pdf#p1") for s in srcs) and any(s.endswith("g.pdf#p2") for s in srcs)
    text_p2 = next(t for s, t in chunks if s.endswith("g.pdf#p2"))
    assert "shipping" in text_p2
    reasons = {Path(p).name: why for p, why in skipped}
    assert "UTF-8" in reasons["b.txt"] and reasons["empty.md"] == "빈 파일" and "bad.pdf" in reasons
    assert "ignore.csv" not in reasons


def test_load_chunks_missing_folder_does_not_raise(tmp_path):
    chunks, skipped = docloader.load_chunks(str(tmp_path / "nope"))
    assert chunks == [] and skipped and skipped[0][1] == "폴더 없음"


def test_pdf_without_text_layer_is_reported(tmp_path):
    from pypdf import PdfWriter
    w = PdfWriter()
    w.add_blank_page(100, 100)  # 스캔본처럼 텍스트가 없다
    with open(tmp_path / "scan.pdf", "wb") as f:
        w.write(f)
    chunks, skipped = docloader.load_chunks(str(tmp_path))
    assert chunks == [] and "텍스트 없음" in skipped[0][1]


# ---------- embedsearch ----------

CHUNKS = [
    ("refund.md", "환불은 구매 후 7일 이내에 가능합니다."),
    ("ship.md", "배송은 영업일 기준 3일이 걸립니다."),
    ("member.md", "회원 탈퇴는 고객센터로 문의해 주세요."),
]
CONCEPTS = [("환불", "돈 돌려", "반품"), ("배송", "택배", "도착"), ("탈퇴", "계정 삭제")]


def fake_embedder(texts, query=False):
    """개념 사전 기반 가짜 임베딩: '돈 돌려받기'와 '환불'이 같은 축을 켠다(동의어 의미 검색을 흉내)."""
    v = np.zeros((len(texts), len(CONCEPTS)))
    for r, t in enumerate(texts):
        for c, words in enumerate(CONCEPTS):
            v[r, c] = sum(w in t for w in words)
    n = np.linalg.norm(v, axis=1, keepdims=True)
    return np.divide(v, n, out=np.zeros_like(v), where=n > 0)


def test_hybrid_finds_synonym_that_keywords_miss():
    q = "돈 돌려받으려면 어떻게 하나요"
    bm25 = embedsearch.build_index(CHUNKS, mode="bm25")
    hyb = embedsearch.build_index(CHUNKS, mode="hybrid", embedder=fake_embedder)
    assert bm25.mode == "bm25" and hyb.mode == "hybrid"
    top_bm = CHUNKS[bm25.search(q, 1)[0][0]][0] if bm25.search(q, 1) else None
    assert top_bm != "refund.md"                       # 키워드만으로는 못 찾는다(기준선)
    assert CHUNKS[hyb.search(q, 1)[0][0]][0] == "refund.md"


def test_hybrid_returns_nothing_for_unrelated_query():
    hyb = embedsearch.HybridIndex(CHUNKS, fake_embedder, min_sim=0.3)
    assert hyb.search("화성 이주 정책 qwerty", 3) == []


def test_hybrid_falls_back_to_bm25_when_embedder_breaks():
    def boom(_texts, query=False):
        raise RuntimeError("모델 로드 실패")
    idx = embedsearch.HybridIndex(CHUNKS, boom)
    assert idx.mode == "bm25" and "RuntimeError" in idx.error
    assert CHUNKS[idx.search("환불 7일", 1)[0][0]][0] == "refund.md"


def test_build_index_default_is_bm25_and_env_switch(monkeypatch):
    monkeypatch.delenv("SEARCH_MODE", raising=False)
    assert embedsearch.build_index(CHUNKS).mode == "bm25"
    monkeypatch.setenv("SEARCH_MODE", "hybrid")
    assert embedsearch.build_index(CHUNKS, embedder=fake_embedder).mode == "hybrid"


# ---------- retrieval_eval ----------

def test_evaluate_hit_mrr_and_none_cases(tmp_path):
    idx = embedsearch.build_index(CHUNKS, mode="bm25")
    cases = [
        {"q": "환불 7일", "expect_source": "refund.md"},                      # rank 1
        {"q": "배송 기간", "expect_source": "ship.md", "expect_contains": "3일"},
        {"q": "탈퇴", "expect_source": "refund.md"},                           # 일부러 틀린 기대 → 실패
        {"q": "화성 이주 qwerty", "expect_none": True},
    ]
    rep = retrieval_eval.evaluate(idx, cases, k=3)
    assert rep["positive"] == 3 and rep["hit_at_k"] == pytest.approx(2 / 3)
    assert rep["mrr"] == pytest.approx(2 / 3)       # (1 + 1 + 0) / 3
    assert rep["none_total"] == 1 and rep["none_ok"] == 1
    assert [r["ok"] for r in rep["rows"]] == [True, True, False, True]


def test_load_cases_validates(tmp_path):
    f = tmp_path / "c.jsonl"
    f.write_text('# 주석\n\n{"q": "a", "expect_source": "x.md"}\n', encoding="utf-8")
    assert len(retrieval_eval.load_cases(f)) == 1
    f.write_text('{"q": "a"}\n', encoding="utf-8")
    with pytest.raises(ValueError, match="expect"):
        retrieval_eval.load_cases(f)
    f.write_text("{broken\n", encoding="utf-8")
    with pytest.raises(ValueError, match="JSON"):
        retrieval_eval.load_cases(f)


# ---------- envload ----------

def test_envload_reads_only_project_root_env(tmp_path, monkeypatch):
    (tmp_path / "requirements.txt").write_text("", encoding="utf-8")
    (tmp_path / ".env").write_text("ENVLOAD_TEST_KEY=inside\n", encoding="utf-8")
    monkeypatch.delenv("ENVLOAD_TEST_KEY", raising=False)
    monkeypatch.setattr(envload, "ROOT", tmp_path)
    assert envload.load_env() is True
    import os
    assert os.environ["ENVLOAD_TEST_KEY"] == "inside"


def test_envload_does_not_override_and_survives_missing_file(tmp_path, monkeypatch):
    (tmp_path / ".env").write_text("ENVLOAD_TEST_KEY=file\n", encoding="utf-8")
    monkeypatch.setenv("ENVLOAD_TEST_KEY", "already")
    monkeypatch.setattr(envload, "ROOT", tmp_path)
    envload.load_env()
    import os
    assert os.environ["ENVLOAD_TEST_KEY"] == "already"
    monkeypatch.setattr(envload, "ROOT", tmp_path / "no_such_dir")
    assert envload.load_env() is False
