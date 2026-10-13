"""Regression tests for the Legal AI Hub preprocessing and inference pipeline.

Run from the project root:   python -m pytest tests -q
Model-dependent tests are skipped when ./models is not available.
"""
import os
import sys

import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
os.chdir(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import app  # noqa: E402  (importing app runs Streamlit in "bare" mode, which is fine for tests)


# ── IPC → BNS translation (bug C6) ───────────────────────────────────────

def test_translation_does_not_cascade():
    out = app.translate_laws_to_bns("accused under section 121 of the IPC")
    # One annotation only, and it is the Waging War mapping, not a re-translation of it.
    assert out.count("[") == 1
    assert "Waging War" in out
    assert "227" not in out


def test_translation_keeps_original_citation_and_word_ipc():
    out = app.translate_laws_to_bns("convicted under Section 302 IPC read with Section 34")
    assert "Section 302" in out          # original kept for the reader
    assert "IPC" in out                  # the bare word IPC is no longer replaced by [BNS]
    assert "103" in out                  # BNS murder section added as annotation


def test_bns_citations_mapped_back_to_ipc_for_model():
    out = app.normalize_bns_to_ipc("He was charged under Section 103 of BNS for murder.")
    assert "Section 302 of the IPC" in out


def test_find_statute_mappings_lists_each_section_once():
    found = app.find_statute_mappings("Section 302 IPC ... again section 302 ... and section 307 of the IPC")
    keys = [k for k, _ in found]
    assert keys.count("Section 302") == 1
    assert "Section 307" in keys


# ── Section extraction / leakage (bug M8) ────────────────────────────────

JUDGMENT = (
    "IN THE SUPREME COURT OF INDIA\nCRIMINAL APPELLATE JURISDICTION\n\nJUDGMENT\n\n"
    + "1. Brief facts of the case are that the appellant was convicted by the trial court. " * 20
    + "\n2. Learned counsel for the appellant submitted that the evidence was weak. " * 15
    + "\n\nIn the result, the appeal is dismissed and the conviction is upheld.\n"
)


def test_final_order_never_reaches_model_input():
    _, sections, crit = app.prepare_document(JUDGMENT)
    assert "dismissed" not in crit.lower()
    assert "dismissed" in sections["JUDGMENT"].lower()
    assert sections["FACTS"]


# ── Heuristic fallback honesty (bug M6) ──────────────────────────────────

def test_heuristic_has_no_fake_confidence():
    label, conf = app.predict("The accused was arrested by police under IPC.", None, None,
                              app.JURISDICTION_LABELS, task="jurisdiction")
    assert label == "Criminal Law"
    assert conf is None


# ── HTML escaping (bug M2/M3) ────────────────────────────────────────────

def test_chat_markup_escapes_html_and_renders_bold():
    out = app.chat_markup("**Match** <script>alert(1)</script>")
    assert "<strong>Match</strong>" in out
    assert "<script>" not in out


def test_lookup_handles_several_sections():
    res = app.lookup_statute("difference between 302 and 307", app.ipc_to_bns_map)
    keys = " ".join(k for k, _ in res)
    assert "302" in keys and "307" in keys


# ── Model-dependent tests ────────────────────────────────────────────────

# app.py loads models lazily; get_models() triggers the (cached) load once for the whole session.
t_b, m_b, t_c, m_c, model_load_error = app.get_models()
MODELS_READY = app.models_ready()
needs_models = pytest.mark.skipif(not MODELS_READY, reason="InLegalBERT models not loaded")


@needs_models
def test_predict_returns_mapped_label_and_probability():
    label, conf = app.predict("The appellant was convicted under section 302.", t_c, m_c,
                              app.OUTCOME_LABELS, task="outcome")
    assert label in app.OUTCOME_LABELS.values()
    assert 50.0 <= conf <= 100.0   # 2-way probability, even if the head has extra outputs


@needs_models
def test_shap_explanation_structure():
    if not app.SHAP_AVAILABLE:
        pytest.skip("shap not installed")
    ex = app.explain_outcome("The appellant was convicted of murder by the trial court on weak evidence.",
                             "Allowed / Accepted", max_tokens=32, max_evals=60)
    assert ex["target"] == "Allowed / Accepted"
    assert ex["words"]
    assert all(isinstance(v, float) for _, v in ex["supporting"] + ex["opposing"])


# ── Full-document sliding-window inference (bug M7) ──────────────────────

def test_window_predict_falls_back_to_heuristic_without_models():
    label, conf = app.predict_windows("The accused was arrested by police under IPC.", None, None,
                                      app.JURISDICTION_LABELS, task="jurisdiction")
    assert label == "Criminal Law"
    assert conf is None


@needs_models
def test_window_predict_covers_long_documents():
    long_text = ("The appellant was convicted by the trial court under section 302 and the "
                 "High Court affirmed the conviction on the testimony of two witnesses. ") * 125  # ~3000 words
    enc = t_c(long_text, truncation=True, max_length=512, stride=128,
                  return_overflowing_tokens=True)
    assert len(enc["input_ids"]) > 1
    label, conf, n = app.predict_windows(long_text, t_c, m_c, app.OUTCOME_LABELS,
                                         task="outcome", return_windows=True)
    assert n > 1
    assert label in app.OUTCOME_LABELS.values()
    assert 50.0 <= conf <= 100.0
    # The public signature still mirrors predict(): (label, confidence %).
    assert app.predict_windows(long_text, t_c, m_c, app.OUTCOME_LABELS, task="outcome") == (label, conf)


# ── Lazy model loading: pages other than the predictor must not wait for torch ──

def test_importing_app_does_not_load_models_or_torch():
    import subprocess
    code = ("import sys, logging; logging.disable(logging.WARNING); import app; "
            "print('torch' in sys.modules, 'transformers' in sys.modules)")
    out = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, timeout=120)
    assert out.returncode == 0, out.stderr[-2000:]
    assert out.stdout.strip().splitlines()[-1] == "False False"


def test_backward_compatible_model_attributes():
    # `app.t_c`, `app.MODELS_READY`, `from app import m_c` still work (resolved lazily).
    assert app.MODELS_READY == MODELS_READY
    assert app.t_c is t_c and app.model_load_error == model_load_error
    from app import m_c as imported_m_c
    assert imported_m_c is m_c


# ── Lab: one click on an example = exactly one question/answer pair ─────

def _lab_app():
    from streamlit.testing.v1 import AppTest
    at = AppTest.from_file(os.path.join(os.path.dirname(os.path.abspath(app.__file__)), "app.py"),
                           default_timeout=300)
    for k, v in dict(authenticated=True, role="Admin", user_email="a@d", user_id="x",
                     offline_demo=True, chat_history=[], predictions={}).items():
        at.session_state[k] = v
    at.query_params["nav"] = "lab"
    at.run()
    assert not at.exception
    return at


def test_lab_example_click_is_not_duplicated():
    at = _lab_app()
    at.button(key="lab_ex_0").click().run()
    roles = [m["role"] for m in at.session_state["lab_messages"]]
    assert roles == ["user", "assistant"]
    # A second, quick click on the same example (double-click on a slow app) adds nothing.
    at.button(key="lab_ex_0").click().run()
    assert len(at.session_state["lab_messages"]) == 2
    # A different question still goes through.
    at.button(key="lab_ex_1").click().run()
    assert len(at.session_state["lab_messages"]) == 4
    assert not at.exception
