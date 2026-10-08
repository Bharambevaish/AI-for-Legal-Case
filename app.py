import streamlit as st
import torch
import json
import re
import html
import datetime
import logging
from supabase import create_client, Client

logger = logging.getLogger(__name__)

# Graceful fallbacks for optional dependencies
try:
    from transformers import AutoTokenizer, AutoModelForSequenceClassification
    TRANSFORMERS_AVAILABLE = True
except ImportError:
    TRANSFORMERS_AVAILABLE = False

try:
    import pymupdf as fitz
    PYMUPDF_AVAILABLE = True
except ImportError:
    try:
        import fitz
        PYMUPDF_AVAILABLE = True
    except ImportError:
        PYMUPDF_AVAILABLE = False

try:
    import spacy
    SPACY_AVAILABLE = True
except ImportError:
    SPACY_AVAILABLE = False

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  PAGE CONFIG
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
st.set_page_config(
    page_title="Legal AI Hub — Judicial Analytics Platform",
    page_icon="⚖️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  GLOBAL THEME & DESIGN SYSTEM
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
def inject_theme():
    theme_css = """<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=Plus+Jakarta+Sans:wght@600;700;800&display=swap');
@import url('https://fonts.googleapis.com/css2?family=Material+Symbols+Outlined:opsz,wght,FILL,GRAD@20..48,100..700,0..1,-50..200');
html, body {
font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif !important;
color: #0B1C30 !important;
background-color: #F8F9FF !important;
}
h1, h2, h3, h4, h5, h6 {
font-family: 'Plus Jakarta Sans', 'Inter', sans-serif !important;
color: #041534 !important;
}
.stApp {
background: #F8F9FF !important;
color: #0B1C30 !important;
}
header[data-testid="stHeader"] {
background: transparent !important;
height: 3.5rem !important;
border: none !important;
box-shadow: none !important;
z-index: 9999 !important;
}
div[data-testid="stSidebarCollapsedControl"],
button[data-testid="stSidebarCollapsedControl"],
[data-testid="collapsedControl"] {
display: flex !important;
visibility: visible !important;
opacity: 1 !important;
position: fixed !important;
top: 0.75rem !important;
left: 0.75rem !important;
z-index: 100000 !important;
color: #041534 !important;
background: #FFFFFF !important;
border: 1px solid #E5EEFF !important;
border-radius: 8px !important;
padding: 4px !important;
box-shadow: 0 1px 4px rgba(0,0,0,0.06) !important;
}
div[data-testid="stToolbar"],
.stDeployButton {
display: none !important;
}
footer {
display: none !important;
}
.block-container {
padding: 2rem 2.5rem !important;
max-width: 1280px !important;
}
[data-testid="stSidebar"] {
background: #FFFFFF !important;
border-right: 1px solid #E5EEFF !important;
box-shadow: 0 1px 8px rgba(0,0,0,0.04) !important;
min-width: 288px !important;
max-width: 288px !important;
width: 288px !important;
}
[data-testid="stSidebar"] div[role="radiogroup"] {
background: transparent !important;
border: none !important;
display: flex !important;
flex-direction: column !important;
gap: 6px !important;
padding: 0 !important;
}
[data-testid="stSidebar"] div[role="radiogroup"] label {
display: flex !important;
align-items: center !important;
padding: 10px 14px !important;
border-radius: 8px !important;
font-size: 13.5px !important;
font-weight: 600 !important;
color: #45464E !important;
background: transparent !important;
border-left: 4px solid transparent !important;
cursor: pointer !important;
transition: all 0.15s ease !important;
user-select: none !important;
}
[data-testid="stSidebar"] div[role="radiogroup"] label:hover {
background: #EFF4FF !important;
color: #041534 !important;
}
[data-testid="stSidebar"] div[role="radiogroup"] label:has(input:checked) {
background: #E5EEFF !important;
color: #041534 !important;
font-weight: 700 !important;
border-left: 4px solid #041534 !important;
box-shadow: 0 1px 3px rgba(4,21,52,0.06) !important;
}
[data-testid="stSidebar"] div[role="radiogroup"] label:has(input:checked) * {
color: #041534 !important;
font-weight: 700 !important;
}
[data-testid="stSidebar"] div[role="radiogroup"] input[type="radio"],
[data-testid="stSidebar"] div[role="radiogroup"] label > div:first-of-type {
display: none !important;
}
[data-testid="stSidebar"] div.stButton > button {
background: #FFFFFF !important;
color: #45464E !important;
border: 1px solid #E5EEFF !important;
border-radius: 8px !important;
font-size: 12px !important;
font-weight: 600 !important;
padding: 6px 12px !important;
margin-top: 8px !important;
box-shadow: none !important;
transition: all 0.15s ease !important;
}
[data-testid="stSidebar"] div.stButton > button:hover {
background: #FEE2E2 !important;
color: #BA1A1A !important;
border-color: #FECACA !important;
}
.pro-card {
background: #FFFFFF;
border: 1px solid #E5EEFF;
border-radius: 12px;
padding: 1.5rem;
box-shadow: 0 1px 8px rgba(0,0,0,0.04);
margin-bottom: 1.25rem;
}
div[data-testid="stTextInput"] label,
div[data-testid="stSelectbox"] label {
font-weight: 600 !important;
color: #45464E !important;
font-size: 0.82rem !important;
margin-bottom: 0.3rem !important;
}
div[data-testid="stTextInput"] input,
div[data-testid="stTextArea"] textarea {
background: #FFFFFF !important;
border: 1px solid #E5EEFF !important;
border-radius: 8px !important;
color: #0B1C30 !important;
padding: 0.6rem 0.85rem !important;
font-size: 0.9rem !important;
transition: all 0.2s ease !important;
}
div[data-testid="stTextInput"] input:focus,
div[data-testid="stTextArea"] textarea:focus {
border-color: #041534 !important;
box-shadow: 0 0 0 3px rgba(4,21,52,0.08) !important;
}
div[data-testid="stSelectbox"] div[role="button"] {
background: #FFFFFF !important;
border: 1px solid #E5EEFF !important;
border-radius: 8px !important;
color: #0B1C30 !important;
padding: 0.55rem 0.85rem !important;
}
div.stButton > button:first-child {
background: #041534 !important;
color: #FFFFFF !important;
border: none !important;
padding: 0.65rem 1.25rem !important;
font-weight: 600 !important;
font-size: 0.85rem !important;
border-radius: 8px !important;
box-shadow: 0 1px 3px rgba(4,21,52,0.15) !important;
transition: all 0.2s ease !important;
width: 100%;
}
div.stButton > button:first-child:hover {
background: #1B2A4A !important;
}
div.stButton > button:first-child:disabled,
div.stButton > button:first-child:disabled:hover {
background: #C5C6CF !important;
color: #75777F !important;
cursor: not-allowed !important;
box-shadow: none !important;
}
.badge {
display: inline-flex;
align-items: center;
padding: 0.25rem 0.65rem;
border-radius: 9999px;
font-size: 0.7rem;
font-weight: 700;
letter-spacing: 0.04em;
text-transform: uppercase;
}
.badge-navy { background: #EFF4FF; color: #041534; }
.badge-favorable { background: #ECFDF5; color: #059669; }
.badge-risk { background: #FEF2F2; color: #BA1A1A; }
.badge-blue { background: #EFF4FF; color: #3F5D9B; }
.badge-slate { background: #EFF4FF; color: #45464E; }
button[data-baseweb="tab"] {
font-weight: 600 !important;
color: #75777F !important;
font-size: 0.85rem !important;
}
button[data-baseweb="tab"][aria-selected="true"] {
color: #041534 !important;
border-bottom-color: #041534 !important;
}
div[data-testid="stDataFrame"] {
border: 1px solid #E5EEFF !important;
border-radius: 12px !important;
overflow: hidden !important;
}
div[data-testid="stMetric"] {
background: #FFFFFF;
border: 1px solid #E5EEFF;
border-radius: 10px;
padding: 1rem 1.25rem;
}
.material-symbols-outlined {
font-family: 'Material Symbols Outlined' !important;
font-weight: normal;
font-style: normal;
display: inline-block;
line-height: 1;
text-transform: none;
letter-spacing: normal;
word-wrap: normal;
white-space: nowrap;
direction: ltr;
}
@keyframes fadeIn {
from { opacity: 0; transform: translateY(6px); }
to { opacity: 1; transform: translateY(0); }
}
.animate-in { animation: fadeIn 0.3s ease-out; }
</style>"""
    st.markdown(theme_css, unsafe_allow_html=True)

inject_theme()

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  DATABASE & STATE MANAGEMENT
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
@st.cache_resource
def _check_supabase_health(url: str, key: str) -> bool:
    try:
        import httpx
        probe = httpx.get(f"{url}/auth/v1/health", headers={"apikey": key}, timeout=3.5)
        if probe.status_code != 200:
            logger.warning(f"Supabase health check returned HTTP {probe.status_code}. Falling back to offline mode.")
            return False
        return True
    except Exception as e:
        logger.warning(f"Supabase liveness probe failed or timed out: {e}. Falling back to offline mode.")
        return False

def init_connection():
    if "sb_client" in st.session_state:
        return st.session_state["sb_client"]

    url = st.secrets.get("SUPABASE_URL") if hasattr(st, "secrets") else None
    key = st.secrets.get("SUPABASE_KEY") if hasattr(st, "secrets") else None
    if not url or not key:
        st.session_state["sb_client"] = None
        return None

    if not _check_supabase_health(url, key):
        st.session_state["sb_client"] = None
        return None

    try:
        client = create_client(url, key)
        st.session_state["sb_client"] = client
        return client
    except Exception as e:
        logger.warning(f"Supabase client initialization failed: {e}. Falling back to offline mode.")
        st.session_state["sb_client"] = None
        return None

supabase: Client = init_connection()

try:
    if "authenticated" not in st.session_state:
        st.session_state.authenticated = False
        st.session_state.user_id = ""
        st.session_state.user_email = ""
        st.session_state.role = ""
        st.session_state.chat_history = []
        st.session_state.predictions = {}
except Exception:
    pass

def get_history():
    if not supabase:
        return []
    try:
        user_role = st.session_state.get('role', 'Student')
        query = supabase.table("case_predictions").select("*")
        if user_role != "Admin":
            query = query.eq("user_email", st.session_state.get('user_email', ''))
        return query.order('created_at', desc=True).execute().data or []
    except Exception as e:
        logger.error(f"Error fetching case history: {e}")
        return []

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  AI INFERENCE ENGINE
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
@st.cache_resource
def load_models():
    if not TRANSFORMERS_AVAILABLE:
        return None, None, None, None, "transformers_unavailable"
    try:
        tokenizer_b = AutoTokenizer.from_pretrained("./models/Module_B/Final", use_fast=True)
        model_b = AutoModelForSequenceClassification.from_pretrained("./models/Module_B/Final")
        tokenizer_c = AutoTokenizer.from_pretrained("./models/Module_C/Final", use_fast=True)
        model_c = AutoModelForSequenceClassification.from_pretrained("./models/Module_C/Final")
        return tokenizer_b, model_b, tokenizer_c, model_c, None
    except Exception as e:
        logger.error(f"Failed to load AI models: {type(e).__name__}: {e}", exc_info=True)
        err_str = str(e).lower()
        if isinstance(e, FileNotFoundError) or "no such file" in err_str or "not found" in err_str:
            err_type = "files_missing"
        elif isinstance(e, MemoryError) or getattr(e, "winerror", None) == 1455 or "paging file" in err_str or "out of memory" in err_str:
            err_type = "out_of_memory"
        else:
            err_type = f"other: {type(e).__name__}: {e}"
        return None, None, None, None, err_type

t_b, m_b, t_c, m_c, model_load_error = load_models()

def extract_text_from_pdf(pdf_file):
    if not PYMUPDF_AVAILABLE:
        return pdf_file.read().decode('utf-8', errors='ignore')
    try:
        doc = fitz.open(stream=pdf_file.read(), filetype="pdf")
        return "\n".join([page.get_text("text") for page in doc])
    except Exception:
        return ""

def clean_legal_text(text):
    pattern = r'(?i)^.*?(?:\bHEADNOTE\b[\s:\"\-]*|\n(?<!DATE OF )\bJUDGMENT\b[\s:\"\-]*|\n\s*ORDER\s*[\s:\"\-]*)(\n|$)'
    cleaned = re.sub(pattern, '', text, count=1, flags=re.DOTALL)
    return cleaned.strip()

@st.cache_data
def load_bns_mapping():
    try:
        with open("bns_mapping.json", 'r') as f:
            return json.load(f)
    except Exception:
        return {
            "302": "101 (Murder)",
            "307": "109 (Attempt to Murder)",
            "379": "303 (Theft)",
            "420": "318 (Cheating)",
            "376": "64 (Rape)",
            "395": "310 (Dacoity)"
        }

ipc_to_bns_map = load_bns_mapping()

def translate_laws_to_bns(text):
    if not ipc_to_bns_map:
        return text
    for ipc, bns in ipc_to_bns_map.items():
        pattern = re.compile(r'\b' + re.escape(ipc) + r'\b', re.IGNORECASE)
        text = pattern.sub(f" [{bns}] ", text)
    return text

def structure_aware_chunking(text):
    # Strip preliminary reporter metadata/citations if present at top
    header_strip_patterns = [
        r'(?i)^.*?(?:equivalent citations[^\n]*\n|author:[^\n]*\n|bench:[^\n]*\n)',
        r'(?i)^.*?(?:\breportable\b|\bjudgment\b|\border\b)[\s\:\-\n]*'
    ]
    cleaned = text
    for pat in header_strip_patterns:
        cleaned = re.sub(pat, '', cleaned, count=1, flags=re.DOTALL).strip()
    if len(cleaned) < 200:
        cleaned = text

    # Realistic section extraction for Indian court rulings
    fact_pattern = r'(?i)(?:brief\s+facts|factual\s+(?:matrix|aspects?|background)|facts?\s+of\s+the\s+case|facts?\s+in\s+brief|background\s+facts?|prosecution\s+(?:case|story)|case\s+of\s+the\s+(?:prosecution|appellant|plaintiff)|the\s+prosecution\s+(?:alleged|case)|(?:^|\n)\s*[0-9]{1,2}[\.\)]\s*(?:facts|factual|the\s+prosecution|the\s+case\s+in\s+brief))[\s\S]*?(?=\n\s*(?:[0-9]{1,2}[\.\)]\s*)?(?:submissions?|arguments?|contentions?|issues?|points?|consideration|findings?|judgment|order)|$)'
    arg_pattern = r'(?i)(?:submissions?|arguments?|contentions?|grounds?\s+of\s+appeal|(?:learned\s+)?counsel\s+(?:for\s+the\s+)?(?:appellant|respondent|parties)\s+(?:submitted|argued|contended)|it\s+was\s+(?:submitted|argued|contended)|(?:^|\n)\s*[0-9]{1,2}[\.\)]\s*(?:submissions?|arguments?|contentions?))[\s\S]*?(?=\n\s*(?:[0-9]{1,2}[\.\)]\s*)?(?:findings?|consideration|our\s+analysis|appreciation|judgment|order|conclusion|in\s+the\s+result)|$)'
    judg_pattern = r'(?i)(?:final\s+judgment|operative\s+order|operative\s+part|in\s+the\s+result|for\s+the\s+(?:foregoing\s+)?reasons|conclusion)[\s\S]*'

    m_facts = re.search(fact_pattern, cleaned)
    m_args = re.search(arg_pattern, cleaned)
    m_judg = re.search(judg_pattern, cleaned)

    facts_text = m_facts.group(0).strip() if m_facts else ""
    args_text = m_args.group(0).strip() if m_args else ""
    judg_text = m_judg.group(0).strip() if m_judg else ""

    ext = {
        "FACTS": facts_text,
        "ARGUMENTS": args_text,
        "JUDGMENT": judg_text
    }

    combined = (facts_text + " " + args_text).strip()
    # Fallback to substantive narrative after preliminary headers (up to 2500 chars)
    crit = combined or cleaned[:2500].strip() or text[:2000]
    return ext, crit

def predict(text, t, m, label_map, task="jurisdiction"):
    if t is None or m is None:
        text_lower = text.lower()
        if task == "jurisdiction":
            if "constitutional" in text_lower or "article" in text_lower or "fundamental rights" in text_lower:
                return label_map.get(2, "Constitutional Law"), 88.6
            elif "murder" in text_lower or "ipc" in text_lower or "accused" in text_lower or "police" in text_lower:
                return label_map.get(1, "Criminal Law"), 84.2
            else:
                return label_map.get(0, "Civil Law"), 79.1
        else:  # task == "outcome"
            if "dismissed" in text_lower or "rejected" in text_lower or "no merit" in text_lower or "conviction affirmed" in text_lower:
                return label_map.get(0, "Dismissed / Rejected"), 82.5
            else:
                return label_map.get(1, "Allowed / Accepted"), 85.0

    try:
        inputs = t(text, padding="max_length", truncation=True, max_length=512, return_tensors="pt")
        with torch.no_grad():
            logits = m(**inputs).logits
            probs = torch.nn.functional.softmax(logits, dim=-1)
            pred_id = torch.argmax(logits, dim=-1).item()
        return label_map[pred_id], probs[0][pred_id].item() * 100
    except Exception as e:
        logger.error(f"Inference error in task '{task}': {e}")
        return label_map[0], 70.0

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  LOGIN PAGE
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
def render_auth():
    login_css = """<style>
.stApp:has(#login-root) {
background-color: #F8FAFC !important;
background-image: radial-gradient(at 0% 0%, rgba(56, 189, 248, 0.04) 0px, transparent 50%), radial-gradient(at 100% 100%, rgba(15, 23, 42, 0.03) 0px, transparent 50%) !important;
background-attachment: fixed !important;
}
.stApp:has(#login-root) .block-container {
max-width: 460px !important;
margin: 0 auto !important;
padding-top: 5.5rem !important;
padding-bottom: 3rem !important;
}
.stApp:has(#login-root) header[data-testid="stHeader"] {
display: none !important;
}
.stApp:has(#login-root) [data-testid="stHeaderActionElements"] {
display: none !important;
}
.login-topbar {
position: fixed !important;
top: 0 !important;
left: 0 !important;
right: 0 !important;
width: 100% !important;
height: 60px !important;
background: rgba(255, 255, 255, 0.8) !important;
backdrop-filter: blur(12px) !important;
border-bottom: 1px solid rgba(226, 232, 240, 0.8) !important;
z-index: 999 !important;
display: flex !important;
align-items: center !important;
padding: 0 1.5rem !important;
box-sizing: border-box !important;
}
.login-topbar-inner {
max-width: 1200px !important;
width: 100% !important;
margin: 0 auto !important;
display: flex !important;
align-items: center !important;
justify-content: flex-start !important;
}
.login-brand {
display: flex !important;
align-items: center !important;
gap: 12px !important;
text-decoration: none !important;
}
.login-brand-logo {
width: 36px !important;
height: 36px !important;
border-radius: 10px !important;
overflow: hidden !important;
flex-shrink: 0 !important;
display: flex !important;
align-items: center !important;
justify-content: center !important;
}
.login-brand-text {
display: flex !important;
flex-direction: column !important;
}
.login-brand-title {
font-family: 'Plus Jakarta Sans', sans-serif !important;
font-size: 15px !important;
font-weight: 700 !important;
color: #0F172A !important;
line-height: 1.2 !important;
letter-spacing: -0.01em !important;
}
.login-brand-tagline {
font-size: 11px !important;
font-weight: 500 !important;
color: #64748B !important;
letter-spacing: 0.02em !important;
}
.login-header {
text-align: center !important;
margin-bottom: 2rem !important;
}
.login-emblem-wrapper {
display: inline-flex !important;
padding: 4px !important;
background: #FFFFFF !important;
border: 1px solid #E2E8F0 !important;
border-radius: 16px !important;
box-shadow: 0 1px 3px rgba(15,23,42,0.06) !important;
margin-bottom: 1rem !important;
}
.login-emblem-icon {
width: 48px !important;
height: 48px !important;
border-radius: 12px !important;
display: flex !important;
align-items: center !important;
justify-content: center !important;
overflow: hidden !important;
}
.login-title {
font-family: 'Plus Jakarta Sans', sans-serif !important;
font-size: 26px !important;
font-weight: 700 !important;
color: #0F172A !important;
margin: 0 0 0.35rem 0 !important;
line-height: 1.2 !important;
letter-spacing: -0.02em !important;
}
.login-subtitle {
font-size: 14px !important;
color: #64748B !important;
margin: 0 !important;
line-height: 1.5 !important;
}
.stApp:has(#login-root) div[data-testid="stVerticalBlockBorderWrapper"]:has(#login-card-anchor) {
background: #FFFFFF !important;
border: 1px solid #E2E8F0 !important;
border-radius: 16px !important;
box-shadow: 0 10px 30px -5px rgba(15,23,42,0.05), 0 4px 12px -2px rgba(15,23,42,0.025) !important;
padding: 32px !important;
}
.chamber-label {
font-size: 11px !important;
font-weight: 700 !important;
text-transform: uppercase !important;
letter-spacing: 0.08em !important;
color: #64748B !important;
margin-bottom: 8px !important;
display: block !important;
}
.stApp:has(#login-root) div[role="radiogroup"] {
background: #F1F5F9 !important;
border: 1px solid #E2E8F0 !important;
border-radius: 12px !important;
padding: 4px !important;
display: flex !important;
flex-direction: row !important;
gap: 4px !important;
margin-bottom: 1.25rem !important;
}
.stApp:has(#login-root) div[role="radiogroup"] label {
flex: 1 1 0% !important;
min-width: 0 !important;
text-align: center !important;
display: flex !important;
justify-content: center !important;
align-items: center !important;
background: transparent !important;
border-radius: 8px !important;
padding: 8px 4px !important;
color: #475569 !important;
font-size: 13px !important;
font-weight: 500 !important;
border: none !important;
cursor: pointer !important;
transition: all 0.15s ease !important;
user-select: none !important;
white-space: nowrap !important;
}
.stApp:has(#login-root) div[role="radiogroup"] label:not(:has(input:checked)):hover {
color: #0F172A !important;
background: rgba(255, 255, 255, 0.6) !important;
}
.stApp:has(#login-root) div[role="radiogroup"] label:has(input:checked) {
background: #0F172A !important;
color: #FFFFFF !important;
font-weight: 600 !important;
box-shadow: 0 1px 3px rgba(15,23,42,0.15) !important;
}
.stApp:has(#login-root) div[role="radiogroup"] label:has(input:checked) * {
color: #FFFFFF !important;
font-weight: 600 !important;
}
.stApp:has(#login-root) div[role="radiogroup"] input[type="radio"],
.stApp:has(#login-root) div[role="radiogroup"] label > div:first-of-type {
display: none !important;
}
.stApp:has(#login-root) div[data-testid="stTextInput"] label {
font-size: 12px !important;
font-weight: 600 !important;
color: #334155 !important;
margin-bottom: 6px !important;
}
.stApp:has(#login-root) div[data-testid="stTextInput"] div[data-baseweb="input"] {
background-color: rgba(248, 250, 252, 0.8) !important;
border: 1px solid #CBD5E1 !important;
border-radius: 12px !important;
min-height: 42px !important;
transition: all 0.15s ease !important;
overflow: hidden !important;
}
.stApp:has(#login-root) div[data-testid="stTextInput"] div[data-baseweb="input"]:focus-within {
background-color: #FFFFFF !important;
border-color: #0F172A !important;
box-shadow: 0 0 0 3px rgba(15,23,42,0.1) !important;
}
.stApp:has(#login-root) div[data-testid="stTextInput"] div[data-baseweb="base-input"] {
background: transparent !important;
}
.stApp:has(#login-root) div[data-testid="stTextInput"] input {
background: transparent !important;
border: none !important;
box-shadow: none !important;
height: 42px !important;
font-size: 13.5px !important;
color: #0F172A !important;
outline: none !important;
}
.stApp:has(#login-root) div[data-testid="stTextInput"]:nth-of-type(1) input {
background-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='16' height='16' viewBox='0 0 24 24' fill='none' stroke='%2394A3B8' stroke-width='2' stroke-linecap='round' stroke-linejoin='round'%3E%3Cpath d='M3 8l7.89 5.26a2 2 0 002.22 0L21 8M5 19h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z'/%3E%3C/svg%3E") !important;
background-repeat: no-repeat !important;
background-position: 12px center !important;
padding-left: 38px !important;
}
.stApp:has(#login-root) div[data-testid="stTextInput"]:nth-of-type(2) input {
background-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='16' height='16' viewBox='0 0 24 24' fill='none' stroke='%2394A3B8' stroke-width='2' stroke-linecap='round' stroke-linejoin='round'%3E%3Crect x='3' y='11' width='18' height='11' rx='2' ry='2'/%3E%3Cpath d='M7 11V7a5 5 0 0110 0v4'/%3E%3C/svg%3E") !important;
background-repeat: no-repeat !important;
background-position: 12px center !important;
padding-left: 38px !important;
}
.stApp:has(#login-root) div[data-testid="stTextInput"] button {
background: transparent !important;
border: none !important;
color: #94A3B8 !important;
box-shadow: none !important;
}
.stApp:has(#login-root) div[data-testid="stTextInput"] button:hover {
background: transparent !important;
color: #475569 !important;
}
.stApp:has(#login-root) div.stButton:nth-of-type(1) > button {
background: #0F172A !important;
color: #FFFFFF !important;
border: none !important;
border-radius: 12px !important;
padding: 10px 16px !important;
font-weight: 600 !important;
font-size: 14px !important;
box-shadow: 0 1px 3px rgba(15,23,42,0.15) !important;
margin-top: 0.5rem !important;
transition: all 0.15s ease !important;
}
.stApp:has(#login-root) div.stButton:nth-of-type(1) > button:hover {
background: #1E293B !important;
}
.stApp:has(#login-root) div.stButton:nth-of-type(1) > button:active {
background: #020617 !important;
}
.stApp:has(#login-root) div.stButton:nth-of-type(2) > button {
background: #F1F5F9 !important;
color: #0F172A !important;
border: 1px solid #E2E8F0 !important;
border-radius: 12px !important;
padding: 10px 16px !important;
font-weight: 600 !important;
font-size: 14px !important;
box-shadow: none !important;
margin-top: 0.35rem !important;
transition: all 0.15s ease !important;
}
.stApp:has(#login-root) div.stButton:nth-of-type(2) > button:hover {
background: #E2E8F0 !important;
color: #0F172A !important;
}
.login-footer {
text-align: center !important;
font-size: 12px !important;
color: #94A3B8 !important;
margin-top: 1.75rem !important;
font-weight: 400 !important;
letter-spacing: 0.01em !important;
}
</style>"""
    st.markdown(login_css, unsafe_allow_html=True)
    st.markdown("""
        <div id="login-root"></div>
        <div class="login-topbar">
            <div class="login-topbar-inner">
                <div class="login-brand">
                    <div class="login-brand-logo">
                        <svg width="36" height="36" fill="none" viewBox="0 0 96 96" xmlns="http://www.w3.org/2000/svg">
                            <rect fill="#0F172A" height="96" rx="24" width="96"></rect>
                            <path d="M48 20V76M30 32H66M30 32L20 54H40L30 32ZM66 32L56 54H76L66 32Z" stroke="#38BDF8" stroke-linecap="round" stroke-linejoin="round" stroke-width="4"></path>
                            <circle cx="48" cy="20" fill="#0EA5E9" r="4"></circle>
                            <circle cx="30" cy="54" fill="#38BDF8" r="3"></circle>
                            <circle cx="66" cy="54" fill="#38BDF8" r="3"></circle>
                            <circle cx="48" cy="76" fill="#38BDF8" r="4"></circle>
                        </svg>
                    </div>
                    <div class="login-brand-text">
                        <span class="login-brand-title">Legal AI Hub</span>
                        <span class="login-brand-tagline">Judicial Intelligence Suite</span>
                    </div>
                </div>
            </div>
        </div>
        <div class="login-header">
            <div class="login-emblem-wrapper">
                <div class="login-emblem-icon">
                    <svg width="48" height="48" fill="none" viewBox="0 0 96 96" xmlns="http://www.w3.org/2000/svg">
                        <rect fill="#0F172A" height="96" rx="24" width="96"></rect>
                        <path d="M48 20V76M30 32H66M30 32L20 54H40L30 32ZM66 32L56 54H76L66 32Z" stroke="#38BDF8" stroke-linecap="round" stroke-linejoin="round" stroke-width="4"></path>
                        <circle cx="48" cy="20" fill="#0EA5E9" r="4"></circle>
                        <circle cx="30" cy="54" fill="#38BDF8" r="3"></circle>
                        <circle cx="66" cy="54" fill="#38BDF8" r="3"></circle>
                        <circle cx="48" cy="76" fill="#38BDF8" r="4"></circle>
                    </svg>
                </div>
            </div>
            <h1 class="login-title">Legal AI Hub</h1>
            <p class="login-subtitle">Sign in to access your judicial analytics workspace</p>
        </div>
    """, unsafe_allow_html=True)

    with st.container(border=True):
        st.markdown('<span id="login-card-anchor" style="display:none;"></span>', unsafe_allow_html=True)
        st.markdown('<label class="chamber-label">CHAMBER JURISDICTION</label>', unsafe_allow_html=True)
        role = st.radio("Select Role", ["Student", "Lawyer", "Judge", "Admin"], index=3, horizontal=True, label_visibility="collapsed", key="auth_role_selector")

        email = st.text_input("Email Address", placeholder="name@firm.com")
        password = st.text_input("Password", type="password", placeholder="Enter your password")

        st.markdown("<div style='height: 0.25rem;'></div>", unsafe_allow_html=True)

        if st.button("Sign In →", use_container_width=True):
            if not email or not password:
                st.warning("Please enter both email and password.")
            elif supabase:
                try:
                    res = supabase.auth.sign_in_with_password({"email": email, "password": password})
                    if res and res.user:
                        user_id = res.user.id
                        fetched_role = None
                        try:
                            profile_res = supabase.table('profiles').select('role').eq('user_id', user_id).execute()
                            if profile_res.data and len(profile_res.data) > 0:
                                fetched_role = profile_res.data[0].get('role')
                        except Exception:
                            pass
                        st.session_state.authenticated = True
                        st.session_state.user_id = user_id
                        st.session_state.user_email = email
                        if fetched_role:
                            st.session_state.role = fetched_role
                        else:
                            st.session_state.role = "Student"
                        st.rerun()
                    else:
                        st.error("Authentication failed. Invalid user credentials.")
                except Exception as err:
                    st.error(f"Sign in failed: {err}")
            else:
                st.session_state.authenticated = True
                st.session_state.user_id = "demo-offline-uid"
                st.session_state.user_email = email if email else f"{role.lower()}@legalai.in"
                st.session_state.role = role
                st.rerun()

        if st.button("Create Account", use_container_width=True):
            if supabase and email and password:
                try:
                    res = supabase.auth.sign_up({"email": email, "password": password})
                    if res and res.user:
                        st.success("Account created successfully as Student! Please sign in. (Role upgrades can be requested from your workspace).")
                    else:
                        st.error("Registration failed.")
                except Exception as err:
                    st.error(f"Registration failed: {err}")
            else:
                st.warning("Please enter email and password to register.")

    st.markdown('<div class="login-footer">Legal AI Hub • InLegalBERT</div>', unsafe_allow_html=True)

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  CASE PREDICTOR
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
def render_predictor():
    predictor_css = """<style>
.stApp:has(#predictor-root) .block-container {
max-width: 1120px !important;
margin: 0 auto !important;
padding-top: 1.5rem !important;
padding-bottom: 3.5rem !important;
}
.stApp:has(#predictor-root) .predictor-header {
margin-bottom: 1.25rem !important;
text-align: left !important;
}
.stApp:has(#predictor-root) .predictor-header .badge {
margin-bottom: 0.4rem !important;
font-size: 0.68rem !important;
letter-spacing: 0.05em !important;
padding: 0.25rem 0.65rem !important;
}
.stApp:has(#predictor-root) .predictor-title {
font-size: 1.85rem !important;
font-weight: 800 !important;
color: #041534 !important;
margin: 0.15rem 0 0.25rem 0 !important;
letter-spacing: -0.025em !important;
line-height: 1.25 !important;
}
.stApp:has(#predictor-root) .predictor-subtitle {
color: #45464E !important;
font-size: 0.92rem !important;
margin: 0 !important;
line-height: 1.5 !important;
}
.stApp:has(#predictor-root) div[data-testid="stVerticalBlockBorderWrapper"]:has(#predictor-filters-card),
.stApp:has(#predictor-root) div[data-testid="stVerticalBlockBorderWrapper"]:has(#predictor-upload-card),
.stApp:has(#predictor-root) div[data-testid="stVerticalBlockBorderWrapper"]:has(#predictor-results-card) {
background: #FFFFFF !important;
border: 1px solid #E5EEFF !important;
border-radius: 12px !important;
box-shadow: 0 1px 8px rgba(0,0,0,0.04) !important;
padding: 20px 22px !important;
}
.stApp:has(#predictor-root) div[data-testid="stVerticalBlockBorderWrapper"]:has(#predictor-filters-card) {
margin-bottom: 1.25rem !important;
padding: 16px 20px !important;
}
.stApp:has(#predictor-root) div:has(#predictor-filters-card) div[data-testid="stSelectbox"] label,
.stApp:has(#predictor-root) div:has(#predictor-filters-card) div[data-testid="stTextInput"] label {
font-size: 11px !important;
font-weight: 700 !important;
text-transform: uppercase !important;
letter-spacing: 0.06em !important;
color: #45464E !important;
margin-bottom: 6px !important;
}
.stApp:has(#predictor-root) div:has(#predictor-filters-card) div[data-testid="stSelectbox"] div[role="button"],
.stApp:has(#predictor-root) div:has(#predictor-filters-card) div[data-testid="stTextInput"] input {
height: 40px !important;
min-height: 40px !important;
border-radius: 8px !important;
border: 1px solid #E5EEFF !important;
background: #FFFFFF !important;
color: #0B1C30 !important;
font-size: 0.88rem !important;
padding: 0 12px !important;
display: flex !important;
align-items: center !important;
box-shadow: none !important;
transition: border-color 0.2s ease, box-shadow 0.2s ease !important;
}
.stApp:has(#predictor-root) div:has(#predictor-filters-card) div[data-testid="stSelectbox"] div[role="button"]:focus,
.stApp:has(#predictor-root) div:has(#predictor-filters-card) div[data-testid="stSelectbox"] div[role="button"]:focus-visible,
.stApp:has(#predictor-root) div:has(#predictor-filters-card) div[data-testid="stTextInput"] input:focus {
border-color: #041534 !important;
box-shadow: 0 0 0 3px rgba(4,21,52,0.1) !important;
outline: none !important;
}
.stApp:has(#predictor-root) div[data-testid="stHorizontalBlock"] {
gap: 20px !important;
align-items: flex-start !important;
}
.card-header {
display: flex !important;
align-items: center !important;
justify-content: space-between !important;
margin-bottom: 1rem !important;
padding-bottom: 0.6rem !important;
border-bottom: 1px solid #EFF4FF !important;
}
.card-title {
font-family: 'Plus Jakarta Sans', sans-serif !important;
font-size: 1.05rem !important;
font-weight: 700 !important;
color: #041534 !important;
margin: 0 !important;
line-height: 1.3 !important;
}
.card-badge {
font-size: 10px !important;
font-weight: 700 !important;
color: #45464E !important;
background: #EFF4FF !important;
padding: 2px 8px !important;
border-radius: 4px !important;
text-transform: uppercase !important;
letter-spacing: 0.05em !important;
}
.stApp:has(#predictor-root) div[data-testid="stFileUploader"] {
background: #F8F9FF !important;
border: 2px dashed #C5C6CF !important;
border-radius: 10px !important;
padding: 1.75rem 1.25rem !important;
transition: all 0.2s ease !important;
}
.stApp:has(#predictor-root) div[data-testid="stFileUploader"]:hover {
border-color: #041534 !important;
background: #EFF4FF !important;
}
.result-banner {
background: #F8F9FF !important;
border-radius: 10px !important;
padding: 16px !important;
margin-bottom: 1rem !important;
border: 1px solid #E5EEFF !important;
}
.stApp:has(#predictor-root) div[data-testid="stAlert"] {
border-radius: 10px !important;
margin-top: 0.75rem !important;
margin-bottom: 0.75rem !important;
}
@media (max-width: 900px) {
.stApp:has(#predictor-root) div[data-testid="stHorizontalBlock"] {
flex-direction: column !important;
gap: 16px !important;
}
.stApp:has(#predictor-root) div[data-testid="stHorizontalBlock"] > div {
width: 100% !important;
min-width: 100% !important;
}
}
</style>"""
    st.markdown(predictor_css, unsafe_allow_html=True)
    st.markdown("""
        <div id="predictor-root"></div>
        <div class="predictor-header">
            <span class="badge badge-navy">AI PREDICTION ENGINE</span>
            <h1 class="predictor-title">Case Prediction Analytics</h1>
            <p class="predictor-subtitle">Upload court documents for AI-powered jurisdiction and outcome prediction.</p>
        </div>
    """, unsafe_allow_html=True)

    with st.container(border=True):
        st.markdown('<span id="predictor-filters-card" style="display:none;"></span>', unsafe_allow_html=True)
        f1, f2, f3 = st.columns(3)
        with f1:
            case_category = st.selectbox("Domain", ["Criminal Law", "Civil Law", "Constitutional Law"])
        with f2:
            court_level = st.selectbox("Court Level", ["Supreme Court of India", "High Court", "District Court"])
        with f3:
            statutory_tags = st.text_input("Statutory Tags", placeholder="e.g., Section 302")

    st.markdown("<div style='height: 0.5rem;'></div>", unsafe_allow_html=True)

    col_left, col_right = st.columns([1, 1], gap="large")

    with col_left:
        with st.container(border=True):
            st.markdown('<span id="predictor-upload-card" style="display:none;"></span>', unsafe_allow_html=True)
            st.markdown('<div class="card-header"><h3 class="card-title">Upload Document</h3><span class="card-badge">PDF, TXT</span></div>', unsafe_allow_html=True)
            if t_b is None or m_b is None or t_c is None or m_c is None:
                if model_load_error == "files_missing":
                    st.warning("⚠️ Deep learning models (InLegalBERT) are unavailable: Model weights or config files are missing in `./models/`. Predictions are running in rule-based heuristic fallback mode.")
                elif model_load_error == "out_of_memory":
                    st.warning("⚠️ Deep learning models (InLegalBERT) are unavailable: System out of memory / page file exhausted (OS Error 1455). Please run inside the project virtual environment (`venv`). Predictions are running in rule-based heuristic fallback mode.")
                elif model_load_error == "transformers_unavailable":
                    st.warning("⚠️ Deep learning models (InLegalBERT) are unavailable: PyTorch or Transformers is not installed. Predictions are running in rule-based heuristic fallback mode.")
                else:
                    st.warning(f"⚠️ Deep learning models (InLegalBERT) are unavailable ({model_load_error}). Predictions are running in rule-based heuristic fallback mode.")

            file = st.file_uploader("Upload PDF or TXT file", type=["pdf", "txt"], label_visibility="collapsed")

            if file:
                with st.spinner("Analyzing document..."):
                    text = extract_text_from_pdf(file) if file.type == "application/pdf" else file.getvalue().decode('utf-8', errors='ignore')
                    clean = translate_laws_to_bns(clean_legal_text(text))
                    struct_d, crit = structure_aware_chunking(clean)

                    # Basic sanity check: verify whether document looks like a court judgment
                    legal_keywords = ["court", "judgment", "appellant", "respondent", "petition", "order", "section", "act"]
                    has_structured_sections = any(bool(struct_d.get(k)) for k in ["FACTS", "ARGUMENTS", "JUDGMENT"])
                    clean_lower = clean.lower()
                    keyword_hits = [kw for kw in legal_keywords if re.search(r'\b' + re.escape(kw) + r'\b', clean_lower)]
                    # Require genuine legal terminology (word boundaries), preventing false positives from words like 'competition' or 'react'
                    is_likely_legal = (len(keyword_hits) >= 2) and (has_structured_sections or len(keyword_hits) >= 3)

                    if not is_likely_legal:
                        st.warning("⚠️ Document Notice: This document does not appear to be a court judgment or legal petition (no judicial sections or statutory citations were recognized). Predictions may be unreliable.")

                    cat, cat_c = predict(crit, t_b, m_b, {0: "Civil Law", 1: "Criminal Law", 2: "Constitutional Law"}, task="jurisdiction")
                    outc, outc_c = predict(crit, t_c, m_c, {0: "Dismissed / Rejected", 1: "Allowed / Accepted"}, task="outcome")

                    st.session_state.predictions = {
                        "category": cat, "cat_conf": cat_c,
                        "outcome": outc, "out_conf": outc_c,
                        "file": file.name, "text": clean, "struct": struct_d,
                        "is_likely_legal": is_likely_legal
                    }

                    if supabase:
                        try:
                            supabase.table("case_predictions").insert({
                                "user_email": st.session_state.user_email,
                                "filename": file.name,
                                "predicted_jurisdiction": cat,
                                "jurisdiction_confidence": cat_c,
                                "predicted_outcome": outc,
                                "outcome_confidence": outc_c
                            }).execute()
                        except Exception:
                            pass

    with col_right:
        with st.container(border=True):
            st.markdown('<span id="predictor-results-card" style="display:none;"></span>', unsafe_allow_html=True)
            st.markdown('<div class="card-header"><h3 class="card-title">Prediction Results</h3></div>', unsafe_allow_html=True)
            if st.session_state.predictions:
                p = st.session_state.predictions
                is_likely_legal = p.get('is_likely_legal', True)

                if is_likely_legal:
                    is_favorable = "Allow" in p['outcome'] or "Accept" in p['outcome']
                    badge_class = "badge-favorable" if is_favorable else "badge-risk"
                    accent = "#059669" if is_favorable else "#DC2626"

                    st.markdown(f"""
                        <div class="result-banner" style="border-left: 4px solid {accent} !important;">
                            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 1.25rem;">
                                <span class="badge {badge_class}">{p['outcome']}</span>
                                <span style="color: #45464E; font-size: 0.78rem;">{p['file']}</span>
                            </div>
                            <div style="margin-bottom: 1.25rem;">
                                <div style="font-size: 0.75rem; color: #45464E; font-weight: 700; text-transform: uppercase; letter-spacing: 0.05em;">Jurisdiction</div>
                                <div style="font-size: 1.3rem; font-weight: 700; color: #041534; margin-top: 0.15rem;">{p['category']}</div>
                                <div style="font-size: 0.78rem; color: #3F5D9B; margin-top: 0.1rem; font-weight: 600;">{p['cat_conf']:.1f}% confidence</div>
                            </div>
                            <div>
                                <div style="font-size: 0.78rem; color: #45464E; display: flex; justify-content: space-between; font-weight: 600;">
                                    <span>Outcome Confidence</span>
                                    <span style="color: {accent}; font-weight: 700;">{p['out_conf']:.1f}%</span>
                                </div>
                                <div style="margin-top: 0.5rem; height: 6px; background: #E5EEFF; border-radius: 999px; overflow: hidden;">
                                    <div style="width: {p['out_conf']}%; height: 100%; background: {accent}; border-radius: 999px; transition: width 0.5s ease;"></div>
                                </div>
                            </div>
                        </div>
                    """, unsafe_allow_html=True)
                else:
                    st.markdown(f"""
                        <div class="result-banner" style="border-left: 4px solid #94A3B8 !important;">
                            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 1.25rem;">
                                <span class="badge badge-slate">UNRELIABLE — NOT A LEGAL DOCUMENT</span>
                                <span style="color: #45464E; font-size: 0.78rem;">{p['file']}</span>
                            </div>
                            <div style="margin-bottom: 1.25rem;">
                                <div style="font-size: 0.75rem; color: #45464E; font-weight: 700; text-transform: uppercase; letter-spacing: 0.05em;">Jurisdiction</div>
                                <div style="font-size: 1.3rem; font-weight: 700; color: #45464E; margin-top: 0.15rem;">Not applicable</div>
                            </div>
                            <div>
                                <div style="font-size: 0.78rem; color: #45464E; font-weight: 600; margin-bottom: 0.25rem;">Outcome Confidence</div>
                                <div style="font-size: 0.8rem; color: #45464E; line-height: 1.4;">Confidence not meaningful — document does not appear to be a court judgment.</div>
                            </div>
                        </div>
                    """, unsafe_allow_html=True)

                if st.button("Save to Research Vault", use_container_width=True, disabled=not p.get('is_likely_legal', True)):
                    if supabase:
                        try:
                            supabase.table("cases_vault").insert({
                                "title": p['file'],
                                "summary": p['text'][:500],
                                "predicted_outcome": p['outcome'],
                                "ratio_decidendi": p['struct'].get('JUDGMENT', '')[:500],
                                "user_email": st.session_state.user_email,
                                "case_category": p['category'],
                                "jurisdiction_confidence": p['cat_conf'],
                                "outcome_confidence": p['out_conf']
                            }).execute()
                            st.success("Case saved to Research Vault successfully.")
                        except Exception as e:
                            st.error(f"Error saving: {e}")
                    else:
                        st.warning("Database offline — cannot save.")
            else:
                st.markdown("""
                    <div style="text-align: center; padding: 3.5rem 1.5rem; background: #F8F9FF; border-radius: 10px; border: 1px dashed #C5C6CF;">
                        <span class="material-symbols-outlined" style="font-size: 42px; color: #C5C6CF; display: block; margin-bottom: 0.75rem;">query_stats</span>
                        <h4 style="font-size: 1rem; font-weight: 700; color: #041534; margin-bottom: 0.35rem;">Awaiting Document Upload</h4>
                        <p style="color: #45464E; font-size: 0.82rem; max-width: 240px; margin: 0 auto;">Upload a PDF or TXT file to generate AI predictions.</p>
                    </div>
                """, unsafe_allow_html=True)

    # Document inspection tabs
    if st.session_state.predictions:
        st.markdown("<div style='height: 2rem;'></div>", unsafe_allow_html=True)
        st.markdown("<h4 style='font-weight: 700; color: #041534; margin-bottom: 1rem;'>Document Analysis</h4>", unsafe_allow_html=True)

        tab_f, tab_a, tab_j, tab_full = st.tabs(["Facts", "Arguments", "Judgment", "Full Text"])
        p = st.session_state.predictions

        with tab_f:
            content = p['struct'].get('FACTS') or 'No facts section detected.'
            st.markdown(f"<div class='pro-card' style='font-size: 0.9rem; line-height: 1.7; color: #334155;'>{content}</div>", unsafe_allow_html=True)
        with tab_a:
            content = p['struct'].get('ARGUMENTS') or 'No arguments section detected.'
            st.markdown(f"<div class='pro-card' style='font-size: 0.9rem; line-height: 1.7; color: #334155;'>{content}</div>", unsafe_allow_html=True)
        with tab_j:
            content = p['struct'].get('JUDGMENT') or 'No judgment section detected.'
            st.markdown(f"<div class='pro-card' style='font-size: 0.9rem; line-height: 1.7; color: #334155;'>{content}</div>", unsafe_allow_html=True)
        with tab_full:
            st.text_area("Full processed text", value=p['text'], height=350, disabled=True)

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  RESEARCH VAULT
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
def render_vault():
    st.markdown("""
        <div class="animate-in" style='margin-bottom: 2rem;'>
            <span class="badge badge-navy" style="margin-bottom: 0.5rem;">Research Vault</span>
            <h1 style="font-weight: 800; font-size: 2.2rem; color: #0F172A; margin: 0; letter-spacing: -0.02em;">Research Vault</h1>
            <p style='color: #64748B; font-size: 0.95rem; margin-top: 0.35rem;'>Your private repository of analyzed cases and legal intelligence.</p>
        </div>
    """, unsafe_allow_html=True)

    if not supabase:
        st.warning("Database is offline. Cannot fetch vault data.")
        return

    try:
        cases = supabase.table("cases_vault").select("*").order("created_at", desc=True).limit(12).execute().data
        if not cases:
            st.markdown("""
                <div class="pro-card" style="text-align: center; padding: 4rem 2rem !important; border-style: dashed !important; background: #FAFBFC !important;">
                    <span class="material-symbols-outlined" style="font-size: 48px; color: #CBD5E1; display: block; margin-bottom: 0.75rem;">inventory_2</span>
                    <h4 style="color: #475569; margin-bottom: 0.35rem;">Vault is Empty</h4>
                    <p style="color: #94A3B8; font-size: 0.85rem;">Analyze cases in the Case Predictor to populate your vault.</p>
                </div>
            """, unsafe_allow_html=True)
        else:
            for i in range(0, len(cases), 3):
                chunk = cases[i:i+3]
                cols = st.columns(3)
                for idx, c in enumerate(chunk):
                    with cols[idx]:
                        outcome = c.get('predicted_outcome', 'Unknown')
                        is_fav = 'Allow' in outcome or 'Accept' in outcome
                        badge_class = "badge-favorable" if is_fav else "badge-risk"
                        clean_title = html.escape(re.sub(r'\s+', ' ', str(c.get('title','Untitled'))).strip())
                        clean_summary = html.escape(re.sub(r'\s+', ' ', str(c.get('summary') or 'No summary available.')).strip()[:200])

                        st.markdown(f"""
                            <div class="pro-card" style="height: 100%; display: flex; flex-direction: column; justify-content: space-between;">
                                <div>
                                    <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.75rem;">
                                        <span class="badge badge-blue">{c.get('case_category', 'General')}</span>
                                        <span style="font-size: 0.72rem; color: #94A3B8;">{str(c.get('created_at',''))[:10]}</span>
                                    </div>
                                    <h4 style="font-size: 1.05rem; font-weight: 700; color: #0F172A; margin: 0 0 0.5rem 0; line-height: 1.35;">{clean_title}</h4>
                                    <p style="font-size: 0.8rem; color: #64748B; line-height: 1.6; margin-bottom: 1rem; height: 64px; overflow: hidden; display: -webkit-box; -webkit-line-clamp: 3; -webkit-box-orient: vertical;">{clean_summary}</p>
                                </div>
                                <div style="padding-top: 0.75rem; border-top: 1px solid #F1F5F9; display: flex; justify-content: space-between; align-items: center;">
                                    <span class="badge {badge_class}">{outcome}</span>
                                    <span style="font-weight: 700; color: #1E3A5F; font-size: 0.95rem;">{c.get('outcome_confidence', 0.0):.1f}%</span>
                                </div>
                            </div>
                        """, unsafe_allow_html=True)
    except Exception as e:
        st.error(f"Error loading vault: {e}")

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  IPC-BNS LAB
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
def lookup_statute(prompt: str, mapping: dict):
    if not prompt or not mapping:
        return []
    cleaned = prompt.strip().lower()
    if not cleaned:
        return []

    results = []
    seen = set()

    # 1. Section number search
    sec_match = re.search(r'\d+[A-Za-z]?', cleaned)
    if sec_match:
        sec_num = sec_match.group(0).lower()
        pattern = re.compile(rf'\b{re.escape(sec_num)}\b', re.IGNORECASE)
        for k, v in mapping.items():
            if pattern.search(k):
                pair = (k, v)
                if pair not in seen:
                    seen.add(pair)
                    results.append(pair)
                if len(results) >= 5:
                    return results

    # 2. Keyword search if no section match and cleaned prompt >= 3 chars
    if not results and len(cleaned) >= 3:
        for k, v in mapping.items():
            k_lower = k.lower()
            v_lower = str(v).lower()
            if cleaned in k_lower or cleaned in v_lower:
                pair = (k, v)
                if pair not in seen:
                    seen.add(pair)
                    results.append(pair)
                if len(results) >= 5:
                    return results

    return results[:5]

def render_lab():
    st.markdown("""
        <div class="animate-in" style='margin-bottom: 2rem;'>
            <span class="badge badge-navy" style="margin-bottom: 0.5rem;">Statutory Lab</span>
            <h1 style="font-weight: 800; font-size: 2.2rem; color: #0F172A; margin: 0; letter-spacing: -0.02em;">IPC-BNS Translation Lab</h1>
            <p style='color: #64748B; font-size: 0.95rem; margin-top: 0.35rem;'>AI-powered consultation for mapping legacy IPC codes to modern BNS equivalents.</p>
        </div>
    """, unsafe_allow_html=True)

    # Determine last searched query to filter relevant cases
    last_query = st.session_state.get('last_statute_query', '')
    if not last_query and st.session_state.get('chat_history'):
        for msg in reversed(st.session_state.chat_history):
            if msg.get('role') == 'user':
                last_query = msg.get('content', '')
                break

    related_cases = []
    if last_query and supabase:
        sec_m = re.search(r'\d+[A-Za-z]?', last_query)
        filter_term = sec_m.group(0) if sec_m else (last_query.strip() if len(last_query.strip()) >= 3 else "")
        if filter_term:
            try:
                clean_term = re.sub(r'[%_,\(\)]', '', filter_term).strip()
                if clean_term:
                    res = supabase.table("cases_vault").select("*").or_(
                        f"title.ilike.%{clean_term}%,summary.ilike.%{clean_term}%"
                    ).limit(3).execute()
                    related_cases = res.data or []
            except Exception as e:
                logger.warning(f"Error fetching related cases: {e}")
                related_cases = []

    col_sidebar, col_chat = st.columns([1, 2.2], gap="large")

    with col_sidebar:
        if related_cases:
            st.markdown("<h4 style='font-weight: 700; color: #0F172A; margin-bottom: 0.75rem;'>Related Cases</h4>", unsafe_allow_html=True)
            for c in related_cases:
                c_title = html.escape(re.sub(r'\s+', ' ', str(c.get('title', 'Untitled'))).strip())
                c_summary = html.escape(re.sub(r'\s+', ' ', str(c.get('summary') or '')).strip()[:100])
                st.markdown(f"""
                    <div class="pro-card" style="padding: 1.1rem !important; margin-bottom: 0.75rem !important;">
                        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.4rem;">
                            <span class="badge badge-blue" style="font-size: 0.6rem;">{c.get('case_category','General')}</span>
                        </div>
                        <h5 style="font-size: 0.85rem; font-weight: 700; color: #0F172A; margin: 0 0 0.25rem 0;">{c_title}</h5>
                        <p style="font-size: 0.72rem; color: #64748B; margin: 0; line-height: 1.5; height: 32px; overflow: hidden;">{c_summary}</p>
                    </div>
                """, unsafe_allow_html=True)

    with col_chat:
        st.markdown("<h4 style='font-weight: 700; color: #0F172A; margin-bottom: 0.75rem;'>AI Legal Assistant</h4>", unsafe_allow_html=True)

        with st.container():
            if not st.session_state.chat_history:
                st.markdown("""
                    <div style="text-align: center; padding: 4rem 0; min-height: 300px;">
                        <span class="material-symbols-outlined" style="font-size: 48px; color: #CBD5E1; display: block; margin-bottom: 0.75rem;">forum</span>
                        <h4 style="color: #475569; margin-bottom: 0.25rem;">Start a Conversation</h4>
                        <p style="color: #94A3B8; font-size: 0.82rem; max-width: 280px; margin: 0 auto;">Ask about IPC sections, BNS mappings, or legal precedents.</p>
                    </div>
                """, unsafe_allow_html=True)
            else:
                for msg in st.session_state.chat_history:
                    if msg["role"] == "user":
                        st.markdown(f"""
                            <div style="display: flex; justify-content: flex-end; margin-bottom: 1rem;">
                                <div style="background: #1E3A5F; color: #FFFFFF; border-radius: 14px 14px 4px 14px; padding: 0.85rem 1.15rem; max-width: 75%; font-size: 0.9rem; line-height: 1.6;">
                                    {msg['content']}
                                </div>
                            </div>
                        """, unsafe_allow_html=True)
                    else:
                        st.markdown(f"""
                            <div style="display: flex; justify-content: flex-start; align-items: flex-start; gap: 0.6rem; margin-bottom: 1rem;">
                                <div style="display: flex; align-items: center; justify-content: center; width: 30px; height: 30px; background: #EFF6FF; border-radius: 50%; flex-shrink: 0;">
                                    <span class="material-symbols-outlined" style="font-size: 16px; color: #1E3A5F;">smart_toy</span>
                                </div>
                                <div style="background: #F8FAFC; border: 1px solid #E2E8F0; border-radius: 4px 14px 14px 14px; padding: 0.85rem 1.15rem; max-width: 75%; font-size: 0.9rem; line-height: 1.6; color: #334155;">
                                    {msg['content']}
                                </div>
                            </div>
                        """, unsafe_allow_html=True)

        prompt = st.chat_input("Ask about IPC sections, BNS mappings, or legal concepts...")
        if prompt:
            st.session_state['last_statute_query'] = prompt
            st.session_state.chat_history.append({"role": "user", "content": prompt})
            matches = lookup_statute(prompt, ipc_to_bns_map)
            if matches:
                if len(matches) == 1:
                    ipc_key, bns_val = matches[0]
                    response = f"**Match Found:**\n\nIPC Section **{ipc_key.title()}** → BNS Section **{bns_val}**\n\nThis mapping is part of the Bharatiya Nyaya Sanhita (BNS) framework."
                else:
                    lines = [f"• **{k.title()}** → **{v}**" for k, v in matches]
                    match_str = "\n".join(lines)
                    response = f"**Matches Found ({len(matches)}):**\n\n{match_str}\n\nThis mapping is part of the Bharatiya Nyaya Sanhita (BNS) framework."
            else:
                response = f"No exact IPC/BNS match found for '{prompt}'. Try entering a specific section number (e.g. 302) or a keyword (e.g. murder)."

            st.session_state.chat_history.append({"role": "assistant", "content": response})

            if supabase:
                try:
                    supabase.table("student_queries").insert({
                        "user_email": st.session_state.user_email,
                        "query_text": prompt,
                        "ai_response": response
                    }).execute()
                except Exception:
                    pass
            st.rerun()

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  CASE HISTORY
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
def render_history():
    st.markdown("""
        <div class="animate-in" style='margin-bottom: 2rem;'>
            <span class="badge badge-navy" style="margin-bottom: 0.5rem;">Audit Log</span>
            <h1 style="font-weight: 800; font-size: 2.2rem; color: #0F172A; margin: 0; letter-spacing: -0.02em;">Case History</h1>
            <p style='color: #64748B; font-size: 0.95rem; margin-top: 0.35rem;'>Complete log of your AI prediction operations.</p>
        </div>
    """, unsafe_allow_html=True)

    if not supabase:
        st.warning("Database is offline. Cannot fetch history.")
        return

    hist = []
    try:
        hist = get_history()
    except Exception as e:
        st.error(f"Failed to load case history: {e}")
        hist = []

    if hist:
        import pandas as pd
        df = pd.DataFrame(hist)
        user_role = st.session_state.get('role', 'Student')
        cols = ['filename', 'predicted_jurisdiction', 'jurisdiction_confidence', 'predicted_outcome', 'outcome_confidence', 'created_at']
        col_names = {
            'filename': 'Case File',
            'predicted_jurisdiction': 'Jurisdiction',
            'jurisdiction_confidence': 'Jurisdiction %',
            'predicted_outcome': 'Outcome',
            'outcome_confidence': 'Confidence %',
            'created_at': 'Date'
        }
        if user_role == 'Admin' and 'user_email' in df.columns:
            cols = ['user_email'] + cols
            col_names['user_email'] = 'User Email'

        available_cols = [c for c in cols if c in df.columns]
        clean_df = df[available_cols].copy()
        clean_df.rename(columns=col_names, inplace=True)
        st.dataframe(clean_df, use_container_width=True, hide_index=True)
    else:
        st.markdown("""
            <div class="pro-card" style="text-align: center; padding: 4rem 2rem !important; border-style: dashed !important; background: #FAFBFC !important;">
                <span class="material-symbols-outlined" style="font-size: 48px; color: #CBD5E1; display: block; margin-bottom: 0.75rem;">history</span>
                <h4 style="color: #475569; margin-bottom: 0.35rem;">No saved cases yet</h4>
                <p style="color: #94A3B8; font-size: 0.85rem;">Upload case documents in the Predictor to start tracking predictions.</p>
            </div>
        """, unsafe_allow_html=True)

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  ROLE REQUESTS MANAGEMENT (ADMIN ONLY)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
def render_role_requests():
    st.markdown("""
        <div class="animate-in" style='margin-bottom: 2rem;'>
            <span class="badge badge-navy" style="margin-bottom: 0.5rem;">Access Control</span>
            <h1 style="font-weight: 800; font-size: 2.2rem; color: #0F172A; margin: 0; letter-spacing: -0.02em;">Role Upgrade Requests</h1>
            <p style='color: #64748B; font-size: 0.95rem; margin-top: 0.35rem;'>Review and process role elevation requests submitted by registered users.</p>
        </div>
    """, unsafe_allow_html=True)

    if not supabase:
        st.warning("Database offline. Cannot manage role requests.")
        return

    try:
        reqs = supabase.table('role_requests').select('*').order('requested_at', desc=True).execute().data
    except Exception as e:
        st.error(f"Error fetching role requests: {e}")
        return

    pending = [r for r in reqs if r.get('status') == 'pending']
    resolved = [r for r in reqs if r.get('status') != 'pending']

    # Metrics
    m1, m2, m3 = st.columns(3)
    with m1:
        st.metric("Pending Requests", len(pending))
    with m2:
        st.metric("Total Approved", len([r for r in resolved if r.get('status') == 'approved']))
    with m3:
        st.metric("Total Rejected", len([r for r in resolved if r.get('status') == 'rejected']))

    st.markdown("<div style='height: 1.5rem;'></div>", unsafe_allow_html=True)

    tab_pending, tab_history = st.tabs(["⏳ Pending Approvals", "📜 Resolved History"])

    with tab_pending:
        if not pending:
            st.markdown("""
                <div class="pro-card" style="text-align: center; padding: 3.5rem 2rem !important; border-style: dashed !important; background: #FAFBFC !important;">
                    <span class="material-symbols-outlined" style="font-size: 42px; color: #CBD5E1; display: block; margin-bottom: 0.75rem;">verified_user</span>
                    <h4 style="color: #475569; margin-bottom: 0.35rem;">No Pending Requests</h4>
                    <p style="color: #94A3B8; font-size: 0.85rem;">All role elevation requests have been processed.</p>
                </div>
            """, unsafe_allow_html=True)
        else:
            for r in pending:
                r_id = r.get('id')
                u_id = r.get('user_id')
                u_email = r.get('user_email', 'Unknown')
                curr_r = r.get('current_role', 'Student')
                req_r = r.get('requested_role', 'Lawyer')
                r_date = str(r.get('requested_at', ''))[:16].replace('T', ' ')

                st.markdown(f"""
                    <div class="pro-card" style="margin-bottom: 1rem;">
                        <div style="display: flex; justify-content: space-between; align-items: center;">
                            <div>
                                <h4 style="font-size: 1.05rem; font-weight: 700; color: #0F172A; margin: 0 0 0.35rem 0;">{u_email}</h4>
                                <div style="display: flex; align-items: center; gap: 0.5rem; font-size: 0.82rem; color: #64748B;">
                                    <span>Current: <strong style="color: #475569;">{curr_r}</strong></span>
                                    <span>➔</span>
                                    <span>Requested: <strong style="color: #1E40AF;">{req_r}</strong></span>
                                    <span>•</span>
                                    <span>{r_date}</span>
                                </div>
                            </div>
                        </div>
                    </div>
                """, unsafe_allow_html=True)

                col_appr, col_rej, _ = st.columns([1, 1, 3], gap="small")
                with col_appr:
                    if st.button("✅ Approve", key=f"appr_{r_id}", use_container_width=True):
                        try:
                            # 1. Update role_requests table
                            supabase.table('role_requests').update({
                                "status": "approved",
                                "reviewed_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
                                "reviewed_by": st.session_state.user_email
                            }).eq('id', r_id).execute()

                            # 2. Elevate user role in profiles table
                            supabase.table('profiles').update({
                                "role": req_r
                            }).eq('user_id', u_id).execute()

                            st.success(f"Approved {u_email} as {req_r}!")
                            st.rerun()
                        except Exception as act_err:
                            st.error(f"Approval failed: {act_err}")

                with col_rej:
                    if st.button("❌ Reject", key=f"rej_{r_id}", use_container_width=True):
                        try:
                            supabase.table('role_requests').update({
                                "status": "rejected",
                                "reviewed_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
                                "reviewed_by": st.session_state.user_email
                            }).eq('id', r_id).execute()
                            st.info(f"Rejected request for {u_email}.")
                            st.rerun()
                        except Exception as act_err:
                            st.error(f"Rejection failed: {act_err}")

    with tab_history:
        if not resolved:
            st.caption("No processed request history.")
        else:
            import pandas as pd
            h_data = []
            for r in resolved:
                h_data.append({
                    "User": r.get('user_email'),
                    "From Role": r.get('current_role'),
                    "Requested": r.get('requested_role'),
                    "Status": r.get('status', '').upper(),
                    "Reviewed By": r.get('reviewed_by', 'Admin'),
                    "Date": str(r.get('requested_at', ''))[:10]
                })
            st.dataframe(pd.DataFrame(h_data), use_container_width=True, hide_index=True)

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  MAIN ROUTER
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
if not st.session_state.get('authenticated', False):
    render_auth()
else:
    # Clean white sidebar
    with st.sidebar:
        user_email = st.session_state.get('user_email', '')
        user_role = st.session_state.get('role', 'Student')
        user_initial = (user_email[0].upper()) if user_email else "U"

        st.markdown("""
            <div style="padding: 1.25rem 0.5rem 1rem 0.5rem; display: flex; align-items: center; gap: 0.75rem; border-bottom: 1px solid #E5EEFF; margin-bottom: 1rem;">
                <div style="width: 36px; height: 36px; border-radius: 10px; background: #041534; display: flex; align-items: center; justify-content: center; flex-shrink: 0;">
                    <svg width="22" height="22" viewBox="0 0 96 96" fill="none" xmlns="http://www.w3.org/2000/svg">
                        <path d="M48 20V76M30 32H66M30 32L20 54H40L30 32ZM66 32L56 54H76L66 32Z" stroke="#38BDF8" stroke-width="5" stroke-linecap="round" stroke-linejoin="round"/>
                        <circle cx="48" cy="20" r="4" fill="#0EA5E9"/>
                        <circle cx="30" cy="54" r="3" fill="#38BDF8"/>
                        <circle cx="66" cy="54" r="3" fill="#38BDF8"/>
                        <circle cx="48" cy="76" r="4" fill="#38BDF8"/>
                    </svg>
                </div>
                <div style="display: flex; flex-direction: column;">
                    <span style="font-family: 'Plus Jakarta Sans', sans-serif; font-weight: 700; font-size: 1.05rem; color: #041534; line-height: 1.2;">Legal AI Hub</span>
                    <span style="font-size: 11px; font-weight: 500; color: #75777F;">Judicial Analytics</span>
                </div>
            </div>
        """, unsafe_allow_html=True)

        allowed_modules = {
            'Judge': [("📋 Case History", "history")],
            'Lawyer': [("🎯 Case Predictor", "predictor"), ("📚 Research Vault", "vault")],
            'Student': [("🔬 IPC-BNS Lab", "lab")],
            'Admin': [
                ("🎯 Case Predictor", "predictor"),
                ("📚 Research Vault", "vault"),
                ("🔬 IPC-BNS Lab", "lab"),
                ("📋 Case History", "history"),
                ("🛡️ Role Requests", "requests")
            ]
        }.get(user_role, [("🎯 Case Predictor", "predictor")])

        nav_names = [name for name, _ in allowed_modules]
        nav_keys = [key for _, key in allowed_modules]

        current_nav = st.query_params.get("nav", nav_keys[0] if nav_keys else "predictor")
        if current_nav not in nav_keys and nav_keys:
            current_nav = nav_keys[0]

        current_idx = nav_keys.index(current_nav) if current_nav in nav_keys else 0

        selected_module_name = st.radio("Navigation", nav_names, index=current_idx, label_visibility="collapsed")
        active_nav_key = nav_keys[nav_names.index(selected_module_name)]

        if active_nav_key != current_nav:
            st.query_params["nav"] = active_nav_key
            st.rerun()

        st.markdown(f"""
            <div style="margin-top: 1.5rem; padding: 12px; background: #EFF4FF; border: 1px solid #E5EEFF; border-radius: 12px; display: flex; align-items: center; gap: 10px;">
                <div style="width: 34px; height: 34px; border-radius: 50%; background: #041534; color: #FFFFFF; font-weight: 700; font-size: 14px; display: flex; align-items: center; justify-content: center; flex-shrink: 0;">
                    {user_initial}
                </div>
                <div style="display: flex; flex-direction: column; min-width: 0; flex: 1;">
                    <span style="font-weight: 600; color: #041534; font-size: 12.5px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis;">{html.escape(user_email)}</span>
                    <span style="font-size: 11px; color: #45464E; font-weight: 500;">{user_role}</span>
                </div>
            </div>
        """, unsafe_allow_html=True)

        # Role Upgrade Request UI (for non-Admin users)
        if user_role != 'Admin' and supabase:
            with st.expander("🚀 Request Role Upgrade"):
                available_roles = [r for r in ["Lawyer", "Judge", "Admin"] if r != user_role]
                req_role = st.selectbox("Select Target Role", available_roles, key="req_role_select")

                existing_pending = None
                try:
                    uid = st.session_state.get('user_id')
                    query = supabase.table('role_requests').select('*').eq('status', 'pending')
                    if uid:
                        query = query.eq('user_id', uid)
                    else:
                        query = query.eq('user_email', st.session_state.user_email)
                    res = query.execute()
                    if res.data and len(res.data) > 0:
                        existing_pending = res.data[0]
                except Exception:
                    pass

                if existing_pending:
                    st.info(f"⏳ Pending request for **{existing_pending.get('requested_role')}** submitted on {str(existing_pending.get('requested_at',''))[:10]}.")
                else:
                    if st.button("Submit Request", use_container_width=True, key="submit_role_req_btn"):
                        try:
                            uid = st.session_state.get('user_id')
                            if not uid and supabase:
                                try:
                                    u_res = supabase.auth.get_user()
                                    if u_res and hasattr(u_res, 'user') and u_res.user:
                                        uid = u_res.user.id
                                        st.session_state.user_id = uid
                                except Exception:
                                    uid = None

                            if not uid:
                                st.error("Please log in again")
                            else:
                                supabase.table('role_requests').insert({
                                    "user_id": uid,
                                    "user_email": st.session_state.user_email,
                                    "current_role": user_role,
                                    "requested_role": req_role,
                                    "status": "pending"
                                }).execute()
                                st.success(f"Request for {req_role} submitted! An Administrator will review it.")
                                st.rerun()
                        except Exception as req_err:
                            st.error(f"Failed to submit request: {req_err}")

        if st.button("Sign Out", use_container_width=True):
            if supabase is not None:
                try:
                    supabase.auth.sign_out()
                except Exception:
                    pass
            st.session_state.authenticated = False
            st.session_state.user_id = ""
            st.session_state.user_email = ""
            st.session_state.role = ""
            st.session_state.chat_history = []
            st.session_state.predictions = {}
            st.query_params.clear()
            st.rerun()

    # Route to correct page
    if active_nav_key == "predictor":
        render_predictor()
    elif active_nav_key == "vault":
        render_vault()
    elif active_nav_key == "lab":
        render_lab()
    elif active_nav_key == "history":
        render_history()
    elif active_nav_key == "requests":
        render_role_requests()

