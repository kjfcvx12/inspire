"""START 시각 기록. 사용: python scripts/start.py
docs/decisions.md의 START 줄을 현재 시각(HH:MM)으로 바꾼다. 없으면 추가한다.
(PowerShell의 Get-Date/Set-Content는 한글 로케일·인코딩 때문에 깨질 수 있어 파이썬으로 처리한다.)"""
import re
import sys
from datetime import datetime
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
path = Path(__file__).resolve().parents[1] / "docs" / "decisions.md"
text = path.read_text(encoding="utf-8") if path.exists() else "# 결정 로그\n"
now = datetime.now().strftime("%H:%M")
new, n = re.subn(r"- \(.*?\) START", f"- ({now}) START", text, count=1)
if n == 0:
    new = text.rstrip("\n") + f"\n- ({now}) START — 시험 시작\n"
path.parent.mkdir(parents=True, exist_ok=True)
with path.open("w", encoding="utf-8", newline="\n") as f:
    f.write(new)
print(f"START = {now}")
