"""스모크 테스트: 시작 시점부터 pytest가 초록불이어야 이후 회귀를 바로 알 수 있다."""
import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_starters_compile():
    files = list(ROOT.glob("starters/**/*.py"))
    assert files
    for p in files:
        compile(p.read_text(encoding="utf-8"), str(p), "exec")


def test_rag_search_returns_text(monkeypatch):
    monkeypatch.chdir(ROOT)  # DOCS_DIR 기본값이 상대경로 "data"
    spec = importlib.util.spec_from_file_location("rag_app", ROOT / "starters/rag_agent/app.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    assert isinstance(mod.search("test"), str)
