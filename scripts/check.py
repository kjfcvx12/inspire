"""하네스: 한 번에 검사한다. 사용: python scripts/check.py [--api]
PASS/WARN/FAIL 한 줄씩 출력하고, FAIL이 하나라도 있으면 종료 코드 1. 키 값은 절대 출력하지 않는다."""
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
os.chdir(ROOT)
sys.path.insert(0, str(ROOT / "starters"))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
SKIP = {".venv", ".git", "__pycache__", "node_modules"}
levels = []


def add(level, name, detail=""):
    levels.append(level)
    print(f"{level:<4} {name}" + (f" — {detail}" if detail else ""))


def check_compile():
    files = [p for p in ROOT.rglob("*.py") if not SKIP & set(p.relative_to(ROOT).parts)]
    bad = []
    for p in files:
        try:
            compile(p.read_text(encoding="utf-8"), str(p), "exec")
        except SyntaxError as e:
            bad.append(f"{p.relative_to(ROOT)}:{e.lineno}")
    if bad:
        add("FAIL", "compile", ", ".join(bad))
    else:
        add("PASS", "compile", f"{len(files)} files")


def check_tests():
    r = subprocess.run([sys.executable, "-m", "pytest", "-q"], capture_output=True,
                       text=True, encoding="utf-8", errors="replace")
    tail = (r.stdout.strip().splitlines() or [""])[-1]
    if r.returncode == 0:
        add("PASS", "pytest", tail)
    elif r.returncode == 5:
        add("WARN", "pytest", "테스트 없음")
    else:
        fails = [ln for ln in r.stdout.splitlines() if ln.startswith(("FAILED", "ERROR"))]
        add("FAIL", "pytest", "; ".join(fails[:2]) or tail)  # 마지막 줄만으로는 원인을 알 수 없다


def check_env():
    try:
        from dotenv import load_dotenv
        load_dotenv()
    except ImportError:
        pass
    has_key = bool(os.environ.get("ANTHROPIC_API_KEY"))
    add("PASS" if has_key else "WARN", "ANTHROPIC_API_KEY",
        "set" if has_key else "missing — mock 폴백으로 동작")
    r = subprocess.run(["git", "ls-files", ".env"], capture_output=True, text=True)
    add("FAIL" if r.stdout.strip() else "PASS", ".env not committed")


def check_api():
    if not os.environ.get("ANTHROPIC_API_KEY"):
        add("WARN", "api", "키 없음 — 건너뜀")
        return
    try:
        import anthropic
        r = anthropic.Anthropic().messages.create(
            model="claude-sonnet-5-5", max_tokens=16,
            messages=[{"role": "user", "content": "ping"}])
        from common.usage_log import record
        row = record("claude-sonnet-5-5", r.usage, tag="check", stop_reason=r.stop_reason)
        add("PASS", "api", f"stop_reason={r.stop_reason}, tokens={row['input']}+{row['output']}, ≈${row['usd']}")
    except Exception as e:  # 키 노출 방지: 예외 이름만 출력
        add("FAIL", "api", type(e).__name__)


if __name__ == "__main__":
    check_compile()
    check_tests()
    check_env()
    if "--api" in sys.argv:
        check_api()
    print(f"== {levels.count('PASS')} PASS / {levels.count('WARN')} WARN / {levels.count('FAIL')} FAIL")
    sys.exit(1 if "FAIL" in levels else 0)
