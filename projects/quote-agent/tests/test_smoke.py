"""스모크·엣지·골든 테스트: 이 폴더만으로 동작하는지 확인한다. 핵심 기능 테스트는 아래에 추가한다."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def test_python_files_compile():
    files = [p for p in ROOT.rglob("*.py") if ".venv" not in p.parts]
    assert files
    for p in files:
        compile(p.read_text(encoding="utf-8"), str(p), "exec")
