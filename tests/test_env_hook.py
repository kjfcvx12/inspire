"""PreToolUse 훅(.claude/hooks/block_env_read.py): .env를 읽는 호출만 막고 정상 작업은 통과시킨다."""
import json
import subprocess
import sys
from pathlib import Path

import pytest

HOOK = Path(__file__).resolve().parents[1] / ".claude" / "hooks" / "block_env_read.py"


def run_hook(tool_name: str, tool_input: dict) -> subprocess.CompletedProcess:
    payload = json.dumps({"tool_name": tool_name, "tool_input": tool_input}, ensure_ascii=False)
    return subprocess.run(
        [sys.executable, "-X", "utf8", str(HOOK)], input=payload.encode("utf-8"), capture_output=True, timeout=30
    )


BLOCKED = [
    ("Bash", {"command": "cat .env"}),
    ("Bash", {"command": 'cat ".env"'}),
    ("Bash", {"command": "wc -c < .env"}),
    ("Bash", {"command": "head -n1 projects/a/.env"}),
    ("Bash", {"command": "cp .env projects/x/.env"}),
    ("Bash", {"command": "cat .env.local"}),
    ("Bash", {"command": r"grep KEY C:\Users\강민구\Desktop\0\.env"}),
    ("PowerShell", {"command": r"Get-Content .\.env"}),
    ("Read", {"file_path": ".env"}),
    ("Read", {"file_path": "projects/x/.env"}),
    ("Read", {"file_path": r"C:\Users\강민구\Desktop\0\.env"}),
    ("Grep", {"pattern": "KEY", "path": ".env"}),
    ("Grep", {"pattern": "KEY", "glob": "**/.env"}),
]

ALLOWED = [
    ("Bash", {"command": "cat .env.example"}),
    ("Bash", {"command": "ls -a"}),
    ("Bash", {"command": "git status --short"}),
    ("Bash", {"command": "python scripts/check.py"}),
    ("Bash", {"command": "cat .gitignore"}),
    ("Bash", {"command": "grep -n envload starters/common/envload.py"}),
    ("Bash", {"command": "echo .envrc my.env"}),
    ("Read", {"file_path": "starters/common/envload.py"}),
    ("Read", {"file_path": ".env.example"}),
    ("Grep", {"pattern": r"\.env", "path": "starters"}),  # 검색어에 .env가 있어도 경로가 아니면 허용
    ("Write", {"file_path": "docs/note.md", "content": "see .env"}),  # 검사 대상 도구가 아님
]


@pytest.mark.parametrize("tool,tool_input", BLOCKED)
def test_blocks_env_access(tool, tool_input):
    result = run_hook(tool, tool_input)
    assert result.returncode == 2, (tool, tool_input, result.stderr)
    assert "차단" in result.stderr.decode("utf-8", "replace")


@pytest.mark.parametrize("tool,tool_input", ALLOWED)
def test_allows_normal_calls(tool, tool_input):
    result = run_hook(tool, tool_input)
    assert result.returncode == 0, (tool, tool_input, result.stderr)


def test_invalid_input_does_not_block():
    result = subprocess.run(
        [sys.executable, "-X", "utf8", str(HOOK)], input=b"not json", capture_output=True, timeout=30
    )
    assert result.returncode == 0
