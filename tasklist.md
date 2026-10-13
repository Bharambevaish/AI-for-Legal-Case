# Legal AI Hub — Task List

Last updated: 14 Oct 2026, IST · Branch: `fix/submission-critical` · [Pull request #1](https://github.com/Bharambevaish/AI-for-Legal-Case/pull/1)

**Summary:** 30 of 31 bugs fixed · 1 bug pending (C9, deferred by choice) · 7 demo-day tasks pending on your laptop · 12 of 12 tests passing.

`[x]` = done · `[ ]` = pending. Tick a box when a task is finished.

---

## 1. Bugs — Critical (8 of 9 done)

- [x] **C1** Offline login could grant Admin without credentials → Admin offline only with `ALLOW_OFFLINE_ADMIN_DEMO = true`
- [x] **C2** Database rules let anyone read every user's data → per-user row-level security in `schema.sql`
- [x] **C3** Users could sign up as Admin → new users are always Student; only Admins change roles
- [x] **C4** `migration.sql` failed on reserved word `current_role` → quoted in `schema.sql`
- [x] **C5** `migration.sql` dropped all tables on re-run → `schema.sql` never drops tables
- [x] **C6** IPC→BNS translator corrupted text → single-pass translator
- [x] **C7** Models were fed BNS-translated text → models read original citations; BNS shown in its own tab
- [x] **C8** SHAP explainability claimed but missing → "AI Decision Drivers" panel implemented
- [ ] **C9** Paper/README accuracy numbers not reproducible → README fixed; **paper and blackbook deferred until after the demo**

## 2. Bugs — Major (12 of 12 done)

- [x] **M1** Duplicate history rows on every click → analysis cached per file
- [x] **M2** Unescaped document text in the page (XSS) → all text escaped
- [x] **M3** Lab chat showed literal `**bold**` → renders correctly
- [x] **M4** Judge's Case History was always empty → Judges see all predictions
- [x] **M5** Errors shown as a fake "Dismissed 70%" → clear error message instead
- [x] **M6** Rule-based fallback showed invented confidence % → labelled "rule-based estimate"
- [x] **M7** Long documents cut at 512 tokens → optional "Analyse full document" mode
- [x] **M8** Final order could leak into model input → text cut at the judgment boundary
- [x] **M9** Database health check cached forever → re-checked every 60 s
- [x] **M10** Vault showed every user's cases → own cases only (Admin/Judge see all)
- [x] **M11** Vault crashed on empty confidence → handled
- [x] **M12** Two conflicting SQL files → one `schema.sql`

## 3. Bugs — Minor (10 of 10 done)

- [x] **m1** Unused Domain/Court/Tags inputs → Domain removed; court level and tags saved
- [x] **m2** Login role picker ignored online → shown only in offline demo
- [x] **m3** `clean_legal_text` look-behind never worked → fixed
- [x] **m4** Eval harness used a different pipeline from the app → shared `prepare_document()`
- [x] **m5** Lab matched only the first section number → all numbers matched
- [x] **m6** Hard-coded admin emails in SQL → removed
- [x] **m7** Stray and duplicate files in root → moved to `Documents/` or deleted
- [x] **m8** Bloated, unpinned `requirements.txt` → only used packages, version ranges
- [x] **m9** README / agent.md / summary out of date → rewritten to match the code
- [x] **m10** No Hugging Face fallback for missing models → added

## 4. Extra work done

- [x] `tests/test_pipeline.py` — 12 regression tests
- [x] `check_setup.py` — demo readiness check
- [x] `run_demo.bat` — one-click Windows launcher
- [x] Research Vault search
- [x] Eval harness reads PDFs from the correct folder
- [x] Schema tested on PostgreSQL 16 (9 security checks pass)
- [x] Fixed after your first real run (13 Oct, 01:10): models failed to load because Module_C's `config.json` says 3 labels but its weights have 2 (app now reads the true count from the weights)
- [x] Fixed: sidebar menu showed a blank pill instead of the page names (CSS hid the menu text on newer Streamlit)
- [x] Fixed: `run_demo.bat` / `check_setup.py` now use your `.venv` folder
- [x] Large/scanned PDFs: only the first 150 pages are read, upload limit 50 MB, clear message for scanned (image-only) PDFs
- [x] Note: `Model Test pdfs/Supreme court decision.pdf` is a 696-page 1890 US law-report book, not an Indian judgment — don't use it in the demo

## 5. Demo-day tasks — on your laptop (3 of 10 done)

- [x] `.streamlit/config.toml`: `fileWatcherType = "none"` added inside the single `[server]` section (your local copy had two `[server]` sections, which is invalid)
- [ ] Get the code: `git fetch` then `git checkout fix/submission-critical` (or merge PR #1 and `git pull`)
- [ ] In the venv: `pip install -r requirements.txt`
- [x] Database: Supabase project "Ai Legal Hub" (`blxbbgvafpjtxbormpjk`) is healthy; all 6 tables and per-user security rules already exist; `admin1@legalai.in` is Admin and its email is now confirmed. **No need to run `schema.sql` before the demo.**
- [x] Run `python check_setup.py` — real models load (21 s) and predict: Criminal Law 99.6%, Allowed 71.9% on the sample case
- [ ] Free up RAM (only 0.1 GB free) and re-run `python check_setup.py --shap` — SHAP must reach PASS
- [ ] Try each PDF in `Model Test pdfs/`; pick the main demo file and a backup
- [ ] (Online database only) Create a pending role request from a Student account to approve live
- [ ] Record a backup screen video of the full demo
- [ ] Start with `run_demo.bat` 10 minutes early; close other apps; charger plugged in

## 6. After the demo (deferred)

- [ ] Optionally run `schema.sql` to switch the database rules from email-based to `user_id`-based (current rules are already safe)

- [ ] **C9** Update paper, blackbook and poster numbers; regenerate figures from `eval_harness/run_eval.py`
- [ ] Re-run `python eval_harness/run_eval.py` with the real models and record new numbers
- [ ] Confirm Module C `config.json` label count (2 or 3) on your PC
- [ ] Build a held-out test set of recent judgments
- [ ] Retrain Module B (Constitutional recall 30%) and Module C as 3-class
- [ ] Decide which of the 7 duplicate paper PDFs in `Documents/Research paper doc/` is final
- [ ] Merge PR #1 into `main`

## 7. Legal Study Assistant chatbot (started 14 Oct 2026)

Goal: a free, offline chatbot that answers law-student questions (sections, concepts, past cases with verdicts) and handles negative questions safely.

- [x] **Phase 1 – Knowledge base:** 543 IPC↔BNS rows from the official table (`knowledge/statutes.json`), 58 verified concepts (`knowledge/concepts.json`), 124 past judgments with real verdicts
- [x] **Phase 2 – Search + answer engine:** `legal_assistant.py` – intent routing (section / concept / past cases / greeting / help / off-topic / unsafe / unclear), TF-IDF search, cited answers, follow-ups
- [x] **Phase 3 – Chat UI:** IPC-BNS Lab rewritten – chat bubbles, example questions, past-case cards with verdict + final order, saves to `student_queries`
- [x] **Phase 4 – Test harness:** `eval_harness/chatbot_eval.py` + 67 questions → 100% (intent, content, case found in top 3); 21 pytest tests
- [x] **Phase 5 – Extensions:** `scripts/add_cases.py` (more judgments from CSV/PDFs); optional free LLM rewrite (Ollama / OpenAI-compatible) with offline fallback
- [x] Your laptop: `git pull`, restart the app, try the Lab page
- [x] Dataset located: Nikhil shared `labeled_case_categories.csv` (530 MB) on Google Drive; `add_cases.py` now reads it in 500-row chunks with a balanced sample (tested: ~315 MB RAM; chatbot with ~1,600 cases ~480 MB, 11 s load)
- [x] Downloaded `labeled_case_categories.csv` and added 1,000 cases (1,124 judgments in the bot)
- [ ] Optional: install Ollama + `qwen2.5:1.5b` and add `LLM_BASE_URL` / `LLM_MODEL` to `secrets.toml`
- [ ] Write 20+ new real student questions into `eval_harness/chatbot_questions.json` (the current set was used while building, so it flatters the bot)

## 8. Speed + quality round (14 Oct 2026, main agent + 2 sub-agents)

- [x] App starts fast: AI models load only on the Case Predictor page; Lab page first load ~2.5 s (was ~9 s + model load)
- [x] Chatbot search index saved to `knowledge/.index_cache.joblib` → loads in ~0.5 s (was ~9 s+ rebuild every start)
- [x] Duplicate chat messages fixed (one click = one answer)
- [x] Better ranking for multi-topic questions (e.g. "bail in a dowry death case"), passages start at word boundaries, years read from judgment text
- [x] Drive model folders checked: `Final` = same models as local; checkpoints not needed; `saved_transformer_model` is an older weaker model (62.5%)
- [x] Real validation accuracy found in Drive `trainer_state.json`: Module B (jurisdiction) 89.7% / F1 0.895, Module C (outcome) 71.6% / F1 0.764 (3 epochs)
- [ ] Your laptop: `git pull`, then `python -c "from legal_assistant import build_index_cache; build_index_cache()"` once (builds the search index, ~10–30 s), then `streamlit run app.py`
- [ ] Optional: replace `models/Module_C/Final/config.json` with the one from Drive `Module_C_Model/Final/` (correct 2-label config; removes the startup warning)
- [ ] After the demo: use the trainer_state numbers above (not 85.2%) in the paper

