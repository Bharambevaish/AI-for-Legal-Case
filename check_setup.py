"""Demo-day readiness check for Legal AI Hub.

Run from the project folder, inside the virtual environment:

    python check_setup.py            # environment, models, prediction, database
    python check_setup.py --shap     # also times one SHAP explanation

Every line prints PASS / WARN / FAIL with what to do about it.
"""
import importlib
import os
import sys
import time

os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")
os.chdir(os.path.dirname(os.path.abspath(__file__)))

results = []


def report(status, name, detail=""):
    results.append(status)
    mark = {"PASS": "[PASS]", "WARN": "[WARN]", "FAIL": "[FAIL]"}[status]
    print(f"{mark} {name}" + (f" - {detail}" if detail else ""))


print("=" * 70)
print(" Legal AI Hub - demo readiness check")
print("=" * 70)

# 1. Python + virtual environment ---------------------------------------
ver = sys.version_info
report("PASS" if (3, 10) <= ver[:2] <= (3, 13) else "WARN", "Python version", sys.version.split()[0])
in_venv = sys.prefix != getattr(sys, "base_prefix", sys.prefix)
report("PASS" if in_venv else "FAIL", "Virtual environment active",
       sys.prefix if in_venv else r"activate it first:  .\.venv\Scripts\Activate.ps1  (or .\venv\Scripts\Activate.ps1)")

# 2. Packages -------------------------------------------------------------
for mod, pip_name, required in [("streamlit", "streamlit", True), ("torch", "torch", True),
                                ("transformers", "transformers", True), ("pymupdf", "pymupdf", True),
                                ("supabase", "supabase", True), ("pandas", "pandas", True),
                                ("shap", "shap", False), ("pytest", "pytest", False)]:
    try:
        m = importlib.import_module(mod)
        report("PASS", f"package {mod}", getattr(m, "__version__", "installed"))
    except Exception as e:
        report("FAIL" if required else "WARN", f"package {mod}",
               f"missing - pip install {pip_name}" + ("" if required else "  (needed for AI Decision Drivers)" if mod == "shap" else ""))

# 3. Memory ---------------------------------------------------------------
try:
    import psutil
    free_gb = psutil.virtual_memory().available / 1e9
    report("PASS" if free_gb >= 2.0 else "WARN", "Free RAM", f"{free_gb:.1f} GB"
           + ("" if free_gb >= 2.0 else " - close Chrome tabs / other apps before the demo (models need ~1.5 GB)"))
except ImportError:
    pass

# 4. Model files ------------------------------------------------------------
import json  # noqa: E402

for module in ("B", "C"):
    d = f"./models/Module_{module}/Final"
    missing = [f for f in ("config.json", "model.safetensors", "tokenizer.json") if not os.path.isfile(os.path.join(d, f))]
    if missing:
        report("WARN", f"Module_{module} files", f"missing {missing} - app will try to download from Hugging Face (needs internet)")
    else:
        n = len(json.load(open(os.path.join(d, "config.json"))).get("id2label", {})) or "?"
        head = None
        try:
            from safetensors import safe_open
            with safe_open(os.path.join(d, "model.safetensors"), framework="pt") as f:
                head = next((f.get_slice(k).get_shape()[0] for k in f.keys() if k.endswith("classifier.weight")), None)
        except Exception:
            pass
        if head and head != n:
            report("WARN", f"Module_{module} files", f"config.json says {n} labels but the weights have {head}; "
                   f"the app loads it with {head} (fine for the demo)")
        else:
            report("PASS", f"Module_{module} files", f"{d} ({n} output labels)")

# 5. Load the app's pipeline and run one real prediction -------------------
try:
    import streamlit.logger
    streamlit.logger.set_log_level("error")
except Exception:
    pass

app = None
try:
    t0 = time.time()
    import app  # noqa: E402  (loads both InLegalBERT models through the app's own loader)
    if app.MODELS_READY:
        report("PASS", "Models load", f"{time.time() - t0:.1f} s")
    else:
        report("FAIL", "Models load", f"{app.model_load_error} - app would fall back to rule-based mode")
except Exception as e:
    report("FAIL", "Import app.py", f"{type(e).__name__}: {e}")

sample_path = os.path.join("Model Test pdfs", "perfect_test_case.txt")
if app is not None and app.MODELS_READY and os.path.isfile(sample_path):
    text = open(sample_path, encoding="utf-8", errors="ignore").read()
    t0 = time.time()
    _, sections, crit = app.prepare_document(text)
    jur, jc = app.predict(crit, app.t_b, app.m_b, app.JURISDICTION_LABELS, task="jurisdiction")
    out, oc = app.predict(crit, app.t_c, app.m_c, app.OUTCOME_LABELS, task="outcome")
    if jur and out:
        report("PASS", "Test prediction", f"{jur} ({jc:.1f}%), {out} ({oc:.1f}%) in {time.time() - t0:.1f} s")
    else:
        report("FAIL", "Test prediction", "inference error - see log above")

    if "--shap" in sys.argv:
        if app.SHAP_AVAILABLE:
            t0 = time.time()
            ex = app.explain_outcome(crit, out)
            top = ", ".join(w for w, _ in ex["supporting"][:5])
            report("PASS", "SHAP decision drivers", f"{time.time() - t0:.0f} s; top words: {top}")
        else:
            report("WARN", "SHAP decision drivers", "pip install shap")

# 6. Database ---------------------------------------------------------------
secrets_path = os.path.join(".streamlit", "secrets.toml")
if not os.path.isfile(secrets_path):
    report("WARN", "Supabase secrets", "no .streamlit/secrets.toml - app runs in offline demo mode")
else:
    try:
        try:
            import tomllib
        except ImportError:
            import tomli as tomllib
        sec = tomllib.load(open(secrets_path, "rb"))
        url, key = sec.get("SUPABASE_URL"), sec.get("SUPABASE_KEY")
        if not (url and key):
            report("FAIL", "Supabase secrets", "SUPABASE_URL / SUPABASE_KEY missing in secrets.toml")
        else:
            import httpx
            r = httpx.get(f"{url}/auth/v1/health", headers={"apikey": key}, timeout=8)
            if r.status_code != 200:
                report("FAIL", "Supabase reachable", f"HTTP {r.status_code} - restore/resume the project in the Supabase dashboard; "
                       "the app will use offline demo mode meanwhile")
            else:
                report("PASS", "Supabase reachable", url)
                r2 = httpx.get(f"{url}/rest/v1/role_requests?select=id&limit=1",
                               headers={"apikey": key, "Authorization": f"Bearer {key}"}, timeout=8)
                report("PASS" if r2.status_code == 200 else "FAIL", "Database schema",
                       "tables found" if r2.status_code == 200 else f"HTTP {r2.status_code} - run schema.sql in the Supabase SQL Editor")
            if str(sec.get("ALLOW_OFFLINE_ADMIN_DEMO", "")).lower() == "true":
                report("WARN", "ALLOW_OFFLINE_ADMIN_DEMO", "enabled - fine for a local demo, remove it afterwards")
    except Exception as e:
        report("FAIL", "Supabase check", f"{type(e).__name__}: {e}")

print("=" * 70)
fails, warns = results.count("FAIL"), results.count("WARN")
if fails:
    print(f" NOT READY: {fails} failure(s), {warns} warning(s). Fix the [FAIL] lines above.")
else:
    print(f" READY for the demo ({warns} warning(s)).  Start it with:  streamlit run app.py")
print("=" * 70)
sys.exit(1 if fails else 0)
