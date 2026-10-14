"""PreToolUse 훅: 비밀값이 든 .env 파일을 읽는 도구 호출을 막는다. 종료 코드 2 = 차단.

permissions.deny의 Read(.env)는 Read 도구만 막으므로, 셸(Bash/PowerShell)과 Grep 호출도 여기서 검사한다.
.env.example/.sample/.template은 허용한다. 한계: 변수·와일드카드·스크립트 내부 접근(`cat .e*`,
`python -c "open('.'+'env')"`)은 문자열 검사로 잡을 수 없다. 우발적 노출을 막는 용도이며 보안 경계가 아니다.
"""
import json
import re
import sys

ENV_RE = re.compile(r"(?<![\w.-])\.env(?![\w-]|\.(?:example|sample|template)\b)", re.IGNORECASE)


def targets(payload: dict) -> list[str]:
    name = payload.get("tool_name", "")
    tool_input = payload.get("tool_input") or {}
    if name in ("Bash", "PowerShell"):
        return [str(tool_input.get("command", ""))]
    if name == "Read":
        return [str(tool_input.get("file_path", ""))]
    if name == "Grep":
        return [str(tool_input.get("path", "")), str(tool_input.get("glob", ""))]
    return []


def main() -> int:
    try:
        payload = json.loads(sys.stdin.buffer.read().decode("utf-8", "replace"))
    except ValueError:
        return 0  # 입력을 해석할 수 없으면 막지 않는다(훅 오류로 모든 작업이 멈추지 않게)
    for text in targets(payload):
        if ENV_RE.search(text):
            sys.stderr.write(
                "차단: .env(비밀값 파일)를 읽는 호출입니다. 키 값이 필요하면 사용자가 직접 확인하세요. "
                ".env.example은 읽을 수 있습니다.\n"
            )
            return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
