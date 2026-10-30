# Security Review — OWASP Top 10 (2021)

**Project:** Legal AI Hub (`app.py`, `legal_assistant.py`, Supabase project "Ai Legal Hub")
**Date:** 30 October 2026  **Branch:** `fix/submission-critical`

**Scope:** the Streamlit app code, its configuration, Python dependencies, git history, and the live Supabase database (tables, row-level security, functions, Auth settings).

**Result:** 14 issues found. 12 are fixed in the code, configuration and live database, and 2 need a setting changed in the Supabase dashboard. After the fixes, `pip-audit` reports 0 known vulnerable packages, and 8 of 8 database attack tests are blocked. 63 automated tests pass, including 11 new security tests.

## Findings

| # | OWASP | Severity | Problem | Fix | Status |
|---|---|---|---|---|---|
| 1 | A01 Broken Access Control | **High** | A role-upgrade request could carry **someone else's email**. The Admin would see "approve victim@x as Admin", but approving changed the role of the attacker's own account. | The database insert rule now requires the request email to match the signed-in user's email. | Fixed (live DB) |
| 2 | A03 Injection (XSS) | **High** | The Admin "Role Requests" page inserted `current_role`, `requested_role` and date values from the database into raw HTML. The database accepted **any text** in `current_role`, so a user could store a script that runs in the Admin's browser. | All values are HTML-escaped (`esc()`), and the database only allows the 4 real role names. | Fixed (code + live DB) |
| 3 | A01 Broken Access Control | Medium | A user's role was read once at sign-in, so an Admin's demotion only took effect after the user signed out. | The role is re-read from `profiles` at least every 60 s (`refresh_role()`). | Fixed |
| 4 | A01 Broken Access Control | Low | The Admin page was hidden only by the menu. Approvals also didn't check that the request was still pending or that the role was valid. | Page-level Admin check; approve/reject only `pending` rows; unknown roles can't be approved. | Fixed |
| 5 | A03 Injection (XSS) | Low | Sidebar role, user initial and vault dates were also put into HTML without escaping. | Escaped. | Fixed |
| 6 | A04 Insecure Design | Low | There was no limit on chatbot questions, vault search, tags or stored text, and a user could flood the Admin queue with requests. | Input caps (1,000 / 100 / 200 characters), a database length check on stored chatbot text, and one pending request per user. | Fixed (code + live DB) |
| 7 | A05 Security Misconfiguration | Medium | Streamlit shows **full stack traces** to visitors by default, and 10 error messages printed raw exception text (database details, internal paths). | `showErrorDetails = "none"`, developer toolbar hidden, XSRF/CORS protection set explicitly. Users now see a generic message and the details go to the server log (`db_error()`). | Fixed |
| 8 | A05 Security Misconfiguration | Medium | 4 `SECURITY DEFINER` database functions could be called by **anonymous** visitors through the public API (`/rest/v1/rpc/...`). | `EXECUTE` revoked from anonymous users; the two trigger functions can't be called by anyone. | Fixed (live DB) |
| 9 | A06 Vulnerable Components | Medium | `requirements.txt` allowed old versions with **72 known vulnerabilities** (torch 2.2, transformers 4.40, streamlit 1.40, scikit-learn 1.4). | Minimum versions raised above the fixes: streamlit ≥ 1.54, torch ≥ 2.13, transformers ≥ 5.10, scikit-learn ≥ 1.5. | Fixed |
| 10 | A07 Auth Failures | Medium | The app had no brute-force protection. Raw sign-in and sign-up errors revealed whether an email was registered, and 6-character passwords were accepted. | Lock-out after 5 failed attempts (60 s); one generic error message; new passwords need 8+ characters with a letter and a digit; email format check; the session uses the verified email from Supabase. | Fixed |
| 11 | A07 Auth Failures | Medium | Supabase **leaked-password protection** is off. | Dashboard: Authentication → Providers/Policies → enable "Leaked password protection". | **Manual** |
| 12 | A07 Auth Failures | Low | The Supabase minimum password length is still the default (6). | Dashboard: Authentication → set minimum password length to 8; keep "Confirm email" on. | **Manual** |
| 13 | A08 Integrity Failures | Low | Model loading could fall back to pickle `.bin` weights, which can run code when loaded. | `use_safetensors=True`. | Fixed |
| 14 | A09 Logging & Monitoring | Medium | Security events weren't logged. | `logs/security.log` and the terminal log sign-ins, failures, lock-outs, sign-ups, role requests, approvals and rejections, role changes and blocked page access. | Fixed |

### Categories checked with no issue found
- **A02 Cryptographic Failures:** passwords are hashed by Supabase Auth, the database connection uses HTTPS, and no keys were found in any of the 14 commits in git history. `secrets.toml` and `.env` are git-ignored. When deploying, serve the app over HTTPS (Streamlit Cloud does this).
- **A03 SQL injection:** no SQL strings are built. Queries go through the Supabase API, the vault search input is sanitised, and chatbot text is shown as plain text.
- **A10 SSRF:** users can't make the server request any URL. The Supabase and optional LLM addresses come only from `secrets.toml`.
- **Row-level security:** enabled on all 6 tables. Users read only their own rows (Admin/Judge read all), and a Student can't change their own role (trigger + policy).

### Accepted risks
- **Offline demo mode** lets anyone in without a password when the database is down. No data can be reached in that mode and Admin is blocked unless `ALLOW_OFFLINE_ADMIN_DEMO = true`. This is kept for live demos.
- **Lock-out is per browser session,** so it can be reset with a new session. Supabase Auth's own server-side rate limits cover the sign-in endpoint.
- **Signed-in users can call `is_admin()` / `current_user_role()`.** The row-level security policies need them, and they only return the caller's own role.
- **The chatbot index cache** (`knowledge/.index_cache.joblib`) is a pickle file. It's built locally and never downloaded, so changing it would already require write access to the project folder.
- **The live database still uses email-based ownership.** `schema.sql` contains the stricter `user_id`-based version for a future upgrade.

## How the fixes were verified
- `python -m pytest tests -q`: **63 passed** (11 new tests in `tests/test_security.py`: escaping, role whitelist, password policy, lock-out, URL access to the Admin page, config, git-ignore, dependency floors, safetensors).
- 8 database attacks run against `schema.sql` on PostgreSQL 16, all blocked: spoofed email, HTML in a role, request for another user, a second pending request, a Student making themself Admin, calling a trigger function, a 5,000-character query, and an anonymous call to `is_admin()`. A valid request is still accepted.
- Supabase security advisor after the fixes: the "anonymous can execute SECURITY DEFINER" warnings are gone. Remaining items are #11 and #12 above (manual) and the accepted helper-function note.
- `pip-audit -r requirements.txt`: no known vulnerabilities.

## Files changed
`app.py`, `.streamlit/config.toml`, `requirements.txt`, `schema.sql`, `.gitignore`, new `security_hardening.sql` (already applied to the live database), new `tests/test_security.py`, this report.
