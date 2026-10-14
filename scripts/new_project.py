"""작업 폴더 생성. 사용: python scripts/new_project.py <이름> [--type rag|predict|blank] [--dest DIR] [--docker]
projects/<이름>/ 에 '그 폴더만 옮겨도 단독으로 실행·검사되는' 프로젝트를 만든다.
레포의 스타터·공통 코드·하네스(check.py 등)를 복사해 넣으므로, 이후 모든 작업은 그 폴더 안에서만 한다."""
import argparse
import re
import shutil
import sys
from importlib import metadata
from pathlib import Path
from typing import Optional

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ROOT = Path(__file__).resolve().parents[1]
MAIN_FILE = {"rag": ("starters/rag_agent/app.py", "app.py"), "predict": ("starters/predict/train.py", "train.py")}
RUN = {
    "rag": "streamlit run app.py",
    "predict": "python train.py data/<파일>.csv <타깃열>",
    "blank": "streamlit run app.py",
}
SCRIPTS = ("check.py", "cost_report.py", "start.py", "eval.py", "eval_retrieval.py")

BASE_REQS = ["anthropic", "python-dotenv", "pydantic", "pytest", "ruff", "tenacity"]
TYPE_REQS = {
    "rag": ["streamlit", "scikit-learn", "pandas", "kiwipiepy", "pypdf"],  # 형태소 검색, PDF 로딩
    "predict": ["scikit-learn", "pandas", "openpyxl"],
    "blank": ["streamlit", "pandas"],
}
OPTIONAL_REQS = {  # 주석으로만 남긴다. 필요할 때 풀어서 쓴다
    "rag": ["sentence-transformers", "plotly"],  # sentence-transformers: SEARCH_MODE=hybrid(임베딩) 때 필요
    "predict": ["lightgbm", "shap", "plotly"],
    "blank": ["plotly", "rank-bm25", "lightgbm", "kiwipiepy"],
}

BLANK_APP = '''"""빈 스타터 (Streamlit). 주제가 정해지면 이 파일을 채운다.
공통 모듈: common.llm(호출·재시도·폴백·스트리밍), common.structured(구조화 출력), common.db(SQLite)."""
import streamlit as st

st.title("TODO: 제목")
'''

RETRIEVAL_TEMPLATE = (
    "# 검색 적중률 케이스: 한 줄 = 한 케이스(JSONL). 규칙은 common/retrieval_eval.py 상단 설명 참고.\n"
    "# 실행: python scripts/eval_retrieval.py eval/retrieval.jsonl --docs data\n"
    "# 아래 샘플은 data/sample.md 용이다. 실제 문서로 바꾸면 실제 질문·근거 파일로 교체한다.\n"
    '{"q": "샘플 문서에는 무엇이 있나요?", "expect_source": "sample.md"}\n'
    '{"q": "화성 이주 정책", "expect_none": true}\n'
)

GOLDEN = {
    "rag": (
        "# 골든셋: 한 줄 = 한 케이스. 규칙은 starters/common/evalkit.py 상단 설명 참고.\n"
        "# 실행: python scripts/eval.py eval/golden.jsonl --target app.py:search\n"
        "# 이 파일은 pytest(check.py)가 오프라인 search로 돌린다. API가 필요한 답변 수준 케이스는 여기 넣지 말고\n"
        "# eval/answers.jsonl로 따로 두고 --target app.py:ask 로 돌린다(여기 넣으면 check.py가 깨진다).\n"
        "# 아래 샘플은 data/sample.md 용이다. 실제 문서로 바꾸면 이 줄도 실제 질문으로 교체한다.\n"
        '{"id": "sample-hit", "input": "샘플 문서", "expect": {"contains": ["샘플 문서입니다"]}, '
        '"tags": ["retrieval"]}\n'
    ),
    "predict": (
        "# 골든셋 템플릿. 예측 주제는 '지표 하한선'을 회귀 테스트한다.\n"
        "# 실행: python scripts/eval.py eval/golden.jsonl --target train.py:fit_and_score\n"
        '# {"id": "baseline", "input": {"path": "data/xxx.csv", "target": "y"}, '
        '"expect": {"key": "score", "range": [0.7, 1.0]}}\n'
    ),
    "blank": (
        "# 골든셋 템플릿. 규칙은 starters/common/evalkit.py 상단 설명 참고.\n"
        "# 실행: python scripts/eval.py eval/golden.jsonl --target app.py:함수이름\n"
        '# {"id": "c1", "input": "입력", "expect": {"contains": ["기대 문구"]}}\n'
    ),
}

README = """# {name}

면접 작업 폴더(유형: {kind}). 이 폴더만 있으면 실행·검사가 된다. 다른 곳으로 옮겨도 그대로 동작한다.

## 실행
```
pip install -r requirements.txt     # (uv: uv pip install -r requirements.txt)
                                    # .env는 생성 시 키트의 것이 복사돼 이미 있다(없으면 .env.example 복사)
{run}
python scripts/check.py             # 컴파일 + ruff + pytest + 환경 검사 (--api: API 실호출)
python scripts/eval.py eval/golden.jsonl --target {main}:함수   # 골든셋 평가(발표 수치의 출처)
python scripts/cost_report.py       # 실제 API 비용 리포트(logs/usage.jsonl 기준)
python scripts/eval_retrieval.py eval/retrieval.jsonl   # (rag) 검색 적중률 hit@k·MRR, bm25 vs hybrid 비교
```

## 구조
- `{main}` — 핵심 코드
- `common/llm.py` — 호출 래퍼: 재시도·mock 폴백·프롬프트 캐싱·스트리밍·비용 기록. `llm.ask()`, `llm.stream_text()`
- `common/structured.py` — 구조화 출력(pydantic 스키마 검증, 실패 시 재질문·폴백). `ask_structured()`
- `common/db.py` — SQLite 저장(`Store.add/list/kv_set`). 파일: `data/app.db`
- `common/evalkit.py`, `eval/golden.jsonl` — 골든셋 평가. `common/edgecases.py` — 엣지 입력 모음
- `common/usage_log.py` — 호출별 토큰·비용 기록(`logs/usage.jsonl`)
- `common/ui.py` — Streamlit 출력용 `md_safe()` (답변의 `~`·`$`가 취소선·수식으로 깨지는 것을 막는다)
- `common/textsearch.py` — 한국어 키워드 검색(형태소+BM25, kiwipiepy 없으면 bigram 폴백). `Index(chunks).search(q, k)`
- `common/docloader.py` — `.txt .md .pdf` → 청크(겹침, PDF는 `경로#p페이지`). 못 읽은 파일은 사유와 함께 `skipped`
- `common/embedsearch.py` — 하이브리드 검색(BM25+임베딩, RRF). `SEARCH_MODE=hybrid`로 켠다. 모델을 못 올리면 BM25로 폴백
- `common/retrieval_eval.py`, `eval/retrieval.jsonl` — 검색 적중률(hit@k·MRR)·"근거 없음" 오탐 평가
- `common/envload.py` — 이 폴더의 `.env`만 읽는다(상위 폴더를 탐색하지 않음)
- `scripts/` — `check.py`(하네스), `eval.py`, `eval_retrieval.py`, `cost_report.py`, `start.py`(시작 시각 기록)
- `tests/` — 스모크·엣지·골든 테스트부터 시작해 핵심 기능 테스트를 추가한다
- `docs/decisions.md` — 결정 로그(시각 · 결정 · 이유)

## 메모
- `.env`는 이 폴더 안의 것만 읽는다. 생성 시 키트의 `.env`가 복사됐다(키 값은 출력 안 함). 폴더째 옮겨도 따라간다.
- `.env`는 `.gitignore`에 있어 커밋되지 않는다. 폴더를 압축·공유할 때는 `.env`를 빼고 보낸다.
- 커밋 금지: `.env`, `logs/`, `.venv/`, `*.db` (`.gitignore`에 포함됨).
"""

GITIGNORE = (".env\n.venv/\n__pycache__/\n*.pyc\n.pytest_cache/\n.ruff_cache/\n.streamlit/secrets.toml\n"
             "logs/\n*.db\n")
RUFF = 'line-length = 120\nexclude = [".venv", "data", "logs"]\n\n[lint]\nselect = ["E", "F", "W"]\n'
PYTEST = "[pytest]\ntestpaths = tests\n"
DOCKERIGNORE = (".env\n.env.*\n!.env.example\n.venv/\nlogs/\n*.db\n__pycache__/\n*.pyc\n"
                ".pytest_cache/\n.ruff_cache/\n.git/\n")
_STREAMLIT_CMD = ('["streamlit", "run", "app.py", "--server.address=0.0.0.0", '
                  '"--server.port=8501", "--server.headless=true"]')
DOCKER_CMD = {  # Streamlit 유형은 8501 포트, predict는 인자가 필요해 사용법만 출력된다
    "rag": _STREAMLIT_CMD,
    "blank": _STREAMLIT_CMD,
    "predict": '["python", "train.py"]',
}
DOCKERFILE = """FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
EXPOSE 8501
ENV PYTHONUTF8=1
CMD {cmd}
"""
DOCKER_README = """
## Docker (선택, `--docker`로 생성됨)
```
docker build -t demo .                                  # 첫 빌드 약 1.5분(pip install), 이후엔 캐시
docker run --rm -p 8501:8501 --env-file .env demo       # http://localhost:8501 (키 없으면 mock 폴백)
docker run --rm demo python -m pytest -q                # 컨테이너 안 테스트
```
- `.dockerignore`가 `.env`를 이미지에서 뺀다. 키는 `--env-file`/`-e`로 실행 시에만 주입한다.
- 임베딩(`SEARCH_MODE=hybrid`)용 sentence-transformers는 이미지에 없다. 없으면 조용히 `bm25`로 동작한다.
  hybrid가 필요하면 Dockerfile의 `pip install` 뒤에 아래를 넣는다
  (빌드 약 2분, 이미지 약 3.6GB, 모델이 이미지에 들어가 오프라인에서도 동작).
  ```
  RUN pip install --no-cache-dir torch --index-url https://download.pytorch.org/whl/cpu
  RUN pip install --no-cache-dir sentence-transformers
  RUN python -c "from sentence_transformers import SentenceTransformer as S; S('intfloat/multilingual-e5-small')"
  ```
- 15분 안에 안 되면 포기하고 로컬 실행(`{run}`)으로 간다.
"""
DECISIONS = (
    "# 결정 로그\n"
    "- (HH:MM) START — 시작 시각 (`python scripts/start.py`가 현재 시각으로 교체)\n"
    "- (시각) 결정 — 이유\n"
)

TEST_IMPORTS = {  # 유형별로 필요한 import만 넣는다(미사용 import는 ruff WARN)
    "rag": "import importlib.util\nimport os\n\nimport pytest\n",
    "predict": "import importlib.util\nimport subprocess\n\nimport pytest\n",
    "blank": "",
}
TEST_HEAD = '''"""스모크·엣지·골든 테스트: 이 폴더만으로 동작하는지 확인한다. 핵심 기능 테스트는 아래에 추가한다."""
import sys
{imports}from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def test_python_files_compile():
    files = [p for p in ROOT.rglob("*.py") if ".venv" not in p.parts]
    assert files
    for p in files:
        compile(p.read_text(encoding="utf-8"), str(p), "exec")
'''
TEST_TAIL = {
    "rag": '''
from common import edgecases, evalkit, llm  # noqa: E402

_APP = None


def load_app():
    """app.py를 한 번만 불러온다(DOCS_DIR 기본값이 상대경로 'data'라서 루트에서 로드)."""
    global _APP
    if _APP is None:
        old = os.getcwd()
        os.chdir(ROOT)
        try:
            spec = importlib.util.spec_from_file_location("rag_app", ROOT / "app.py")
            _APP = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(_APP)
        finally:
            os.chdir(old)
    return _APP


def test_rag_search_returns_text():
    assert isinstance(load_app().search("test"), str)


@pytest.mark.parametrize("text", edgecases.TEXT_EDGES)
def test_search_survives_edge_inputs(text):
    assert isinstance(load_app().search(text), str)


def test_ask_falls_back_to_mock_when_api_is_down(monkeypatch, tmp_path):
    monkeypatch.setenv("USAGE_LOG_PATH", str(tmp_path / "usage.jsonl"))

    def offline():
        raise RuntimeError("offline")
    monkeypatch.setattr(llm, "get_client", offline)
    assert load_app().ask("질문").startswith("(mock)")


@pytest.mark.parametrize("text", ["", "   ", "\\n\\t"])
def test_ask_rejects_blank_question_without_calling_api(monkeypatch, text):
    def boom(*a, **k):
        raise AssertionError("빈 질문으로 API를 호출하면 안 된다")
    monkeypatch.setattr(llm, "create", boom)
    assert "질문을 입력" in load_app().ask(text)


def test_ask_rejects_overlong_question_without_calling_api(monkeypatch):
    def boom(*a, **k):
        raise AssertionError("너무 긴 질문으로 API를 호출하면 안 된다")
    monkeypatch.setattr(llm, "create", boom)
    assert "너무 깁니다" in load_app().ask("한" * 5000)


def test_golden_set_passes():
    cases = evalkit.load_golden(ROOT / "eval" / "golden.jsonl")
    assert cases, "eval/golden.jsonl에 케이스가 없습니다"
    rep = evalkit.run_eval(load_app().search, cases)
    assert rep.rate == 1.0, evalkit.to_markdown(rep)
''',
    "predict": '''

def _tiny_csv(tmp_path):
    import random
    random.seed(0)
    rows = ["x1,x2,city,y"]
    for _ in range(80):
        x1, x2 = random.random(), random.random()
        rows.append(f"{x1:.4f},{x2:.4f},{random.choice('abc')},{3 * x1 + x2:.4f}")
    csv = tmp_path / "tiny.csv"
    csv.write_text("\\n".join(rows), encoding="utf-8")
    return csv


def _load_train():
    spec = importlib.util.spec_from_file_location("train_mod", ROOT / "train.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_train_runs_on_tiny_csv(tmp_path):
    r = subprocess.run([sys.executable, str(ROOT / "train.py"), str(_tiny_csv(tmp_path)), "y"],
                       capture_output=True, text=True, encoding="utf-8", errors="replace")
    assert r.returncode == 0, r.stderr[-500:]
    assert "R2" in r.stdout


def test_fit_and_score_returns_metric_and_rejects_bad_input(tmp_path):
    train = _load_train()
    res = train.fit_and_score(str(_tiny_csv(tmp_path)), "y")
    assert res["metric"] == "r2" and res["score"] > 0.5  # y = 3*x1 + x2 는 쉽게 배워진다
    with pytest.raises(ValueError, match="타깃 열"):
        train.fit_and_score(str(_tiny_csv(tmp_path)), "no_such_col")
''',
    "blank": "",
}


def requirements(kind: str) -> str:
    def pin(pkg):
        try:
            return f"{pkg}>={metadata.version(pkg)}"
        except metadata.PackageNotFoundError:
            return pkg
    lines = [pin(p) for p in dict.fromkeys(BASE_REQS + TYPE_REQS[kind])]
    lines += ["", "# 선택(필요할 때 주석 해제)"] + [f"# {pin(p)}" for p in OPTIONAL_REQS[kind]]
    return "\n".join(lines) + "\n"


def write(path: Path, text: str):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as f:
        f.write(text)


def create(name: str, kind: str, dest: Path, env_src: Optional[Path] = None, copy_env: bool = True,
           docker: bool = False) -> Path:
    if not re.fullmatch(r"[A-Za-z0-9_-]+", name):
        raise SystemExit(f"이름은 영문/숫자/_/- 만 가능합니다: {name!r}")
    proj = dest / name
    if proj.exists():
        raise SystemExit(f"이미 있음: {proj} (덮어쓰지 않습니다)")
    ignore = shutil.ignore_patterns("__pycache__", "*.pyc")
    shutil.copytree(ROOT / "starters" / "common", proj / "common", ignore=ignore)
    (proj / "scripts").mkdir(parents=True, exist_ok=True)
    for script in SCRIPTS:
        shutil.copy2(ROOT / "scripts" / script, proj / "scripts" / script)
    if kind in MAIN_FILE:
        src, main = MAIN_FILE[kind]
        shutil.copy2(ROOT / src, proj / main)
    else:
        main = "app.py"
        write(proj / main, BLANK_APP)
    (proj / "data").mkdir(exist_ok=True)
    if kind == "rag":
        shutil.copy2(ROOT / "data" / "sample.md", proj / "data" / "sample.md")
    else:
        write(proj / "data" / ".gitkeep", "")
    shutil.copy2(ROOT / ".env.example", proj / ".env.example")
    src = env_src if env_src is not None else ROOT / ".env"
    if copy_env and src.is_file():  # 내용을 읽거나 출력하지 않고 파일째 복사한다
        shutil.copy2(src, proj / ".env")
    readme = README.format(name=name, kind=kind, run=RUN[kind], main=main)
    if docker:
        readme += DOCKER_README.format(run=RUN[kind])
        write(proj / "Dockerfile", DOCKERFILE.format(cmd=DOCKER_CMD[kind]))
        write(proj / ".dockerignore", DOCKERIGNORE)
    write(proj / "README.md", readme)
    write(proj / "requirements.txt", requirements(kind))
    write(proj / ".gitignore", GITIGNORE)
    write(proj / "ruff.toml", RUFF)
    write(proj / "pytest.ini", PYTEST)
    write(proj / "docs" / "decisions.md", DECISIONS)
    write(proj / "eval" / "golden.jsonl", GOLDEN[kind])
    if kind == "rag":
        write(proj / "eval" / "retrieval.jsonl", RETRIEVAL_TEMPLATE)
    write(proj / "tests" / "test_smoke.py", TEST_HEAD.format(imports=TEST_IMPORTS[kind]) + TEST_TAIL[kind])
    return proj


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("name")
    ap.add_argument("--type", choices=["rag", "predict", "blank"], default="blank", dest="kind")
    ap.add_argument("--dest", default=str(ROOT / "projects"))
    ap.add_argument("--no-env", action="store_true", help="키트의 .env를 복사하지 않는다")
    ap.add_argument("--docker", action="store_true", help="Dockerfile·.dockerignore를 함께 만든다(선택)")
    a = ap.parse_args()
    p = create(a.name, a.kind, Path(a.dest), copy_env=not a.no_env, docker=a.docker)
    print(f"생성: {p}")
    has_env = (p / ".env").is_file()
    print(".env: " + ("복사됨(키 값은 출력하지 않음)" if has_env else "없음 — .env.example을 복사해 키를 넣으세요"))
    print(f"다음: python {p / 'scripts' / 'check.py'}   (이후 작업은 이 폴더 안에서만)")
