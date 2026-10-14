"""new_project.py가 만든 폴더가 '옮겨도 단독으로' 동작하는지 검증한다.
tmp_path는 레포 밖이므로 폴더를 다른 곳으로 옮긴 상황과 같다."""
import os
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


def test_scaffold_has_no_secrets_unless_env_is_copied(tmp_path):
    proj = new_project.create("demo", "rag", tmp_path, copy_env=False)
    assert not (proj / ".env").exists()
    assert "ANTHROPIC_API_KEY=" in (proj / ".env.example").read_text(encoding="utf-8")


def test_copied_env_value_appears_nowhere_else_and_is_gitignored(tmp_path):
    secret = "sk-test-DO-NOT-LEAK-123456"
    src = tmp_path / "kit.env"
    src.write_text(f"ANTHROPIC_API_KEY={secret}\n", encoding="utf-8")
    proj = new_project.create("demo", "rag", tmp_path, env_src=src)
    leaks = [p for p in proj.rglob("*") if p.is_file() and p.name != ".env"
             and secret.encode() in p.read_bytes()]
    assert leaks == []
    assert ".env" in (proj / ".gitignore").read_text(encoding="utf-8").splitlines()


def test_env_is_copied_into_project_and_read_only_from_there(tmp_path):
    src = tmp_path / "kit.env"
    src.write_text("SCAFFOLD_ENV_PROBE=from-project\n", encoding="utf-8")
    proj = new_project.create("demo", "blank", tmp_path, env_src=src)
    assert (proj / ".env").read_bytes() == src.read_bytes()
    code = ("import sys, os; sys.path.insert(0, '.'); from common import envload; "
            "print(envload.load_env(), os.environ.get('SCAFFOLD_ENV_PROBE'))")
    r = run(["-c", code], proj)
    assert r.returncode == 0, r.stderr
    assert r.stdout.split() == ["True", "from-project"]


def test_env_not_copied_when_missing_or_disabled(tmp_path):
    src = tmp_path / "kit.env"
    src.write_text("K=v\n", encoding="utf-8")
    assert not (new_project.create("a", "blank", tmp_path, env_src=src, copy_env=False) / ".env").exists()
    assert not (new_project.create("b", "blank", tmp_path, env_src=tmp_path / "nope.env") / ".env").exists()


def test_project_does_not_pick_up_parent_env(tmp_path):
    """폴더가 다른 프로젝트 안에 중첩돼도 상위 폴더의 .env를 집어 오지 않는다(키 혼선 방지)."""
    (tmp_path / ".env").write_text("SCAFFOLD_ENV_PROBE=parent\n", encoding="utf-8")
    proj = new_project.create("demo", "blank", tmp_path, env_src=tmp_path / "nope.env")
    code = ("import sys, os; sys.path.insert(0, '.'); from common import envload; "
            "print(envload.load_env(), os.environ.get('SCAFFOLD_ENV_PROBE'))")
    env = {k: v for k, v in __import__("os").environ.items() if k != "SCAFFOLD_ENV_PROBE"}
    r = subprocess.run([sys.executable, "-c", code], cwd=proj, capture_output=True, text=True, env=env)
    assert r.returncode == 0, r.stderr
    assert r.stdout.split() == ["False", "None"]


def test_rag_scaffold_has_retrieval_eval_and_kiwipiepy_pypdf_requirements(tmp_path):
    proj = new_project.create("demo", "rag", tmp_path, copy_env=False)
    reqs = (proj / "requirements.txt").read_text(encoding="utf-8").splitlines()
    active = [ln.split(">=")[0] for ln in reqs if ln and not ln.startswith("#")]
    assert "kiwipiepy" in active and "pypdf" in active
    assert (proj / "eval" / "retrieval.jsonl").is_file() and (proj / "scripts" / "eval_retrieval.py").is_file()
    r = run(["scripts/eval_retrieval.py", "eval/retrieval.jsonl", "--mode", "bm25", "--min-hit", "1.0"], proj)
    assert r.returncode == 0, r.stdout[-600:] + r.stderr[-300:]
    assert "hit@k" in r.stdout and (proj / "logs" / "eval_retrieval.json").is_file()


def test_docker_files_only_with_flag(tmp_path):
    assert not (new_project.create("a", "rag", tmp_path, copy_env=False) / "Dockerfile").exists()
    proj = new_project.create("b", "rag", tmp_path, copy_env=False, docker=True)
    df = (proj / "Dockerfile").read_text(encoding="utf-8")
    assert "streamlit" in df and "--server.address=0.0.0.0" in df and "EXPOSE 8501" in df
    readme = (proj / "README.md").read_text(encoding="utf-8")
    assert "## Docker" in readme and "whl/cpu" in readme and "sentence-transformers" in readme
    assert "## Docker" not in (tmp_path / "a" / "README.md").read_text(encoding="utf-8")


@pytest.mark.parametrize("kind", ["rag", "predict", "blank"])
def test_dockerignore_keeps_env_out_of_image(tmp_path, kind):
    proj = new_project.create("demo", kind, tmp_path, copy_env=False, docker=True)
    lines = (proj / ".dockerignore").read_text(encoding="utf-8").splitlines()
    assert ".env" in lines and "!.env.example" in lines and lines.index(".env") < lines.index("!.env.example")
    assert "logs/" in lines and "*.db" in lines
    cmd = [ln for ln in (proj / "Dockerfile").read_text(encoding="utf-8").splitlines() if ln.startswith("CMD")]
    assert len(cmd) == 1 and ("train.py" in cmd[0] if kind == "predict" else "app.py" in cmd[0])


def test_docker_scaffold_still_passes_own_check(tmp_path):
    proj = new_project.create("demo", "rag", tmp_path, docker=True)
    r = run(["scripts/check.py"], proj)
    assert r.returncode == 0, r.stdout[-800:]


@pytest.mark.skipif(not os.environ.get("RUN_DOCKER_TESTS"),
                    reason="실제 docker build(약 1.5분, 엔진 필요)는 RUN_DOCKER_TESTS=1일 때만")
def test_docker_image_has_no_env_and_runs_pytest(tmp_path):
    secret = "sk-test-DO-NOT-LEAK-654321"
    src = tmp_path / "kit.env"
    src.write_text(f"ANTHROPIC_API_KEY={secret}\n", encoding="utf-8")
    proj = new_project.create("demo", "blank", tmp_path, env_src=src, docker=True)
    assert (proj / ".env").is_file()  # 폴더엔 .env가 있지만 이미지엔 없어야 한다
    tag = "kit-docker-test"
    b = subprocess.run(["docker", "build", "-q", "-t", tag, str(proj)], capture_output=True, text=True)
    assert b.returncode == 0, b.stderr[-600:]
    try:
        code = "import os; print(sorted(f for f in os.listdir('/app') if f.startswith('.env')))"
        r = subprocess.run(["docker", "run", "--rm", tag, "python", "-c", code], capture_output=True, text=True)
        assert r.stdout.strip() == "['.env.example']", r.stdout + r.stderr[-300:]
        t = subprocess.run(["docker", "run", "--rm", tag, "python", "-m", "pytest", "-q"],
                           capture_output=True, text=True)
        assert t.returncode == 0, t.stdout[-600:]
    finally:
        subprocess.run(["docker", "rmi", "-f", tag], capture_output=True)
