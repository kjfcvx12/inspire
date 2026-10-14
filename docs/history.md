# Work History

## Rules (read first)
- Store all records in this file in **English**. Show/report to the user in **Korean**.
- **Reading:** read only the `Current State` section. It is a cumulative summary of every entry below, so it alone gives the full picture. Open the Log only when you need detail.
- **Writing:** on every update, (1) add a new entry at the top of the Log (newest first, next number), then (2) rewrite `Current State` so it folds in the new entry and still covers everything before it. Keep it short; never leave it stale.
- Date format: YYYY-MM-DD. Record what was done, the result, and what is still open. Do not store secrets (API keys, tokens).

## Current State (cumulative, as of Entry 021, 2026-10-14)

> Session wrap-up protocol: when the user writes "클리어" → update this file, run `python scripts/check.py`, commit, report state; push only on "클리어 푸시". Then the user runs `/clear`.

> Setup overview for humans: `docs/setup-summary.md` (Korean, includes optimization recommendations).

**Repo**
- Local folder `C:\Users\강민구\Desktop\0` is a git repo connected to `https://github.com/kjfcvx12/inspire` (remote `origin`).
- Only remote branch is `claude/wizardly-gates-yc1p6c` (also remote HEAD); checked out locally with tracking. No `main` branch.
- Project is an "Interview Kit" for a 2-hour vibe-coding interview (stack and rules in `CLAUDE.md`; skills `/plan`, `/present`, `/demo-ready` in `.claude/skills/`; starters in `starters/predict` and `starters/rag_agent`).
- `.vscode/`, `1.txt` (a local note) and `.playwright-mcp/` are git-ignored. `uv.lock` is committed. Entries up to 018 are on origin (pushed at the start of Entry 019); Entry 019 commits are local and not pushed (push needs "클리어 푸시").

**Python environment**
- Conda lives at `C:\ProgramData\anaconda3` and is **not on PATH**. Activate with: `conda activate work` (in Anaconda Prompt), or call `C:\ProgramData\anaconda3\envs\work\python.exe` directly.
- Environments: `base` (Python 3.13.12) and `work` (Python 3.12.15). The old 3.10 `fastapi`/`work` env and the temporary `interview` env were deleted.
- `work` has all `pyproject.toml` deps: anthropic 1.13.0, scikit-learn 1.9.1, pandas 3.0.6, streamlit 1.65.0, fastapi 0.143.0, uvicorn 0.54.0, python-dotenv 1.2.4, pytest 9.1.1.
- Extras in `work`: uv 0.13.0, langfuse 4.17.0, supabase 2.32.0, matplotlib 3.11.2. `pip check` is clean.
- Pre-installed for the interview (Entry 013): core deps `ruff` 0.17.0, `openpyxl` 3.1.5, `plotly` 7.1.0, `tenacity` 9.2.1; extras `rank-bm25` 0.2.2 (RAG), `lightgbm` 4.7.0 + `shap` 0.53.0 (prediction), `kiwipiepy` 0.24.0 (Korean tokenizing). All declared in `pyproject.toml`. Not installed on purpose: chromadb/faiss, langchain (opaque).
- Deep-learning stack (Entry 017): installed into `work` and added to `pyproject.toml` `extras`: torch 2.14.1 (CPU build; `cuda: False`), torchvision 0.29.1, torchaudio 2.11.0, transformers 5.19.0, sentence-transformers 6.1.0, accelerate 1.15.0, datasets 5.1.0, tqdm, pillow. `uv pip check` clean; torch ≈ 474 MB in site-packages, uv cache ≈ 596 MB. Suggested but not installed: faiss-cpu, pypdf, optuna, xgboost, duckdb, python-multipart, ipykernel (user did not answer).
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

**Korean retrieval fix (Entry 017)**
- Problem measured: the RAG starter's whitespace TF-IDF scored 0 for Korean queries whose words only appear with particles attached ("배송" vs "배송은").
- Fix: new `starters/common/textsearch.py` (`Index(chunks).search(q, k)`): kiwipiepy content-morpheme tokens + self-written BM25 (no new dependency); falls back to character bigrams when kiwipiepy is missing. `rag_agent/app.py` uses it and returns "관련 문서 없음" on zero score instead of padding with unrelated chunks. Scaffold README lists the module (`scripts/new_project.py`).
- `tests/test_textsearch.py` (7 tests, kiwi and bigram paths, empty/symbol-only input, plain-TF-IDF baseline = 0). 39 tests total.
- Limits: keyword-only (no synonym match; sentence-transformers hybrid not wired); only a 3-document toy corpus, so no accuracy number exists; Streamlit app not run end-to-end.

**Real-world PDF/scan check and /share-out test (Entry 021)**
- Real third-party Korean text PDFs (1 policy report, 4 Wikipedia-rendered PDFs, 2-40 pages): extraction fine, no PUA/U+FFFD/cid garbage, page self-search returns the right page; line-unwrap joins spot-checked (correct for mid-word breaks, occasional false join in caption lists). Decomposed (NFD) Hangul jamo exist in archaic-Korean quotations; added NFC normalization for file text, PDF text, OCR output and query tokenization (macOS-made files and typed queries).
- Synthetic scan variants (skew+noise+JPEG, image rotated 90 and 180, PDF /Rotate attribute, low resolution, handwriting-like jitter): Claude OCR character error rate 0-1% on 103 characters; the handwriting-like image is a font simulation, not real handwriting.
- Real images: a printed Korean + Meitei phrase chart (Wikimedia Commons, public domain) gave 12/13 phrases (the one miss is a spelling-form difference where the OCR matched the image); a real Joseon-era cursive Hangul letter scan (Commons, public domain) cannot be verified against ground truth. With the original prompt the model produced fluent archaic text of unknown fidelity; with the new prompt it marks illegible parts as `[판독불가]` (58 marks vs 2 readable words) and the loader reports "OCR 신뢰 낮음" instead of indexing guesses.
- `docloader` OCR hardening: prompt asks for `[판독불가]` / `[다른 문자]` markers instead of guessing; markers are stripped before indexing; if unreadable marks exceed 25% of (marks + words) a reliability warning is added to `skipped`; OCR pages with fewer than 6 content characters (page numbers) count as missing; the OCR cache key now includes the prompt.
- `/share-out` end-to-end test: pre-publish safety review, then one Notion private draft (`notion-create-pages`, draft mode) containing the check summary; re-fetched and rendered correctly. No secrets or personal paths in the content. Drive and Canva were not exercised. The test page remains in the user's Notion as a private draft.
- Downloaded PDFs/images were kept outside the repo in a scratch folder and read with `python -I`; nothing from them was committed.

**PDF Korean/scan handling, hackathon-style threshold check, embedding cache (Entry 020)**
- Korean PDFs (printed from HTML with Chrome, Malgun Gothic): text and table rows extract correctly. Defects found and fixed in `docloader`: (1) PDF line wraps split Korean words ("라스\n트") -> `unwrap_korean_lines` joins only after long lines whose edge characters are Hangul (headings/short lines untouched); (2) a mixed PDF silently lost its scanned pages -> reported per page in `skipped` ("텍스트 없는 쪽 누락(스캔 쪽): p2"); corrupt/encrypted PDFs get readable reasons.
- Scanned PDFs have no text layer; no Tesseract on this PC. Added opt-in `PDF_OCR=claude`: only text-less pages are sent (whole PDF as a document block, max 20 pages / 20 MB), result cached in `logs/ocr_cache/<sha1>.txt`, failures reported in `skipped` and never block other files. Live check on a scanned and a mixed PDF: both became searchable (2 calls, ~$0.02). Unit tests use fake LLM objects (`tests/test_pdf_korean.py`, 9 tests).
- Hackathon-style threshold check (topic: Korean food guide chatbot; 9 Korean Wikipedia articles, 82 chunks, `scripts/fetch_wiki_corpus.py`, `eval/retrieval_hackathon_food.jsonl`, 18 dev + 18 test queries; corpus not committed, CC BY-SA). Coverage gate 0.25: test hit@3 stays 100% (no loss); stricter gates lose hits (0.3: dev 93%; 0.5: 67-80%). Retrieval-only abstention is weak and corpus dependent (0.25: dev 1/3, test 0/3; 0.3: test 3/3), BM25 itself already hit 100% on this lexically friendly question set, hybrid gave no gain here (it did on the paraphrase-heavy toy corpus). End-to-end answers (live API): 6/6 out-of-scope questions refused, 5/5 sample in-scope questions answered. Conclusion: keep defaults (0.25 morph / 0.1 bigram) as a safe minimal filter; abstention is the LLM prompt's job.
- Embedding model: user will work on this PC, so the cached `intfloat/multilingual-e5-small` is kept. `embedsearch` now loads with `local_files_only=True` first (no network check; ~16 s cold load) and downloads only if missing; `check.py` has an `embedding cache` check (PASS when cached, WARN under `SEARCH_MODE=hybrid` when not).
- `/share-out` was only explained to the user this turn (no publish).

**Retrieval stack and project-local .env (Entry 019)**
- Scaffold `.env`: `new_project.py` copies the kit `.env` into the project folder (file copy, value never read or printed; `--no-env` skips). Code reads only the project-root `.env` via `common/envload.py` (no upward search), so moving the folder carries the key and a nested folder cannot pick up a parent's key. Tests cover copy, no-leak into other files, and no-parent-pickup.
- `kiwipiepy` and `pypdf` are core dependencies in `pyproject.toml` and active in the RAG scaffold `requirements.txt`; `sentence-transformers` is a commented optional line there.
- `common/docloader.py`: txt/md/pdf to overlapping chunks (PDF source gets `#pN`); unreadable files are returned in `skipped` with a reason (non-UTF-8, empty, no text layer, encrypted/corrupt) instead of raising.
- `common/embedsearch.py`: BM25 + embedding hybrid via reciprocal rank fusion; default model `intfloat/multilingual-e5-small` (query/passage prefixes), falls back to BM25 if the model cannot load; `SEARCH_MODE=hybrid` enables it; the Streamlit app caches the index and shows mode/skipped files in the sidebar.
- `common/retrieval_eval.py` + `scripts/eval_retrieval.py` + `eval/retrieval_demo.jsonl` (+ `data/demo_faq`, 8 docs / 13 questions). Measured: BM25 hit@3 73% / MRR 0.73, hybrid(e5-small) 100% / 0.88, hit@1 73% vs 82%. Embedding search cannot abstain on out-of-corpus questions (0/2; similarities cluster at 0.8-0.9), so abstention stays with the LLM prompt; `min_sim` defaults to 0. MiniLM-multilingual was worse and is not the default.
- Skills actually invoked on a scratch project: `/new-project` (5 PASS), `/eval` (golden 9/10 -> 10/10), `/edge-cases`, `/share-out` (safety check only). Defects they exposed: (1) a single common word ("신청") pulled an unrelated doc -> idf-weighted query-coverage gate in `textsearch` (0.25 morph / 0.1 bigram; bigram at 0.25 had dropped hit rate to 53%, caught by an existing test); (2) blank question caused an API 400 whose raw error and request id reached the UI -> `ask()` now rejects blank and >2000-char input without an API call. Prompt-injection probe (live API) refused cleanly with no key/prompt leak.
- Final live check: scaffolded project run with `SEARCH_MODE=hybrid` in Streamlit via Playwright; the paraphrase question that BM25 misses was answered from `refund.md`.

**Pre-interview verification (Entry 018)**
- Live API (real key): `check.py --api` PASS; `llm.ask`, prompt caching (2nd identical long-system call read 16,419 tokens from cache), `ask_structured` (pydantic, 1 attempt), `stream_text` all worked against `claude-sonnet-5-5`. Price table in `usage_log.PRICES` matches the official table (Sonnet 5.5 $2/$10, Opus 5.5 $4/$20, Haiku 5.5 $0.10/$0.50, cache read $0.20/$0.20/$0.01, cache write 1.25x).
- Scaffolded `rag` project run with Streamlit and driven through Playwright MCP (it started without issue): Korean question -> `search` tool call -> grounded answer with source, per-question cost, history sidebar; a fact missing from the document was answered as "not found".
- Defect found by that run: model text `2~3일` rendered as strikethrough and the `$a ... $b` cost caption rendered as math. Fix: `starters/common/ui.py` `md_safe()` applied in `rag_agent/app.py`; `tests/test_ui.py` (4 tests); re-verified in the browser.
- Reproducibility: fresh `git clone` + `uv sync` (+ `--extra extras`) passes the harness; a scaffold folder copied outside the repo installs from its `requirements.txt` into a new venv and passes its own `check.py` (19 passed).
- Config: `git push` removed and `mcp__playwright` added to `.claude/settings.json` allow list; `.gitignore` gained `.vscode/`, `1.txt`, `.playwright-mcp/`.
- Observed, not changed: scaffold `requirements.txt` has `kiwipiepy` commented out, so a fresh RAG project uses the bigram fallback unless it is enabled (its Korean quality is unmeasured).

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
- `.env` now holds a working `ANTHROPIC_API_KEY` (Entry 018 live checks passed). A scaffolded project folder that is moved elsewhere needs its own `.env` (the dotenv search only finds the kit's `.env` while the folder sits inside the kit).
- `uv.lock` / `.venv` do not exist; the real environment is conda `work`. `pip install` into `work` was used, so a fresh `uv sync` was not tested with the new deps (unverified).
- Starters were not actually run end-to-end (need a CSV / API key) — unverified.
- Runtime choice resolved by convention: commands work in conda `work` or uv `.venv`; no single mandated env.
- Origin has everything up to Entry 020. Entry 021 is committed locally and not pushed (push needs "클리어 푸시"; `git push` is not in the allow list, so a permission prompt also appears).
- Latest harness (Entry 021): kit `check.py --api` 7 PASS / 0 WARN / 0 FAIL, ruff clean, pytest 80 passed. Fresh-clone and standalone-scaffold reproduction were last verified in Entry 019 (62 / 23 passed) and not repeated since.
- Still not verified: a full 120-minute human run-through; the Haiku >100K-token price tier is not modeled in `usage_log.PRICES`; real third-party PDFs were limited to one government-style policy report and four Wikipedia-rendered PDFs (no multi-column journals, no table-heavy statements); synthetic scans are screen captures; real handwriting was only a Joseon-era brush letter (reported as unreadable, accuracy uncheckable) - modern handwriting accuracy is unknown; `/share-out` was exercised once end to end (Notion private draft only; Drive and Canva paths untested).
- Server-side refusal `fallbacks` (beta) are not enabled; refusals are surfaced as mock fallback instead.
- Session operation (discussed, nothing built): one writer session per project folder; extra sessions only read (summary) or publish finished, committed artifacts (`/share-out`). Offered but not built: read-only `scripts/status.py` and `docs/sessions.md`. Whether the interview rules allow multiple sessions is unknown.
- Tool note: the sandbox blocked a `Test-Path` on `.env`; do not rely on checking that path directly.

## Log (newest first)

### Entry 021 — 2026-10-14 — Real third-party Korean PDFs, rotated/handwritten scans, /share-out test
- User asked to check real third-party Korean PDFs and rotated/handwritten scans, and to test `/share-out`.
- Downloaded real PDFs/images (Wikipedia-rendered PDFs, a policy report, Commons images) into an isolated scratch folder; built rotated/skewed/noisy/handwriting-like scan variants; measured OCR error rates; added NFC normalization and OCR reliability handling.
- Published one Notion private draft through `/share-out` and verified it by re-reading.
- Mistakes caught: Commons returned HTTP 429 after rapid requests (backed off and retried once); my first handwriting-like image cut off the last line, which would have inflated error (regenerated with a shorter line); a baseline test assumed no normalization after normalization moved into the tokenizer (replaced with a stronger test); ruff E501 again flagged new Hangul-heavy lines.
- Open: modern real handwriting accuracy; multi-column/table-heavy PDFs; Drive/Canva share paths; push.

### Entry 020 — 2026-10-14 — Korean/scanned PDF check, hackathon-style threshold test, embedding cache
- User asked: push, check Korean PDFs and scans, test the coverage threshold on one hackathon-style topic, work with the embedding model on this PC, explain `/share-out`.
- Built Chrome-printed Korean PDFs plus scanned/mixed/encrypted/truncated variants; fixed word-splitting line wraps and silent loss of scanned pages; added opt-in Claude OCR with cache and limits.
- Ran a dev/test threshold sweep on a real Wikipedia corpus; kept the defaults and documented the weak retrieval-level abstention with the measured end-to-end answer behavior.
- Added the embedding-cache harness check and local-first model loading.
- Mistakes caught: ruff E501 counts wide (Hangul) characters, so new comments/docstrings broke the scaffold's "PASS ruff" test until shortened; the scanned-PDF fixture is a screenshot, so it only approximates real scans.
- Open: real third-party Korean PDFs and rotated/handwritten scans; 120-minute human rehearsal; `/share-out` publish only on request.

### Entry 019 — 2026-10-14 — Push, kiwipiepy default, project-local .env, retrieval stack, skill runs
- User asked for: push, enable kiwipiepy, invoke the slash skills, move `.env` inside the project, and implement the open items. Pushed Entries up to 018 first.
- Implemented PDF loading, hybrid search, retrieval hit-rate eval, env loader, coverage gate, input guard (details in Current State). Mutation checks on `embedsearch`/`docloader` each failed a test, then were reverted.
- Mistakes caught: template strings written through the shell lost backslashes twice (a broken `RETRIEVAL_TEMPLATE`; a `"\n\t"` literal that expanded to real newlines in generated tests) - fixed with file-based edits and verified in the generated output; an old test asserting "scaffold never has .env" was updated to the new intended behavior; `st.cache_resource` parameter named `_signature` would have been excluded from the cache key (renamed).
- Open: push (needs "클리어 푸시"); real Korean/scanned PDFs; coverage threshold re-check on a real corpus; embedding model download size (~470 MB) is cached on this PC only; 120-minute human rehearsal.

### Entry 018 — 2026-10-14 — Pre-interview verification pass
- User asked to proceed with the recommended order (live API, rehearsal run, fresh-environment reproduction, config cleanup).
- Live API paths verified; price table verified; scaffolded RAG app run in the browser; markdown rendering defect found and fixed with `md_safe()` + tests; fresh clone and standalone scaffold reproduced; permissions and gitignore tidied; `uv.lock` committed.
- Mistake caught: a test file written through the shell lost a backslash and failed; rewritten with the Write tool.
- Open: push (needs "클리어 푸시"), `/new-project` etc. not invoked as slash skills, kiwipiepy not enabled by default in scaffolds, no 120-minute human rehearsal.

### Entry 017 — 2026-10-14 — Deep-learning packages and Korean retrieval fix
- Answered "what to install with PyTorch"; installed torch/torchvision/torchaudio/transformers/sentence-transformers/accelerate/datasets/tqdm/pillow into conda `work` (CPU build) and added them to `pyproject.toml` extras (16 entries; dry-run resolve clean). Reported measured sizes.
- Reviewed RAG readiness: starter existed (TF-IDF + agent loop + mock fallback) but scored 0 on Korean queries. Fixed with `common/textsearch.py` (kiwipiepy + BM25, bigram fallback) and a no-result message; added 7 tests. A first baseline test was wrong (doc contained the bare token) and was corrected before commit.
- Wrap-up: `check.py` 4 PASS / 1 WARN / 0 FAIL, pytest 39 passed. Committed locally; not pushed.
- Open: hybrid embedding search, PDF loading, retrieval-hit-rate eval, and a real `streamlit run` are not done.

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
