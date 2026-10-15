"""선택 서비스(Langfuse, Supabase) 연결 확인. 사용: python scripts/check_services.py
읽기 전용 확인만 한다(테이블 생성·쓰기 없음). 키 값과 응답 본문은 출력하지 않는다. 값이 비어 있으면 SKIP."""
import base64
import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
os.chdir(ROOT)
sys.path[:0] = [str(ROOT), str(ROOT / "starters")]
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from common.envload import load_env  # noqa: E402

levels = []


def add(level, name, detail=""):
    levels.append(level)
    print(f"{level:<4} {name}" + (f" — {detail}" if detail else ""))


def check_langfuse():
    pk, sk = os.environ.get("LANGFUSE_PUBLIC_KEY", ""), os.environ.get("LANGFUSE_SECRET_KEY", "")
    host = os.environ.get("LANGFUSE_HOST", "https://cloud.langfuse.com")
    if not (pk and sk):
        add("SKIP", "langfuse", "LANGFUSE_PUBLIC_KEY/SECRET_KEY 비어 있음")
        return
    if not pk.startswith("pk-lf-") or not sk.startswith("sk-lf-"):
        add("WARN", "langfuse 키 형식", "pk-lf-/sk-lf- 로 시작하지 않음(공백·따옴표 확인)")
    try:
        from langfuse import Langfuse
    except ImportError:
        add("FAIL", "langfuse", "패키지 미설치")
        return
    try:
        ok = Langfuse(public_key=pk, secret_key=sk, host=host).auth_check()
    except Exception as e:  # 메시지에 값이 섞일 수 있어 종류만 출력
        add("FAIL", "langfuse 인증", f"{type(e).__name__} (host={host}, 지역이 맞는지 확인)")
        return
    add("PASS" if ok else "FAIL", "langfuse 인증", f"host={host}" if ok else f"인증 거부 (host={host}, 지역·키 확인)")


def _jwt_role(token: str) -> str:
    try:
        payload = token.split(".")[1]
        payload += "=" * (-len(payload) % 4)
        return json.loads(base64.urlsafe_b64decode(payload)).get("role", "")
    except Exception:
        return ""


def check_supabase():
    url, key = os.environ.get("SUPABASE_URL", "").strip(), os.environ.get("SUPABASE_KEY", "").strip()
    if not (url and key):
        add("SKIP", "supabase", "SUPABASE_URL/SUPABASE_KEY 비어 있음")
        return
    if not url.startswith("https://") or url.rstrip("/").count("/") > 2:
        add("FAIL", "supabase URL 형식", "https://<프로젝트ID>.supabase.co 형태여야 함(경로 없이)")
        return
    if key.startswith("sb_secret_") or _jwt_role(key) == "service_role":
        add("WARN", "supabase 키 종류", "secret/service_role 키로 보임 — RLS를 우회하므로 publishable(anon) 키 권장")
    req = urllib.request.Request(url.rstrip("/") + "/rest/v1/__check_nonexistent__?select=*",
                                 headers={"apikey": key})
    try:
        urllib.request.urlopen(req, timeout=10)
        add("PASS", "supabase Data API", "응답 200")
        return
    except urllib.error.HTTPError as e:
        status = e.code
        try:
            code = json.loads(e.read().decode("utf-8", "replace")).get("code", "")
        except Exception:
            code = ""
    except Exception as e:
        add("FAIL", "supabase 접속", f"{type(e).__name__} — 일시중지(paused)·URL 오타·네트워크 확인")
        return
    if status == 404 and code == "PGRST205":
        add("PASS", "supabase Data API", "도달·키 수락 (테스트 테이블이 없다는 응답 PGRST205는 정상)")
    elif status in (401, 403):
        add("FAIL", "supabase 인증", f"HTTP {status} {code} — 키가 틀렸거나 키 종류 확인")
    else:
        add("FAIL", "supabase Data API", f"HTTP {status} {code} — Data API 활성화 여부 확인")


if __name__ == "__main__":
    if not load_env():
        print(".env 없음 또는 python-dotenv 미설치")
    check_langfuse()
    check_supabase()
    n = {k: levels.count(k) for k in ("PASS", "SKIP", "WARN", "FAIL")}
    print(f"== {n['PASS']} PASS / {n['SKIP']} SKIP / {n['WARN']} WARN / {n['FAIL']} FAIL")
    sys.exit(1 if "FAIL" in levels else 0)
