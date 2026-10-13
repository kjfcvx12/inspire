"""new_project.py가 만든 폴더가 '옮겨도 단독으로' 동작하는지 검증한다.
tmp_path는 레포 밖이므로 폴더를 다른 곳으로 옮긴 상황과 같다."""
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import new_project  # noqa: E402


def run(args, cwd):
    return subprocess.run([sys.executable, *args], cwd=cwd, capture_output=True,
                          text=True, encoding="utf-8", errors="replace")


@pytest.mark.parametrize("kind", ["rag", "predict", "blank"])
def test_scaffold_runs_standalone(tmp_path, kind):
    proj = new_project.create("demo", kind, tmp_path)
    r = run(["scripts/check.py"], proj)
    assert r.returncode == 0, r.stdout[-800:]
    assert not [ln for ln in r.stdout.splitlines() if ln.startswith("FAIL")]
    assert "PASS pytest" in r.stdout and "PASS ruff" in r.stdout


def test_usage_log_stays_inside_moved_folder(tmp_path):
    proj = new_project.create("demo", "blank", tmp_path)
    code = "import sys; sys.path.insert(0, '.'); from common import usage_log; print(usage_log.log_path())"
    r = run(["-c", code], proj)
    assert r.returncode == 0, r.stderr
    assert Path(r.stdout.strip()).resolve() == (proj / "logs" / "usage.jsonl").resolve()


def test_refuses_to_overwrite_and_bad_names(tmp_path):
    new_project.create("demo", "blank", tmp_path)
    with pytest.raises(SystemExit):
        new_project.create("demo", "blank", tmp_path)
    with pytest.raises(SystemExit):
        new_project.create("../evil", "blank", tmp_path)


def test_scaffold_has_no_secrets(tmp_path):
    proj = new_project.create("demo", "rag", tmp_path)
    assert not (proj / ".env").exists()
    assert "ANTHROPIC_API_KEY=" in (proj / ".env.example").read_text(encoding="utf-8")
