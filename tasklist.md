# Legal AI Hub — Task List

Last updated: 13 Oct 2026, 00:10 IST · Branch: `fix/submission-critical` · [Pull request #1](https://github.com/Bharambevaish/AI-for-Legal-Case/pull/1)

**Summary:** 30 of 31 bugs fixed · 1 bug pending (C9, deferred by choice) · 8 demo-day tasks pending on your laptop · 12 of 12 tests passing.

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

## 5. Demo-day tasks — on your laptop (0 of 8 done)

- [ ] Get the code: `git fetch` then `git checkout fix/submission-critical` (or merge PR #1 and `git pull`)
- [ ] In the venv: `pip install -r requirements.txt`
- [ ] Database: restore Supabase and run `schema.sql` + set your Admin role — **or** add `ALLOW_OFFLINE_ADMIN_DEMO = true` to `.streamlit/secrets.toml`
- [ ] Run `python check_setup.py --shap` — every line PASS (this is the first test with the real models)
- [ ] Try each PDF in `Model Test pdfs/`; pick the main demo file and a backup
- [ ] (Online database only) Create a pending role request from a Student account to approve live
- [ ] Record a backup screen video of the full demo
- [ ] Start with `run_demo.bat` 10 minutes early; close other apps; charger plugged in

## 6. After the demo (deferred)

- [ ] **C9** Update paper, blackbook and poster numbers; regenerate figures from `eval_harness/run_eval.py`
- [ ] Re-run `python eval_harness/run_eval.py` with the real models and record new numbers
- [ ] Confirm Module C `config.json` label count (2 or 3) on your PC
- [ ] Build a held-out test set of recent judgments
- [ ] Retrain Module B (Constitutional recall 30%) and Module C as 3-class
- [ ] Decide which of the 7 duplicate paper PDFs in `Documents/Research paper doc/` is final
- [ ] Merge PR #1 into `main`
