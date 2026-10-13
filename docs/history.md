# Work History

## Rules (read first)
- Store all records in this file in **English**. Show/report to the user in **Korean**.
- **Reading:** read only the `Current State` section. It is a cumulative summary of every entry below, so it alone gives the full picture. Open the Log only when you need detail.
- **Writing:** on every update, (1) add a new entry at the top of the Log (newest first, next number), then (2) rewrite `Current State` so it folds in the new entry and still covers everything before it. Keep it short; never leave it stale.
- Date format: YYYY-MM-DD. Record what was done, the result, and what is still open. Do not store secrets (API keys, tokens).

## Current State (cumulative, as of Entry 010, 2026-10-14)

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
- System-wide: GitHub CLI `gh` 2.102.0 (winget; not logged in), git, Node.js, VS Code. System Python is 3.14.3 (unused).

**Interview kit additions (Entry 007)**
- Harness: `scripts/check.py` (compile + pytest + env/secret checks; `--api` for a live ping; PASS/WARN/FAIL, exit 1 on FAIL; never prints key values) and `tests/test_smoke.py` (2 tests).
- Skills added: `checkpoint` (check → commit → decisions log), `timecheck` (progress vs. schedule, freeze at 85 min), `build-loop` (loop engineering: done-criterion, small slice, 3 failures/15 min → change approach), `harness` (harness engineering checklist). Updated `plan`, `present` (now 9 sections incl. AI usage, Q&A, demo-fallback), `demo-ready` (7 items), `time-plan.md` (cumulative-minute table).
- Agents added in `.claude/agents/`: `verifier` (independent verification, no edits) and `interviewer` (mock interviewer Q&A).
- `.claude/settings.json`: added `env.PYTHONUTF8=1`, allow `pip`, `conda`, `git push`; `.env` read still denied.
- `CLAUDE.md`: commands now plain `python`/`streamlit`/`pytest` (prefix `uv run` if using uv), added the ask-only-direction rule and a loop/harness/agent section. `pyproject.toml`: optional extra `extras = [langfuse, supabase, matplotlib]`. `docs/decisions.md`: START line template.
- Stored two feedback memories (ask only about direction; history.md convention).
- Real API cost tracking (Entry 008): `starters/common/usage_log.py` records every call's tokens, USD (price table dated 2026-10-06, to be re-verified) and stop_reason to `logs/usage.jsonl` (gitignored; no prompt content). `starters/rag_agent/app.py` records each call and shows per-question and cumulative cost in the UI. `scripts/cost_report.py` prints a presentation-ready table; `check.py --api` also logs its ping. `/present` now pulls the cost report into "결과·한계".

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
- `.env` not created yet. Copy `.env.example` to `.env` and fill `ANTHROPIC_API_KEY` (user must enter keys).
- Starters were not actually run end-to-end (need a CSV / API key) — unverified.
- Runtime choice resolved by convention: commands work in conda `work` or uv `.venv`; no single mandated env.
- All kit changes are uncommitted local edits (plus untracked `.vscode/`); nothing pushed.
- Tool note: the sandbox blocked a `Test-Path` on `.env`; do not rely on checking that path directly.

## Log (newest first)

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
