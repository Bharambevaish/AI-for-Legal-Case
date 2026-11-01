"""Security regression tests (OWASP Top 10 review, Oct 2026).

Run from the project root:   python -m pytest tests -q
"""
import os
import sys
import time
import tomllib

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
os.chdir(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import app  # noqa: E402

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))


# A03 Injection / XSS ────────────────────────────────────────────────────

def test_esc_neutralises_html():
    out = app.esc('<img src=x onerror=alert(1)>')
    assert "<" not in out and ">" not in out
    assert app.esc(None) == ""


def test_safe_role_rejects_unknown_values():
    assert app.safe_role("Admin") == "Admin"
    for bad in ("<script>", "SuperAdmin", "", None, "admin"):
        assert app.safe_role(bad) == "Student"


def test_no_unescaped_db_values_in_role_request_card():
    src = open(os.path.join(ROOT, "app.py"), encoding="utf-8").read()
    start = src.index("def render_role_requests")
    card_start = src.index('<div class="pro-card" style="margin-bottom: 1rem;">', start)
    block = src[card_start:src.index("unsafe_allow_html=True", card_start)]   # the raw-HTML card only
    for raw in ("{curr_r}", "{req_r}", "{r_date}", "{u_email}"):
        assert raw not in block, f"{raw} is rendered without escaping"


# A07 Identification and authentication failures ─────────────────────────

def test_password_policy():
    assert app.password_problem("short1")            # too short
    assert app.password_problem("longpassword")      # no digit
    assert app.password_problem("1234567890")        # no letter
    assert app.password_problem("Legal2026ok") is None


def test_email_format():
    assert app.EMAIL_RE.match("name@firm.com")
    for bad in ("name", "name@", "@firm.com", "a b@firm.com", "name@firm"):
        assert not app.EMAIL_RE.match(bad)


def test_login_lockout_after_repeated_failures():
    app.st.session_state.login_failures = 0
    app.st.session_state.login_locked_until = 0
    for _ in range(app.MAX_LOGIN_ATTEMPTS - 1):
        app.record_login_failure("x@y.com")
    assert app.login_lock_remaining() == 0
    app.record_login_failure("x@y.com")
    assert 0 < app.login_lock_remaining() <= app.LOGIN_LOCK_SECONDS
    app.st.session_state.login_locked_until = time.time() - 1
    assert app.login_lock_remaining() == 0


# A01 Broken access control ──────────────────────────────────────────────

def test_role_requests_page_refuses_non_admins():
    from streamlit.testing.v1 import AppTest
    at = AppTest.from_file(os.path.join(ROOT, "app.py"), default_timeout=300)
    for k, v in dict(authenticated=True, role="Student", user_email="s@d", user_id="x",
                     offline_demo=True, chat_history=[], predictions={}).items():
        at.session_state[k] = v
    at.query_params["nav"] = "requests"     # try to open the Admin page directly by URL
    at.run()
    assert not at.exception
    assert not any("Role Upgrade Requests" in m.value for m in at.markdown)


# A05 Security misconfiguration / A06 Vulnerable components ───────────────

def test_streamlit_config_hides_errors_and_keeps_xsrf():
    with open(os.path.join(ROOT, ".streamlit", "config.toml"), "rb") as f:
        cfg = tomllib.load(f)
    assert cfg["client"]["showErrorDetails"] == "none"
    assert cfg["server"].get("enableXsrfProtection", True) is True
    assert cfg["server"].get("enableCORS", True) is True


def test_secrets_are_git_ignored():
    ignored = open(os.path.join(ROOT, ".gitignore"), encoding="utf-8").read()
    assert ".streamlit/secrets.toml" in ignored and ".env" in ignored


def test_dependency_floors_are_above_known_fixes():
    req = open(os.path.join(ROOT, "requirements.txt"), encoding="utf-8").read()
    for line in ("streamlit>=1.54", "torch>=2.13", "transformers>=5.10", "scikit-learn>=1.5"):
        assert line in req


# A08 Software and data integrity ────────────────────────────────────────

def test_models_load_only_from_safetensors():
    src = open(os.path.join(ROOT, "app.py"), encoding="utf-8").read()
    assert "from_pretrained(src, use_safetensors=True" in src
