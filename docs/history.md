# Work History

## Rules (read first)
- Store all records in this file in **English**. Show/report to the user in **Korean**.
- **Reading:** read only the `Current State` section. It is a cumulative summary of every entry below, so it alone gives the full picture. Open the Log only when you need detail.
- **Writing:** on every update, (1) add a new entry at the top of the Log (newest first, next number), then (2) rewrite `Current State` so it folds in the new entry and still covers everything before it. Keep it short; never leave it stale.
- Date format: YYYY-MM-DD. Record what was done, the result, and what is still open. Do not store secrets (API keys, tokens).

## Current State (cumulative, as of Entry 016, 2026-10-14)

> Session wrap-up protocol: when the user writes "클리어" → update this file, run `python scripts/check.py`, commit, report state; push only on "클리어 푸시". Then the user runs `/clear`.

> Setup overview for humans: `docs/setup-summary.md` (Korean, includes optimization recommendations).

**Repo**
- Local folder `C:\Users\강민구\Desktop\0` is a git repo connected to `https://github.com/kjfcvx12/inspire` (remote `origin`).
- Only remote branch is `claude/wizardly-gates-yc1p6c` (also remote HEAD); checked out locally with tracking. No `main` branch.
- Project is an "Interview Kit" for a 2-hour vibe-coding interview (stack and rules in `CLAUDE.md`; skills `/plan`, `/present`, `/demo-ready` in `.claude/skills/`; starters in `starters/predict` and `starters/rag_agent`).
- `.vscode/` is untracked locally. Nothing committed or pushed by us yet.

**Python environment**
- Conda lives at `C:\ProgramData\anaconda3` and is **not on PATH**. Activate with: `conda activate work` (in Anaconda Prompt), or call `C:\ProgramData\anaconda3\envs\work\python.exe` directly.
- Environments: `base` (Python 3.13.12) and `work` (Python 3.12.15). The old 3.10 `fastapi`/`work` env and the temporary `interview` env were deleted.
- `work` has all `pyproject.toml` deps: anthropic 1.13.0, scikit-learn 1.9.1, pandas 3.0.6, streamlit 1.65.0, fastapi 0.143.0, uvicorn 0.54.0, python-dotenv 1.2.4, pytest 9.1.1.
- Extras in `work`: uv 0.13.0, langfuse 4.17.0, supabase 2.32.0, matplotlib 3.11.2. `pip check` is clean.
- Pre-installed for the interview (Entry 013): core deps `ruff` 0.17.0, `openpyxl` 3.1.5, `plotly` 7.1.0, `tenacity` 9.2.1; extras `rank-bm25` 0.2.2 (RAG), `lightgbm` 4.7.0 + `shap` 0.53.0 (prediction), `kiwipiepy` 0.24.0 (Korean tokenizing). All declared in `pyproject.toml`. Not installed on purpose: torch/sentence-transformers/chromadb/faiss (slow download), langchain (opaque).
- `pyproject.toml` has `[tool.ruff]` (line-length 120, rules E/F/W). `scripts/check.py` runs ruff as a WARN-level step (lint never blocks the flow).
- System-wide: GitHub CLI `gh` 2.102.0 (winget; not logged in), git, Node.js, VS Code. System Python is 3.14.3 (unused).

**Interview kit additions (Entry 007)**
- Harness: `scripts/check.py` (compile + pytest + env/secret checks; `--api` for a live ping; PASS/WARN/FAIL, exit 1 on FAIL; never prints key values) and `tests/test_smoke.py` (2 tests).
- Skills added: `checkpoint` (check → commit → decisions log), `timecheck` (progress vs. schedule, freeze at 85 min), `build-loop` (loop engineering: done-criterion, small slice, 3 failures/15 min → change approach), `harness` (harness engineering checklist). Updated `plan`, `present` (now 9 sections incl. AI usage, Q&A, demo-fallback), `demo-ready` (7 items), `time-plan.md` (cumulative-minute table).
- Agents added in `.claude/agents/`: `verifier` (independent verification, no edits) and `interviewer` (mock interviewer Q&A).
- `.claude/settings.json`: added `env.PYTHONUTF8=1`, allow `pip`, `conda`, `git push`; `.env` read still denied.
- `CLAUDE.md`: commands now plain `python`/`streamlit`/`pytest` (prefix `uv run` if using uv), added the ask-only-direction rule and a loop/harness/agent section. `pyproject.toml`: optional extra `extras = [langfuse, supabase, matplotlib]`. `docs/decisions.md`: START line template.
- Stored two feedback memories (ask only about direction; history.md convention).
- Real API cost tracking (Entry 008): `starters/common/usage_log.py` records every call's tokens, USD (price table dated 2026-10-06, to be re-verified) and stop_reason to `logs/usage.jsonl` (gitignored; no prompt content). `starters/rag_agent/app.py` records each call and shows per-question and cumulative cost in the UI. `scripts/cost_report.py` prints a presentation-ready table; `check.py --api` also logs its ping. `/present` now pulls the cost report into "결과·한계".

**Portable work folder (Entry 014)**
- `python scripts/new_project.py <name> --type rag|predict|blank [--dest DIR]` creates `projects/<name>/`: starter code, `common/usage_log.py`, copies of `scripts/{check,cost_report,start}.py`, `tests/test_smoke.py`, `docs/decisions.md`, `requirements.txt` (`>=` installed versions), `.env.example`, `.gitignore`, `ruff.toml`, `pytest.ini`, README. It refuses to overwrite and never copies `.env`.
- Skill `/new-project` wraps it. `CLAUDE.md` rule: all interview work happens inside `projects/<name>/`; skills' `docs/decisions.md`, `scripts/check.py`, `tests/` mean that folder's own files.
- To make copies standalone: `starters/common/usage_log.py` finds its root by the nearest `pyproject.toml`/`requirements.txt`; `rag_agent/app.py`, `check.py`, `cost_report.py` put both the folder and its parent on `sys.path`. Kit-level `check.py`/ruff/pytest skip `projects/` (each project has its own harness).
- `tests/test_new_project.py` (6 tests, 11 total) scaffolds into pytest `tmp_path` (outside the repo = "moved" case) and runs the copy's own `check.py`; mutation (old `parents[2]` root) made the log-path test fail as intended, then reverted.

**Common modules, MCP, extra skills (Entry 015)**
- `starters/common/` (copied into every scaffold): `llm.py` (tenacity retry on 429/5xx/connection only, usage recording, system-block prompt caching, mock fallback, `stream_text`, refusal → fallback; SDK's own retries off), `structured.py` (`messages.parse(output_format=Model)` + error-note re-ask + fallback; no forced `tool_choice` because Sonnet 5.5 returns 400), `db.py` (SQLite `Store`, parameterized only, no file created on read), `evalkit.py` + `scripts/eval.py` (golden JSONL: contains/regex/range/approx/judge; exit 1 below `--min-pass`; writes `logs/eval_last.json`), `edgecases.py` (`TEXT_EDGES`, `frame_edges`).
- Starters now use them: `rag_agent/app.py` (llm.create, Store history sidebar, no re-ask on rerun, tool input not trusted), `predict/train.py` (`fit_and_score()` + input validation). Scaffold adds `eval/golden.jsonl`, `scripts/eval.py`, pydantic, edge/golden/offline tests, `*.db` ignored.
- MCP: `.mcp.json` pins `@playwright/mcp@0.0.83` (Chrome) and `@upstash/context7-mcp@4.4.1`; `enabledMcpjsonServers` + allow `mcp__context7` in `.claude/settings.json`. Both packages were executed once (version/help) outside the repo. Notion, Google Drive and Canva are account-level connectors; a read-only call to each succeeded (Canva has no brand kits).
- Skills added: `/eval`, `/edge-cases`, `/share-out` (publishes to Notion/Drive/Canva only on request, after confirmation and a secrets check). `CLAUDE.md` documents flow, modules and MCP.
- Tests: `tests/test_common_modules.py` (21, fake SDK client) + scaffold tests; 32 total. Mutations (retry 4xx, retry mid-stream, drop usage record, ignore refusal) each failed a test, then reverted.

**Rehearsal (Entry 010)**
- Ran the full flow once on a dummy topic (breast-cancer classifier, no API) in a scratch copy of the kit; report in `docs/rehearsal-report.md`. Elapsed ~7 min is AI execution time, not human time (not usable as a 120-min estimate).
- Both agents were actually invoked: `verifier` found silent acceptance of nonsense inputs; `interviewer` found unreproducible presentation numbers, weak tests, training-row demo samples, and a "0 won" cost claim. A threshold decision made on one small holdout was reversed after CV.
- Kit changes from lessons: `scripts/start.py`; `check.py` shows pytest FAILED/ERROR lines; new rules in `CLAUDE.md`, `/build-loop` (evidence scripts, CV before deciding), `/harness` (value/direction assertions, mutation test, nonsense inputs), `/present` (reproducible source per number, "no record" ≠ 0, runtime vs dev cost), `verifier` (silent-nonsense check).
- Main project has a `.env` file now (content not read); `check.py` reports `ANTHROPIC_API_KEY` missing, so the key is empty/unset.

**Verified**
- All imports succeed in `work`; `python scripts/check.py` → 3 PASS / 1 WARN (no API key) / 0 FAIL; `pytest` → 2 passed.
- Negative test: a deliberately broken `.py` made the harness report FAIL and exit 1 (temp file removed).
- Cost tracking verified with a fake Anthropic client (no real API call): `ask()` → 2 rows logged, summary $0.0128 for 2×(1200 in/400 out) matches hand calculation, `cost_report.py` output correct, empty-log message OK. Harness now 3 PASS / 1 WARN / 0 FAIL, pytest 5 passed.
- Not verified: the new skills/agents were not invoked yet; `--api` path and real usage logging not run against the live API (no key); possible `max_tokens=1024` truncation with default-on thinking on Sonnet 5.5 is unmeasured (report flags `truncated` calls).

**Open items / caveats**
- `.env` exists but `ANTHROPIC_API_KEY` is empty/unset (harness WARN). The user must enter the key.
- `uv.lock` / `.venv` do not exist; the real environment is conda `work`. `pip install` into `work` was used, so a fresh `uv sync` was not tested with the new deps (unverified).
- Starters were not actually run end-to-end (need a CSV / API key) — unverified.
- Runtime choice resolved by convention: commands work in conda `work` or uv `.venv`; no single mandated env.
- Everything up to Entry 012 is pushed to `origin/claude/wizardly-gates-yc1p6c` (0aa1ede..8aa21ff). Entries 013-015 changes are uncommitted. `.vscode/` and `1.txt` stay untracked.
- Not verified: new skills (`/new-project`, `/eval`, `/edge-cases`, `/share-out`) not invoked as slash commands; real `streamlit run` and any live API call (no key) — retry/fallback/caching/streaming/structured output were tested only against a fake client, so real cache hits and `messages.parse` behavior are unconfirmed; Playwright/context7 were not started as MCP servers inside Claude Code (needs a new session + approval, Chrome install assumed); `/share-out` never publishes in tests; `pip install -r requirements.txt` into a fresh env not run.
- Server-side refusal `fallbacks` (beta) are not enabled; refusals are surfaced as mock fallback instead.
- Session operation (discussed, nothing built): one writer session per project folder; extra sessions only read (summary) or publish finished, committed artifacts (`/share-out`). Offered but not built: read-only `scripts/status.py` and `docs/sessions.md`. Whether the interview rules allow multiple sessions is unknown.
- Tool note: the sandbox blocked a `Test-Path` on `.env`; do not rely on checking that path directly.

## Log (newest first)

### Entry 016 — 2026-10-14 — Explanations and wrap-up
- Explained Playwright/context7 roles and caveats; discussed splitting work into reader / worker / external-publisher sessions (recommendation: single writer, others read-only). No code changes.
- "클리어" wrap-up: harness run, Entries 013-016 committed locally in two commits (code+config, docs). Not pushed.

### Entry 015 — 2026-10-14 — Common modules, MCP, extra skills
- User asked to connect Playwright + context7 + Notion/Drive/Canva and to implement all six suggested techniques plus the extra skill candidates.
- Built `llm`, `structured`, `db`, `evalkit`/`eval.py`, `edgecases`; wired into starters and scaffold; added `/eval`, `/edge-cases`, `/share-out`; `.mcp.json`; docs/rules updated.
- Defects found by tests while building: ruff E402/E501 in generated projects (twice), tenacity `initial` deprecation, `pandas._append` private API, noisy Streamlit warnings in `eval.py`; all fixed.
- Result: harness 4 PASS / 1 WARN (no API key) / 0 FAIL, pytest 32 passed, ruff clean; scaffolded rag project runs `eval.py` end to end.

### Entry 014 — 2026-10-14 — Self-contained work folder scaffold
- User asked for a separate folder per job so that moving only that folder yields a usable project (also asked about MCP/skills/techniques to add; answered as recommendations only, nothing built).
- Added `scripts/new_project.py`, `.claude/skills/new-project/SKILL.md`, `tests/test_new_project.py`; adjusted `usage_log.py`, `rag_agent/app.py`, `check.py`, `cost_report.py` (path assumptions), `pyproject.toml` (pytest `testpaths`, ruff exclude `projects`), `CLAUDE.md` (rule + command).
- Bugs found by the new tests while building: unused imports in generated smoke test and an E402 introduced by my `app.py` edit (both made the generated project's ruff WARN) — fixed; one test bug (`"FAIL" in stdout` matched the summary "0 FAIL").
- Result: kit harness 4 PASS / 1 WARN (no API key) / 0 FAIL, pytest 11 passed; scaffolded rag/predict/blank each reach PASS compile/ruff/pytest standalone.

### Entry 013 — 2026-10-14 — Pre-install interview packages and add lint to the harness
- User asked to install recommended packages ahead of time (interview time is scarce). Installed into conda `work`: ruff, openpyxl, plotly, tenacity, rank-bm25, lightgbm, shap, kiwipiepy. Chose lightgbm over xgboost (lighter, one comparison model is enough).
- `pyproject.toml`: ruff/openpyxl/plotly/tenacity in dependencies; rank-bm25/lightgbm/shap/kiwipiepy in `extras`; added `[tool.ruff]` config.
- `scripts/check.py`: new `check_lint()` (WARN-level, skipped with a message if ruff is missing). The first ruff run found 1 issue (multiple imports on one line in `starters/rag_agent/app.py`), fixed.
- Verified: all new packages import under `python -I`; kiwipiepy tokenizes Korean correctly from a UTF-8 file (garbling seen with `python -c` came from shell argument encoding, not the library); `pip check` clean; harness 4 PASS / 1 WARN (no API key) / 0 FAIL, pytest 5 passed.
- Not verified: starters do not use the new packages yet (BM25/LightGBM/SHAP are available but not wired in); `uv sync` from a clean checkout not run.

### Entry 012 — 2026-10-14 — Push and "클리어" wrap-up protocol
- Added a wrap-up rule to `CLAUDE.md` and memory: on "클리어" update this history file, run the harness, commit, report state and unpushed count, then the user runs `/clear`; push only on "클리어 푸시".
- Pushed the local commits to `origin/claude/wizardly-gates-yc1p6c` at the user's request (f6af838..ad54446, exit 0), then a final doc-only commit to keep this file accurate.

### Entry 011 — 2026-10-14 — Committed all changes locally
- Three logical commits (harness/cost/tests; skills/agents/rules; docs) plus this history update. Secret scan found nothing; `.env`, `logs/`, `.vscode/` were not committed. Not pushed.

### Entry 010 — 2026-10-14 — Rehearsal on a dummy topic and kit fixes
- Copied the kit to a scratch dir (removed the copied `.env` immediately, never read it), ran plan → golden tests → implementation → CV comparison → demo (AppTest) → checkpoint → verifier → presentation → interviewer → fixes → mutation test.
- Outcome: 22 tests passing, harness 3 PASS / 1 WARN / 0 FAIL; mutation (flipped probability column) made 2 tests fail as intended.
- Applied the lessons to the real kit (see Current State) and wrote `docs/rehearsal-report.md`.
- Limits: skills were followed manually (not invoked as slash commands), no live API or real Streamlit server, only a tabular/no-API topic.

### Entry 009 — 2026-10-14 — Setup summary file and optimization recommendations
- Added `docs/setup-summary.md` (Korean): environment, file map, 120-minute flow, token/time/quality optimization recommendations (Claude Code session, app/API, time, quality), exam-day checklist, open items.
- Recommendations are qualitative (no measured numbers). Notable: lower default effort from `high` to `medium`, `/clear` between phases, effort `low` + adequate `max_tokens` in the app, Haiku 5.5 for repeated tests.
- No behavior changes were applied to the kit in this entry; recommendations only.

### Entry 008 — 2026-10-14 — Real API cost tracking for the presentation
- Added `starters/common/usage_log.py` (record/summary/cost), `scripts/cost_report.py`, `tests/test_usage_log.py` (3 tests); wired logging and a cost caption into `starters/rag_agent/app.py`; `check.py --api` logs its ping; `logs/` gitignored.
- Updated `CLAUDE.md` commands, `/present` (step 7 + verification rule) and the presentation template.
- Cost estimate basis (from API skill price table, 2026-10-06): Sonnet 5.5 $2/$10 per 1M tokens in/out, cache read $0.20; typical RAG question estimated ~$0.02 (unmeasured).

### Entry 007 — 2026-10-14 — Pre-flight fixes, loop/harness engineering, agents
- Pre-flight: unified commands in `CLAUDE.md`, widened permissions, `PYTHONUTF8=1`, added `tests/test_smoke.py` and `scripts/check.py`, added optional extras to `pyproject.toml`.
- New skills: `checkpoint`, `timecheck`, `build-loop` (loop engineering), `harness` (harness engineering). Extended `plan`, `present`, `demo-ready`, `time-plan.md`; added START line to `docs/decisions.md`.
- New agents: `verifier`, `interviewer` (user asked for agents mid-task).
- Added the "ask only about direction and truly important things" rule to `CLAUDE.md` and memory.
- Verified: harness 3 PASS / 1 WARN / 0 FAIL, pytest 2 passed, negative test produced FAIL as expected.

### Entry 006 — 2026-10-14 — Created this history file
- Added `docs/history.md` with the rules above and back-filled entries 001–005.
- Added a one-line pointer in `CLAUDE.md` rules.

### Entry 005 — 2026-10-14 — Installed remaining tools
- `pip install uv` into `work` → uv 0.13.0.
- `pip install langfuse supabase matplotlib` into `work` → 4.17.0 / 2.32.0 / 3.11.2; `pip check` clean.
- `winget install GitHub.cli` → gh 2.102.0 at `C:\Program Files\GitHub CLI\gh.exe` (needs a new terminal for PATH; `gh auth login` not done).
- Open: these extras are not in `pyproject.toml`.

### Entry 004 — 2026-10-14 — Built project-matching env and renamed it to `work`
- Created conda env `interview` (Python 3.12.15) and pip-installed all deps from `pyproject.toml` (`pip install .` avoided: flat layout would break the build).
- Smoke test: imports OK, starters compile, no tests collected.
- Per user request: deleted old `work` (3.10), cloned `interview` → `work`, verified imports, deleted `interview`.

### Entry 003 — 2026-10-14 — Environment audit and rename
- Found no venv/conda active, no `.venv`, no `uv.lock`; `uv` missing; conda not on PATH but present at `C:\ProgramData\anaconda3`.
- Original conda env `fastapi` was Python 3.10.20 with only fastapi/uvicorn/python-dotenv — incompatible with `requires-python >= 3.11` and missing most deps.
- `conda activate fastapi` works only within a single shell call (each tool call is a fresh shell).
- Renamed `fastapi` → `work` via `conda create --clone` then `conda env remove` (conda has no rename).

### Entry 002 — 2026-10-14 — Project overview
- Read `README.md`, `CLAUDE.md`, `docs/decisions.md`; `git log` shows 5 kit-building commits, latest `f6af838 Add output formats and verification rules to skills`.
- Remote file list: `.claude/` (settings + 3 skills), `.env.example`, `CLAUDE.md`, `README.md`, `data/sample.md`, `docs/decisions.md`, `docs/presentation.md`, `pyproject.toml`, `starters/`.

### Entry 001 — 2026-10-14 — Connected local folder to GitHub repo
- Local folder was not a git repo (contained only an empty `.vscode/`).
- `git init`, `git remote add origin https://github.com/kjfcvx12/inspire.git`, `git fetch`.
- `git checkout -b claude/wizardly-gates-yc1p6c --track origin/claude/wizardly-gates-yc1p6c` (the only remote branch).
