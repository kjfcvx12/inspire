"""환경변수 로딩. 프로젝트 루트(requirements.txt/pyproject.toml이 있는 가장 가까운 폴더)의 .env만 읽는다.
python-dotenv의 기본 동작(상위 폴더를 끝까지 탐색)은 폴더를 옮기거나 중첩하면 엉뚱한 .env를 집어 올 수 있어 쓰지 않는다.
이미 설정된 환경변수는 덮어쓰지 않는다."""
from pathlib import Path

from .usage_log import ROOT


def env_path() -> Path:
    return ROOT / ".env"


def load_env() -> bool:
    """프로젝트 .env를 읽었으면 True. python-dotenv가 없거나 파일이 없으면 False(조용히 mock 폴백으로 간다)."""
    p = env_path()
    if not p.is_file():
        return False
    try:
        from dotenv import load_dotenv
    except ImportError:
        return False
    return bool(load_dotenv(p, override=False))
