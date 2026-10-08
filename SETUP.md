# Legal AI Hub — Setup & Deployment Guide

This guide details all instructions required to set up and run **Legal AI Hub (AI for Legal Case Outcome Prediction)** on another computer or laptop from scratch.

---

## 📋 Information You Need to Share with Your Friend

Share the following credentials and details with your friend so their local instance connects properly:

| Item | Description | Where to Find in Supabase |
| :--- | :--- | :--- |
| **`SUPABASE_URL`** | Project API URL (e.g., `https://xyzcompany.supabase.co`) | Supabase Dashboard $\rightarrow$ **Project Settings** $\rightarrow$ **API** $\rightarrow$ Project URL |
| **`SUPABASE_KEY`** | Public `anon` API Key (safe for client use) | Supabase Dashboard $\rightarrow$ **Project Settings** $\rightarrow$ **API** $\rightarrow$ `anon` / `public` key |
| **Model Weights** (If using local fine-tuned models) | `models/` directory containing PyTorch model weights | Share via Google Drive / USB if not downloading from Hugging Face |
| **Admin Credentials** (Optional) | Default Admin email & password | Supabase $\rightarrow$ Authentication $\rightarrow$ Users |

> ⚠️ **Note:** Never share your Supabase **`service_role` (secret)** key. Only share the **`anon` (public)** key.

---

## 🚀 Step-by-Step Installation Guide

### Step 1: Clone the Repository

Open PowerShell or Terminal on the friend's laptop:

```bash
git clone https://github.com/Bharambevaish/AI-for-Legal-Case.git
cd AI-for-Legal-Case
```

---

### Step 2: Create & Activate a Python Virtual Environment

Ensure **Python 3.10** or **Python 3.11** is installed.

#### On Windows (PowerShell):
```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
```
*(If PowerShell shows an execution policy error, run: `Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass` and then activate)*.

#### On macOS / Linux:
```bash
python3 -m venv venv
source venv/bin/activate
```

---

### Step 3: Install Required Dependencies

Upgrade pip and install the project requirements:

```bash
pip install --upgrade pip
pip install streamlit torch transformers supabase pymupdf scikit-learn pandas numpy
```
*(Or install via `pip install -r requirements.txt` if available)*.

---

### Step 4: Setup the Supabase Database

You can either **use the existing Supabase project** (Option A) or **create a new one** (Option B).

#### Option A: Connect to Existing Project (Fastest)
1. Provide your friend with your `SUPABASE_URL` and `SUPABASE_KEY`.
2. Skip to **Step 5**.

#### Option B: Setup a Fresh Supabase Database
1. Go to [https://supabase.com](https://supabase.com) and create a free account.
2. Click **New Project**, choose a name (e.g. `legal-ai-hub`), set a database password, and choose your nearest region.
3. Once the project is provisioned, open **SQL Editor** in the left sidebar.
4. Open the file `migration.sql` from this repository, copy its entire contents, paste it into the SQL Editor, and click **Run**.
   - *This creates: `case_predictions`, `cases_vault`, `student_queries`, and `statutory_bridge`.*
5. Open the file `role_system_setup.sql`, copy its entire contents, paste it into the SQL Editor, and click **Run**.
   - *This creates: `public.profiles`, `public.role_requests`, row-level security (RLS) policies, and auto-profile triggers.*

---

### Step 5: Configure Secrets & Credentials

Create a directory named `.streamlit` in the project root if it does not already exist:

#### Windows PowerShell:
```powershell
New-Item -ItemType Directory -Force -Path .streamlit
New-Item -ItemType File -Force -Path .streamlit\secrets.toml
```

Open `.streamlit/secrets.toml` in any code or text editor and paste your Supabase keys:

```toml
SUPABASE_URL = "https://your-project-ref.supabase.co"
SUPABASE_KEY = "your-anon-public-key"
```

*(You can also set these as system environment variables if preferred).*

---

### Step 6: Create the Admin Account

1. Start the app (see Step 7 below).
2. On the login screen, enter the desired admin email (e.g., `admin@legalai.in`) and password.
3. Click **Create Account** (the account will register in Supabase as `Student`).
4. Go to your **Supabase Dashboard $\rightarrow$ SQL Editor** and run:
   ```sql
   UPDATE public.profiles
   SET role = 'Admin'
   WHERE email = 'admin@legalai.in';
   ```
5. Return to the app, select the **Admin** tab in Chamber Jurisdiction, enter the credentials, and click **Sign In →**.

---

### Step 7: Run the Application

Start the Streamlit application:

```bash
streamlit run app.py
```

The browser will open automatically at `http://localhost:8501`.

---

## 🛠️ Troubleshooting Common Issues

1. **PyMuPDF / PDF reading errors**:
   Ensure `PyMuPDF` is installed: `pip install pymupdf`.
2. **Torch / CUDA warning**:
   The app runs seamlessly on CPU. If running with GPU, install PyTorch with CUDA support from [pytorch.org](https://pytorch.org).
3. **Database Offline Banner**:
   If the app shows *"Database Offline"*, verify that `.streamlit/secrets.toml` exists and that the `SUPABASE_URL` and `SUPABASE_KEY` values are exact.
