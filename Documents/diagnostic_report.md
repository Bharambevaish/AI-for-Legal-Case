# 🩺 Full Project Health Check & Diagnostic Report

> **Date & Time of Assessment**: September 28, 2026  
> **Target Application**: Legal AI Hub (`app.py`)  
> **Status**: **Issues Detected (Non-Breaking to Fatal depending on execution runtime)**  
> **Policy**: No code or files were modified; this report provides an audit of findings, stack traces, and root causes for review.

---

## Executive Summary Matrix

| Check Item | Target / Component | Status | Key Finding / Error |
| :--- | :--- | :--- | :--- |
| **1. Dependencies** | `requirements.txt` via `pip install` | ⚠️ **Warnings** | Corrupted package warning `~umpy`; scripts installed to unmapped PATH; version downgrades during install. |
| **2. App Launch** | `python -m streamlit run app.py` | ⚠️ **Degraded** | Starts on `http://localhost:8501`, but silent fallback to mock predictions occurs if run outside `venv`. |
| **3. Model Weights & Loading** | `./models/Module_B/Final`<br>`./models/Module_C/Final` | ❌ **Fatal in Global Python**<br>✅ **Passed in `venv`** | In Global Python: `OSError: [WinError 1455] The paging file is too small for this operation to complete`.<br>In `venv`: Loads successfully in <1s. Local `vocab.txt` missing. |
| **4. Secrets Config** | `.streamlit/secrets.toml` | ✅ **Passed** | `SUPABASE_URL` and `SUPABASE_KEY` exist and are populated (values kept private). |
| **5. Cloud Database** | Supabase Project (`Legal-AI-Platform`) | ❌ **Failed (HTTP 522)** | Remote instance is in **Unhealthy** state. Queries time out with Cloudflare Error 522; app does not auto-fallback to demo mode when client is initialized. |
| **6. Module Imports** | All imports in `app.py` | ⚠️ **Warning** | All 10 modules import cleanly, but `fitz` throws deprecation warning (`use pymupdf instead`). |

---

## Detailed Check-by-Check Findings

### 1. `pip install -r requirements.txt` Health Check

#### Findings:
1. **Corrupted Package in Global Environment**:
   - `WARNING: Ignoring invalid distribution ~umpy (C:\Users\ASUS\AppData\Roaming\Python\Python313\site-packages)`
   - **Cause**: An interrupted or failed pip upgrade left a ghost folder prefixed with `~umpy`.
2. **Missing PATH Warnings for CLI Scripts**:
   - Scripts installed into `C:\Users\ASUS\AppData\Roaming\Python\Python313\Scripts` (e.g., `pymupdf.exe`, `typer.exe`, `spacy.exe`, `weasel.exe`, `plotly_get_chrome.exe`) are not on Windows system `PATH`.
3. **Dependency Version Discrepancies**:
   - Global Python had newer/conflicting packages (`websockets 16.0`, `click 8.1.8`) that had to be uninstalled/reinstalled during requirement resolution.
   - The dedicated project virtual environment (`.\venv`) already contains pre-aligned packages (`torch 2.12.0`, `transformers 5.9.0`, `streamlit 1.55.0`).

---

### 2. Streamlit Application Launch Test (`python -m streamlit run app.py`)

#### Findings:
- Running `python -m streamlit run app.py --server.headless true`:
  - Starts the web server on `http://localhost:8501`.
  - HTTP GET requests return `200 OK`.
- **Runtime Silent Degradation**:
  - In `app.py`, the model loader function is wrapped in:
    ```python
    @st.cache_resource
    def load_models():
        if not TRANSFORMERS_AVAILABLE:
            return None, None, None, None
        try:
            tokenizer = AutoTokenizer.from_pretrained("law-ai/InLegalBERT", use_fast=False)
            model_b = AutoModelForSequenceClassification.from_pretrained("./models/Module_B/Final")
            model_c = AutoModelForSequenceClassification.from_pretrained("./models/Module_C/Final")
            return tokenizer, model_b, tokenizer, model_c
        except Exception:
            return None, None, None, None
    ```
  - When invoked under the global Python runtime, `from_pretrained` throws an unhandled OS error (detailed below). The `except Exception:` clause swallows it silently, setting `t_b, m_b, t_c, m_c = None, None, None, None`, causing the app to silently execute dummy keyword heuristics rather than running actual neural network inferences.

---

### 3. Model Files Existence & Pretrained Loading Check

#### File Existence & Integrity Check:
- **Module B** (`./models/Module_B/Final`):
  - `config.json`: **Present** (976 bytes, 3 labels: Civil, Criminal, Constitutional)
  - `model.safetensors`: **Present** (437,961,700 bytes / ~417.7 MB)
  - `tokenizer.json`: **Present** (701,945 bytes)
  - `tokenizer_config.json`: **Present** (374 bytes)
  - `training_args.bin`: **Present** (5,201 bytes)
- **Module C** (`./models/Module_C/Final`):
  - `config.json`: **Present** (822 bytes, 2 labels: Dismissed, Allowed)
  - `model.safetensors`: **Present** (437,958,624 bytes / ~417.7 MB)
  - `tokenizer.json`: **Present** (701,945 bytes)
  - `tokenizer_config.json`: **Present** (374 bytes)
  - `training_args.bin`: **Present** (5,201 bytes)

#### Model Loading Results:

##### Scenario A: Global Python (`C:\Python313\python.exe` - PyTorch 2.9.1+cpu / Transformers 4.57.3)
- **Result**: ❌ **CRASH (Out of Virtual Memory / Paging File)**
- **Stack Trace**:
  ```text
  Traceback (most recent call last):
    File "<string>", line 20, in <module>
      m_b = AutoModelForSequenceClassification.from_pretrained('./models/Module_B/Final')
    File "...\transformers\models\auto\auto_factory.py", line 604, in from_pretrained
      return model_class.from_pretrained(pretrained_model_name_or_path, *model_args, config=config, **hub_kwargs, **kwargs)
    File "...\transformers\modeling_utils.py", line 4925, in from_pretrained
      with safe_open(checkpoint_files[0], framework="pt") as f:
  OSError: The paging file is too small for this operation to complete. (os error 1455)
  ```
- **Root Cause**:
  - The host machine has 8.0 GB Total Physical RAM with only **~440 MB free memory** available at runtime.
  - PyTorch 2.9.1 attempts to memory-map the 438 MB uncompressed tensor weights into Windows page file space, exhausting available virtual memory.

##### Scenario B: Project Virtual Environment (`.\venv\Scripts\python.exe` - PyTorch 2.12.0 / Transformers 5.9.0)
- **Result**: ✅ **PASSED**
- Both `Module_B` and `Module_C` loaded into memory in < 1 second:
  ```text
  Loading weights: 100%|##########| 201/201 [00:00<00:00, 3988.89it/s]
  Module B Loaded!
  Loading weights: 100%|##########| 201/201 [00:00<00:00, 2859.72it/s]
  Module C Loaded!
  ```

#### Tokenizer Files Check:
- **Local Tokenizer Loading (`use_fast=False`)**:
  - Attempting `AutoTokenizer.from_pretrained('./models/Module_B/Final', use_fast=False)` raises:
    `TypeError: _path_isfile: path should be string, bytes, os.PathLike or integer, not NoneType`
  - **Root Cause**: The local directories only contain `tokenizer.json` (Hugging Face Fast format). The slow `BertTokenizer` requires `vocab.txt`, which is missing locally.
- **Hugging Face Remote Tokenizer**:
  - `AutoTokenizer.from_pretrained('law-ai/InLegalBERT', use_fast=False)` succeeds because it fetches or utilizes cached `vocab.txt` from Hugging Face cache.

---

### 4. `.streamlit/secrets.toml` Verification

- **File Path**: `.streamlit/secrets.toml`
- **Result**: ✅ **CONFIRMED**
- **Checks**:
  - File exists and is valid TOML format.
  - `SUPABASE_URL`: Key is present and string is non-empty.
  - `SUPABASE_KEY`: Key is present and string is non-empty.
  - No secret values are exposed in logs or reports.

---

### 5. Supabase Database Connection & Services Health Check

#### Test Execution:
A direct test query was dispatched using the official `supabase-py` client against the configured `SUPABASE_URL`.

#### Result: ❌ **FAILED (Cloudflare Error 522 - Connection Timed Out)**
- **Raw API Response**:
  ```python
  APIError: {
      'message': 'JSON could not be generated',
      'code': 522,
      'hint': 'Refer to full message for details',
      'details': "Cloudflare 522: Connection timed out for nxbspesmruprdgviqqcr.supabase.co"
  }
  ```
- **Correlation with Dashboard Screenshot**:
  - The Supabase management dashboard for project `Legal-AI-Platform` reports the instance as **Unhealthy**:
    - `Database`: **Unhealthy**
    - `PostgREST`: **Unhealthy**
    - `Auth`: **Unhealthy**
    - `Realtime`: **Unhealthy**
    - `Storage`: **Unhealthy**
    - Notice on screen: *"Recently restored projects can take up to 5 minutes to become fully operational. If services stay unhealthy, refer to our docs for more information."*
- **App Behavior & Fallback Gap**:
  - In `app.py`:
    ```python
    @st.cache_resource
    def init_connection():
        try:
            return create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])
        except Exception:
            return None
    supabase: Client = init_connection()
    ```
  - `create_client()` creates an in-memory client without sending a network handshake. Therefore, `supabase` is truthy (`not None`).
  - When users attempt to Sign In, `app.py` checks `elif supabase:`, attempting `supabase.auth.sign_in_with_password()`. Because the backend server is unresponsive, the app hangs until Cloudflare times out (HTTP 522), then displays an error to the user.
  - The `# Offline / Demo mode` branch in `app.py` is unreachable as long as secrets exist, meaning the app does **not** fall back to offline demo mode automatically when Supabase is down.

---

### 6. Codebase Imports & Package Compatibility in `app.py`

Every module imported by `app.py` was inspected and verified across both environments:

| Import Statement in `app.py` | Underlying Library | Global Python | Virtual Env (`.\venv`) | Status & Compatibility Notes |
| :--- | :--- | :--- | :--- | :--- |
| `import streamlit as st` | `streamlit` | `1.54.0` | `1.55.0` | Compatible |
| `import torch` | `torch` | `2.9.1+cpu` | `2.12.0` | **Warning**: 2.9.1 suffers from OS 1455 memory mapping errors on 8GB host. |
| `import json` | Standard Library | Built-in | Built-in | Compatible |
| `import re` | Standard Library | Built-in | Built-in | Compatible |
| `import datetime` | Standard Library | Built-in | Built-in | Compatible |
| `from supabase import create_client, Client` | `supabase` | `2.31.0` | `2.28.2` | Compatible (network failure is remote infrastructure, not library) |
| `from transformers import AutoTokenizer, ...` | `transformers` | `4.57.3` | `5.9.0` | Compatible in `venv` |
| `import fitz` | `PyMuPDF` | `1.28.2` | `1.27.2` | ⚠️ **Deprecation Warning**: `The fitz API is deprecated and will be removed in future. Use import pymupdf instead.` |
| `import spacy` | `spacy` | `3.8.16` | `3.8.11` | Compatible |
| `import pandas as pd` (in `render_history`) | `pandas` | `2.3.3` | `2.3.3` | Compatible |

---

## Summary of Core Deficiencies Identified

1. **Host Environment Discrepancy**:
   - Running `python -m streamlit run app.py` defaults to `C:\Python313\python.exe`, which encounters Windows OS Error 1455 (page file exhaustion) when loading model weights.
   - The app must be executed through `.\venv\Scripts\python.exe` where PyTorch 2.12.0 and Transformers 5.9.0 load the models properly.
2. **Missing Local `vocab.txt`**:
   - `AutoTokenizer.from_pretrained('./models/Module_B/Final', use_fast=False)` cannot operate fully offline because only `tokenizer.json` was saved, not `vocab.txt`.
3. **Supabase Cloud Unhealthy State**:
   - The remote Supabase PostgreSQL/PostgREST instance (`nxbspesmruprdgviqqcr.supabase.co`) is currently down/unresponsive, causing HTTP 522 timeouts on all database and auth operations.
4. **Fragile Offline Fallback Logic in `app.py`**:
   - The application checks `if supabase:` rather than performing a quick liveness/ping check. When Supabase is down, it halts with error messages rather than gracefully engaging offline demo mode.
5. **Deprecated PyMuPDF Import**:
   - `import fitz` triggers deprecation logs; modern syntax is `import pymupdf as fitz` or `import pymupdf`.
