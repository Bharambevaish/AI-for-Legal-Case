import json

def get_app_code():
    return '''import streamlit as st
import streamlit.components.v1 as components
import torch
from transformers import AutoTokenizer, AutoModelForSequenceClassification, pipeline
import fitz
import re
import shap
import spacy
import os
import json
from supabase import create_client, Client

# --- PAGE CONFIG ---
st.set_page_config(page_title="The Lucid Architect | Legal AI Hub", layout="wide", initial_sidebar_state="collapsed")

# --- ASSETS ---
IMG_AVATAR = "https://images.unsplash.com/photo-1556157382-97eda2d62296?auto=format&fit=crop&q=80&w=200"
IMG_ATRIUM = "https://images.unsplash.com/photo-1497366216548-37526070297c?auto=format&fit=crop&q=80&w=1200"
IMG_BOOKS = "https://images.unsplash.com/photo-1505664177941-dc06a928923a?auto=format&fit=crop&q=80&w=800"
IMG_SCALES = "https://images.unsplash.com/photo-1589829085413-56de8ae18c73?auto=format&fit=crop&q=80&w=800"

# --- GLOBAL STYLES & HACKS ---
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&display=swap');
@import url('https://fonts.googleapis.com/css2?family=Material+Symbols+Outlined:opsz,wght,FILL,GRAD@24,400,0,0');

/* Hide Streamlit Elements */
[data-testid="stSidebar"], header[data-testid="stHeader"], footer { display: none !important; }

/* Apply styling to body */
.block-container { 
    padding: 0 !important; 
    margin: 0 !important; 
    max-width: 100% !important; 
}
body { font-family: 'Inter', sans-serif !important; background-color: #f7f9fb; }

/* Native Widget Overrides */
[data-testid="stFileUploader"] {
    background: transparent !important;
    border: 2px dashed rgba(188, 201, 198, 0.4) !important;
    border-radius: 0.75rem !important;
    padding: 2rem !important;
}
[data-testid="stFileUploader"]:hover {
    background: rgba(255,255,255,0.5) !important;
    border-color: #00685f !important;
}
[data-testid="stButton"] button {
    background-color: #00685f !important;
    color: white !important;
    border-radius: 0.5rem !important;
    padding: 0.75rem !important;
    font-weight: 700 !important;
    box-shadow: 0 4px 14px rgba(0, 104, 95, 0.2) !important;
    border: none !important;
}
[data-testid="stTextInput"] input {
    background: #e6e8ea !important;
    border: none !important;
    padding: 1rem 1.5rem !important;
    border-radius: 0.3rem !important;
    font-size: 0.95rem !important;
    color: #191c1e !important;
}
[data-testid="stTextInput"] input:focus {
    box-shadow: 0 0 0 2px #00685f !important;
    background: #ffffff !important;
}
[data-testid="stTextInput"] label { display: none !important; }

[data-testid="stChatInput"] {
    background: #ffffff !important;
    border: 1px solid rgba(188, 201, 198, 0.3) !important;
    border-radius: 9999px !important;
    padding: 0.25rem 1rem !important;
    box-shadow: inset 0 2px 4px rgba(0,0,0,0.02) !important;
}
[data-testid="stChatInput"] textarea {
    color: #191c1e !important;
}
</style>
""", unsafe_allow_html=True)

components.html("""
<script>
    if (!window.parent.document.getElementById('t-cdn')) {
        let s = window.parent.document.createElement('script');
        s.id = 't-cdn';
        s.src = 'https://cdn.tailwindcss.com?plugins=forms,container-queries';
        window.parent.document.head.appendChild(s);
        let c = window.parent.document.createElement('script');
        c.innerHTML = `tailwind.config={darkMode:'class',theme:{extend:{colors:{
            'primary':'#00685f','surface':'#f7f9fb','on-surface':'#191c1e',
            'surface-container-high':'#e6e8ea','surface-container-lowest':'#ffffff',
            'surface-container-low':'#f2f4f6','outline-variant':'#bcc9c6',
            'on-surface-variant':'#3d4947','secondary-container':'#c2ebe3',
            'on-secondary-container':'#456b66','tertiary-fixed':'#ffdbce',
            'on-tertiary-fixed':'#370e00'
        }}}}`;
        window.parent.document.head.appendChild(c);
    }
</script>""", height=0)

# --- BACKEND LOGIC ---
@st.cache_resource
def init_connection():
    return create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])

try:
    supabase: Client = init_connection()
except Exception as e:
    st.error("Failed to connect to Supabase.")
    st.stop()

if "authenticated" not in st.session_state:
    st.session_state.authenticated = False
    st.session_state.user_email = ""
    st.session_state.chat_history = []
    st.session_state.predictions = {}

@st.cache_resource
def load_models():
    tokenizer = AutoTokenizer.from_pretrained("law-ai/InLegalBERT", use_fast=False)
    model_b = AutoModelForSequenceClassification.from_pretrained("./models/Module_B/Final")
    model_c = AutoModelForSequenceClassification.from_pretrained("./models/Module_C/Final")
    return tokenizer, model_b, tokenizer, model_c

try:
    nlp = spacy.load("en_core_web_sm")
except OSError:
    nlp = None

def extract_text_from_pdf(pdf_file):
    doc = fitz.open(stream=pdf_file.read(), filetype="pdf")
    return "\\n".join([page.get_text("text") for page in doc])

def clean_legal_text(text):
    pattern = r'(?i)^.*?(?:\\bHEADNOTE\\b[\\s:\\"\\x2D]*|\\n(?<!DATE OF )\\bJUDGMENT\\b[\\s:\\"\\x2D]*|\\n\\s*ORDER\\s*[\\s:\\"\\x2D]*)(\\n|$)'
    cleaned = re.sub(pattern, '', text, count=1, flags=re.DOTALL)
    return cleaned.strip()

@st.cache_data
def load_bns_mapping():
    try:
        with open("bns_mapping.json", 'r') as f:
            return json.load(f)
    except: return {}

ipc_to_bns_map = load_bns_mapping()

def translate_laws_to_bns(text):
    if not ipc_to_bns_map: return text
    for ipc, bns in ipc_to_bns_map.items():
        pattern = re.compile(r'\\b' + re.escape(ipc) + r'\\b', re.IGNORECASE)
        text = pattern.sub(f" [{bns}] ", text)
    return text

def structure_aware_chunking(text):
    sections = {
        "FACTS": r"(?i)(?:brief facts|factual matrix)[\\s\\S]*?(?=\\n(?:arguments|issues|judgment))",
        "ARGUMENTS": r"(?i)(?:arguments|submissions)[\\s\\S]*?(?=\\n(?:issues|judgment))",
        "JUDGMENT": r"(?i)(?:final judgment|order)[\\s\\S]*"
    }
    ext = {}
    for sec, pat in sections.items():
        m = re.search(pat, text)
        ext[sec] = m.group(0).strip() if m else ""
    return ext, (ext.get("FACTS", "") + " " + ext.get("ARGUMENTS", "")) or text[:2000]

def predict(text, t, m, label_map):
    inputs = t(text, padding="max_length", truncation=True, max_length=512, return_tensors="pt")
    with torch.no_grad():
        logits = m(**inputs).logits
        probs = torch.nn.functional.softmax(logits, dim=-1)
        pred_id = torch.argmax(logits, dim=-1).item()
    return label_map[pred_id], probs[0][pred_id].item() * 100

def get_history():
    try: return supabase.table("case_predictions").select("*").eq("user_email", st.session_state.user_email).order('created_at', desc=True).limit(5).execute().data
    except: return []

# --- VIEWS ---
def render_auth():
    auth_mode = st.query_params.get("auth", "login")
    st.markdown(f"""
    <div style="position: absolute; top: 0; left: 0; right: 0; z-index: 9999;" class="bg-surface/85 backdrop-blur-xl px-12 py-6">
        <div class="max-w-screen-2xl mx-auto flex justify-between items-center">
            <div class="text-xl font-bold tracking-tighter">Lucid Architect</div>
            <a href="?auth={'login' if auth_mode == 'signup' else 'signup'}" class="bg-primary text-white px-6 py-2 rounded-lg text-sm font-semibold hover:opacity-90 transition-all">{"Sign In" if auth_mode == "signup" else "Sign Up"}</a>
        </div>
    </div>
    <div class="flex min-h-screen bg-surface">
        <div class="hidden lg:block lg:w-[55%] relative p-12">
            <div class="absolute inset-y-12 inset-x-12 bg-surface-container-high rounded-xl overflow-hidden shadow-2xl">
                <img src="{IMG_ATRIUM}" class="absolute inset-0 w-full h-full object-cover opacity-90"/>
                <div class="absolute inset-0 bg-gradient-to-tr from-primary/30 to-transparent"></div>
                <div class="absolute bottom-12 left-12"><h1 class="text-5xl font-bold text-white tracking-tight leading-[1.1]">The architecture of <span class="text-[#89f5e7]">legal intelligence</span>.</h1></div>
            </div>
        </div>
        <div class="w-full lg:w-[45%] flex items-center justify-center p-12 mt-12">
            <div class="w-full max-w-md bg-white p-10 rounded-xl shadow-[0px_20px_40px_rgba(0,0,0,0.06)] border border-outline-variant/10">
    """, unsafe_allow_html=True)
    
    col_auth1, col_auth2 = st.columns([1,0.01])
    with col_auth1:
        st.markdown(f"<h2 class='text-3xl font-bold mb-2'>{'Welcome Back' if auth_mode=='login' else 'Create your account'}</h2>", unsafe_allow_html=True)
        st.markdown(f"<p class='text-on-surface-variant text-sm mb-8'>Enterprise-grade authentication for v4.0</p>", unsafe_allow_html=True)
        
        email = st.text_input("EMAIL", key="auth_e", placeholder="name@firm.com")
        password = st.text_input("PASS", key="auth_p", type="password", placeholder="••••••••")
        
        st.markdown("<div style='margin-top:20px'></div>", unsafe_allow_html=True)
        btn_label = "Authorize Access" if auth_mode == "login" else "Initialize Account"
        if st.button(btn_label, use_container_width=True):
            if auth_mode == "login":
                try:
                    res = supabase.auth.sign_in_with_password({"email": email, "password": password})
                    st.session_state.authenticated = True
                    st.session_state.user_email = res.user.email
                    st.query_params["nav"] = "predictor"
                    st.rerun()
                except: st.error("Login failed.")
            else:
                try:
                    supabase.auth.sign_up({"email": email, "password": password})
                    st.success("Account created! Please Sign In.")
                except: st.error("Sign up failed.")
    
    st.markdown("""
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)

def render_shell(nav):
    # Top Navbar & Side Rail Wrapper
    st.markdown(f"""
    <div class="fixed top-0 left-0 right-0 z-[99] bg-[#f7f9fb]/90 backdrop-blur-xl border-b border-outline-variant/10">
        <div class="flex justify-between items-center px-12 h-20 w-full max-w-screen-2xl mx-auto">
            <div class="text-xl font-bold tracking-tighter text-primary">The Lucid Architect</div>
            <nav class="hidden md:flex items-center gap-8">
                <a href="/?nav=predictor" class="text-sm font-semibold {'text-primary border-b-2 border-primary' if nav=='predictor' else 'text-on-surface-variant hover:text-primary'} transition-colors px-2 py-1">Case Predictor</a>
                <a href="/?nav=vault" class="text-sm font-semibold {'text-primary border-b-2 border-primary' if nav=='vault' else 'text-on-surface-variant hover:text-primary'} transition-colors px-2 py-1">Research Vault</a>
                <a href="/?nav=solver" class="text-sm font-semibold {'text-primary border-b-2 border-primary' if nav=='solver' else 'text-on-surface-variant hover:text-primary'} transition-colors px-2 py-1">Doubt Solver</a>
                <a href="/?nav=history" class="text-sm font-semibold {'text-primary border-b-2 border-primary' if nav=='history' else 'text-on-surface-variant hover:text-primary'} transition-colors px-2 py-1">Case History</a>
            </nav>
            <div class="flex flex-row items-center gap-4">
                <img src="{IMG_AVATAR}" class="w-10 h-10 rounded-full object-cover border border-outline-variant/20 shadow-sm"/>
                <div class="text-xs text-on-surface font-semibold">{st.session_state.user_email}</div>
            </div>
        </div>
    </div>
    
    <aside class="fixed left-0 top-20 bottom-0 w-20 bg-white border-r border-[#bcc9c6]/15 shadow-[20px_0_40px_rgba(25,28,30,0.04)] flex flex-col items-center py-8 z-[98]">
        <div class="flex flex-col items-center gap-4 w-full">
            <a href="/?nav=predictor" class="flex flex-col items-center gap-1 group w-full py-4 transition-all {'text-primary border-l-2 border-primary bg-surface-container-low' if nav=='predictor' else 'text-on-surface-variant hover:bg-surface-container-low'}">
                <span class="material-symbols-outlined"{ ' style="font-variation-settings: \\'FILL\\' 1;"' if nav=='predictor' else '' }>gavel</span>
                <span class="text-[10px] uppercase font-bold tracking-widest">Predict</span>
            </a>
            <a href="/?nav=vault" class="flex flex-col items-center gap-1 group w-full py-4 transition-all {'text-primary border-l-2 border-primary bg-surface-container-low' if nav=='vault' else 'text-on-surface-variant hover:bg-surface-container-low'}">
                <span class="material-symbols-outlined"{ ' style="font-variation-settings: \\'FILL\\' 1;"' if nav=='vault' else '' }>inventory_2</span>
                <span class="text-[10px] uppercase font-bold tracking-widest">Vault</span>
            </a>
            <a href="/?nav=solver" class="flex flex-col items-center gap-1 group w-full py-4 transition-all {'text-primary border-l-2 border-primary bg-surface-container-low' if nav=='solver' else 'text-on-surface-variant hover:bg-surface-container-low'}">
                <span class="material-symbols-outlined"{ ' style="font-variation-settings: \\'FILL\\' 1;"' if nav=='solver' else '' }>quiz</span>
                <span class="text-[10px] uppercase font-bold tracking-widest">Solver</span>
            </a>
            <a href="/?nav=history" class="flex flex-col items-center gap-1 group w-full py-4 transition-all {'text-primary border-l-2 border-primary bg-surface-container-low' if nav=='history' else 'text-on-surface-variant hover:bg-surface-container-low'}">
                <span class="material-symbols-outlined"{ ' style="font-variation-settings: \\'FILL\\' 1;"' if nav=='history' else '' }>history</span>
                <span class="text-[10px] uppercase font-bold tracking-widest">History</span>
            </a>
        </div>
    </aside>
    """, unsafe_allow_html=True)

def render_predictor():
    st.markdown("""
    <div style="padding: 120px 40px 60px 100px; max-width: 1400px; margin: 0 auto; position: relative; z-index: 1;">
        <h1 class="text-5xl font-extrabold text-on-surface mb-2 tracking-tight">Workspace <span class="italic font-light text-primary">Overview</span></h1>
        <p class="text-lg text-on-surface-variant mb-12">Advanced legal analytics and AI-driven case research.</p>
        
        <div class="bg-surface-container-lowest border border-outline-variant/10 rounded-xl p-8 shadow-sm mb-12">
            <div class="flex gap-3 items-center mb-6">
                <div class="bg-primary text-white p-2 rounded-lg flex items-center"><span class="material-symbols-outlined">analytics</span></div>
                <h2 class="text-2xl font-bold">Case Predictor</h2>
            </div>
    """, unsafe_allow_html=True)
    
    t1, t2 = st.columns([1, 1], gap="medium")
    with t1:
        st.markdown("<div class='mb-6'>", unsafe_allow_html=True)
        file = st.file_uploader("DROP BRIEFING", key="brief")
        st.markdown("</div>", unsafe_allow_html=True)
    with t2:
        if file:
            with st.spinner("Analyzing..."):
                t_b, m_b, t_c, m_c = load_models()
                text = extract_text_from_pdf(file) if file.type == "application/pdf" else file.getvalue().decode()
                clean = translate_laws_to_bns(clean_legal_text(text))
                struct_d, crit = structure_aware_chunking(clean)
                
                cat, cat_c = predict(crit, t_b, m_b, {0: "Civil", 1: "Criminal", 2: "Constitutional"})
                outc, outc_c = predict(crit, t_c, m_c, {0: "Dismissed/Rejected", 1: "Allowed/Accepted"})
                
                st.session_state.predictions = {"category": cat, "cat_conf": cat_c, "outcome": outc, "out_conf": outc_c, "file": file.name, "text": clean, "struct": struct_d}
                
                try:
                    supabase.table("case_predictions").insert({
                        "user_email": st.session_state.user_email, "filename": file.name,
                        "predicted_jurisdiction": cat, "jurisdiction_confidence": cat_c,
                        "predicted_outcome": outc, "outcome_confidence": outc_c
                    }).execute()
                except: pass

        if st.session_state.predictions:
            p = st.session_state.predictions
            color = "primary" if "Allow" in p['outcome'] or "Accept" in p['outcome'] else "red-600"
            state = "Favorable" if color == "primary" else "High Risk"
            st.markdown(f"""
            <div class="bg-primary/5 rounded-xl p-6 border-l-4 border-primary shadow-sm mb-4">
                <h3 class="font-bold text-lg mb-1">Probability Forecast</h3>
                <p class="text-sm text-on-surface-variant mb-4">Jurisdiction: {p['category']} ({p['cat_conf']:.1f}%)</p>
                <div class="flex items-end gap-2 text-{color}">
                    <span class="text-5xl font-black">{p['out_conf']:.1f}%</span>
                    <span class="font-bold uppercase tracking-wide pb-1">{p['outcome']} - {state}</span>
                </div>
            </div>
            """, unsafe_allow_html=True)
            if st.button("💾 Save to Research Vault", use_container_width=True):
                try:
                    supabase.table("cases_vault").insert({
                        "title": p['file'], "summary": p['text'][:500], "predicted_outcome": p['outcome'],
                        "ratio_decidendi": p['struct'].get('JUDGMENT', '')[:500],
                        "uploaded_by": st.session_state.user_email,
                        "case_category": p['category'], "jurisdiction_confidence": p['cat_conf'],
                        "outcome_confidence": p['out_conf']
                    }).execute()
                    st.success("Case saved to Research Vault!")
                except Exception as e:
                    st.error(f"Error saving to Vault: {e}")
                
    st.markdown("</div>", unsafe_allow_html=True)
    
    # RECENT ACTIVITY PREVIEW
    hist = get_history()
    if hist:
        rows = ""
        for r in hist:
            rows += f"""<tr class="hover:bg-surface-container transition-colors border-b border-outline-variant/10">
                <td class="py-4 px-4 font-bold">{r['filename']}</td>
                <td class="py-4 px-4"><span class="px-3 py-1 bg-secondary-container text-on-secondary-container rounded-full text-[10px] uppercase font-bold tracking-widest">{r['predicted_outcome']} ({r['outcome_confidence']:.1f}%)</span></td>
                <td class="py-4 px-4 text-sm text-on-surface-variant">{r['predicted_jurisdiction']}</td>
                <td class="py-4 px-4 text-sm text-on-surface-variant text-right tracking-widest">{r['created_at'][:10]}</td>
            </tr>"""
        st.markdown(f"""
        <div class="mt-8">
            <h3 class="text-2xl font-bold mb-6 tracking-tight">Recent Activity Preview</h3>
            <div class="bg-white rounded-xl shadow-sm overflow-hidden border border-outline-variant/10">
                <table class="w-full text-left">{rows}</table>
            </div>
        </div>
        """, unsafe_allow_html=True)
    st.markdown("</div>", unsafe_allow_html=True)

def render_vault():
    st.markdown("""
    <div style="padding: 120px 40px 60px 100px; max-width: 1400px; margin: 0 auto; position: relative; z-index: 1;">
        <h2 class="text-4xl font-extrabold tracking-tight mb-2">Research Vault</h2>
        <p class="text-lg text-on-surface-variant mb-12">Your firm's private repository of analyzed cases and intelligence.</p>
    """, unsafe_allow_html=True)

    try:
        cases = supabase.table("cases_vault").select("*").order("created_at", desc=True).limit(10).execute().data
        if not cases:
            st.info("Vault is empty. Upload cases via the Case Predictor.")
        else:
            cards = ""
            for i, c in enumerate(cases):
                img = IMG_BOOKS if i % 2 == 0 else IMG_SCALES
                cards += f"""
                <div class="bg-white rounded-xl overflow-hidden shadow-sm hover:shadow-lg transition-all border border-outline-variant/10 group">
                    <div class="aspect-[4/3] relative overflow-hidden">
                        <img src="{img}" class="w-full h-full object-cover group-hover:scale-105 transition-transform duration-500"/>
                        <div class="absolute inset-0 bg-gradient-to-t from-[#191c1e] to-transparent opacity-0 group-hover:opacity-80 transition-opacity p-6 flex flex-col justify-end">
                            <span class="text-white text-sm font-bold tracking-widest uppercase">Open Document -></span>
                        </div>
                    </div>
                    <div class="p-6">
                        <span class="text-[10px] font-bold tracking-widest uppercase bg-surface-container text-on-surface-variant px-2 py-1 rounded">{c.get('case_category', 'Law')}</span>
                        <h4 class="font-bold text-lg leading-tight mt-3 mb-2 block text-on-surface">{c.get('title','Untitled')}</h4>
                        <p class="text-sm text-on-surface-variant line-clamp-2 leading-relaxed">Ratio Decidendi: {(c.get('ratio_decidendi') or c.get('summary') or 'Not Extracted')[:150]}</p>
                        <div class="mt-4 pt-4 border-t border-outline-variant/10 flex justify-between items-center text-xs font-bold text-primary">
                            <span>{c.get('predicted_outcome', 'Unknown')}</span>
                            <span>{c.get('outcome_confidence', 0):.1f}%</span>
                        </div>
                    </div>
                </div>
                """
            st.markdown(f'<div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-8">{cards}</div>', unsafe_allow_html=True)
    except:
        st.error("Could not fetch vault data.")
    st.markdown("</div>", unsafe_allow_html=True)

def render_solver():
    st.markdown("""
    <div style="padding: 80px 0 0 80px; height: 100vh; overflow: hidden; position: relative; z-index: 1;" class="flex w-full">
        <!-- Left Panel -->
        <div class="w-1/3 bg-surface-container-low p-10 overflow-y-auto border-r border-[#eceef0] shadow-[inset_-10px_0_20px_rgba(0,0,0,0.01)] h-full">
            <h2 class="text-2xl font-bold mb-2">Relevant Cases</h2>
            <p class="text-xs font-bold text-on-surface-variant uppercase tracking-widest mb-8">AI-Curated Intelligence</p>
    """, unsafe_allow_html=True)
    try:
        cases = supabase.table("cases_vault").select("*").limit(3).execute().data
        for c in cases:
            st.markdown(f"""
            <div class="bg-white p-6 rounded-xl border-l-4 border-primary shadow-sm mb-4 hover:shadow-md transition-shadow">
                <span class="text-[10px] bg-secondary-container text-on-secondary-container rounded px-2 py-1 font-bold uppercase tracking-widest">Matched Concept</span>
                <h3 class="font-bold text-md mt-3 mb-2 leading-tight">{c.get('title')}</h3>
                <p class="text-xs text-on-surface-variant leading-relaxed line-clamp-3">{c.get('summary','')}</p>
            </div>
            """, unsafe_allow_html=True)
    except: pass
    st.markdown("""
        </div>
        <!-- Right Chat Area -->
        <div class="w-2/3 flex flex-col bg-white h-full relative">
            <div class="h-20 px-10 flex items-center justify-between border-b border-outline-variant/10 shrink-0 bg-white/80 backdrop-blur-md">
                <div class="flex items-center">
                    <span class="material-symbols-outlined text-white bg-primary p-2 flex items-center justify-center rounded-lg mr-4" style="font-variation-settings: 'FILL' 1;">auto_awesome</span>
                    <div>
                        <h2 class="font-bold text-lg leading-tight">Legal Intelligence Assistant</h2>
                        <p class="text-[10px] uppercase font-bold tracking-widest text-[#00685f] flex items-center gap-1 mt-1"><span class="w-1.5 h-1.5 rounded-full bg-[#00685f]"></span> Active Session</p>
                    </div>
                </div>
            </div>
            <div class="p-10 space-y-8 overflow-y-auto flex-1 pb-32">
    """, unsafe_allow_html=True)
    
    for msg in st.session_state.chat_history:
        if msg["role"] == "user":
            st.markdown(f"""
            <div class="flex items-start justify-end">
                <div class="bg-primary text-white px-6 py-5 rounded-tl-3xl rounded-bl-3xl rounded-br-3xl max-w-xl text-[15px] shadow-lg leading-relaxed">{msg["content"]}</div>
                <img src="{IMG_AVATAR}" class="w-8 h-8 rounded-full ml-4 object-cover mt-1"/>
            </div>
            """, unsafe_allow_html=True)
        else:
            st.markdown(f"""
            <div class="flex items-start">
                <div class="bg-[#e6e8ea] w-8 h-8 rounded-full flex items-center justify-center mr-4 mt-1"><span class="material-symbols-outlined text-[#3d4947] text-sm" style="font-variation-settings: 'FILL' 1;">robot</span></div>
                <div class="bg-[#f2f4f6] text-on-surface px-6 py-5 rounded-tr-3xl rounded-br-3xl rounded-bl-3xl max-w-2xl text-[15px] leading-relaxed">{msg["content"]}</div>
            </div>
            """, unsafe_allow_html=True)
            
    st.markdown("""
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)
    
    # st.chat_input rendered in the bottom right, constrained within the column
    col_empty, col_chat = st.columns([4, 8])
    with col_chat:
        prompt = st.chat_input("Ask a follow-up about legislation or cases...")
        if prompt:
            st.session_state.chat_history.append({"role": "user", "content": prompt})
            st.session_state.chat_history.append({"role": "assistant", "content": "I am looking into IPC and BNS mappings for your query. (Retrieval engine active...)"})
            st.rerun()

def render_history():
    st.markdown("""<div style="padding: 120px 40px 60px 100px; max-width: 1400px; margin: 0 auto; position: relative; z-index: 1;">""", unsafe_allow_html=True)
    st.markdown("<h2 class='text-4xl font-extrabold tracking-tight mb-2'>Case History</h2><p class='text-lg text-on-surface-variant mb-12'>Log of your previous AI prediction operations.</p>", unsafe_allow_html=True)
    hist = get_history()
    if hist:
        rows = ""
        for r in hist:
            rows += f"""<tr class="hover:bg-surface-container-low transition-colors border-b border-outline-variant/10">
                <td class="py-6 px-6 font-bold">{r['filename']}</td>
                <td class="py-6 px-6"><span class="bg-primary/10 text-primary px-3 py-1 rounded-full font-bold text-[10px] uppercase tracking-widest">{r['predicted_outcome']} ({r['outcome_confidence']:.1f}%)</span></td>
                <td class="py-6 px-6 text-sm font-semibold">{r['predicted_jurisdiction']}</td>
                <td class="py-6 px-6 text-sm text-on-surface-variant text-right font-medium tracking-widest">{r['created_at'][:10]}</td>
            </tr>"""
        st.markdown(f"""
            <div class="bg-white rounded-xl shadow-sm border border-outline-variant/10 overflow-hidden">
                <table class="w-full text-left">
                <thead class="bg-surface-container-low border-b border-outline-variant/10">
                    <tr><th class="py-4 px-6 text-[10px] font-bold text-on-surface-variant uppercase tracking-widest">Case Reference</th><th class="py-4 px-6 text-[10px] font-bold text-on-surface-variant uppercase tracking-widest">AI Prediction</th><th class="py-4 px-6 text-[10px] font-bold text-on-surface-variant uppercase tracking-widest">Jurisdiction</th><th class="py-4 px-6 text-right text-[10px] font-bold text-on-surface-variant uppercase tracking-widest">Date</th></tr>
                </thead>
                <tbody>{rows}</tbody></table>
            </div>
        """, unsafe_allow_html=True)
    else:
        st.info("No Case History yet.")
    st.markdown("</div>", unsafe_allow_html=True)

# --- ROUTER ---
if not st.session_state.get('authenticated', False):
    render_auth()
else:
    nav = st.query_params.get("nav", "predictor")
    render_shell(nav)
    if nav == "predictor": render_predictor()
    elif nav == "vault": render_vault()
    elif nav == "solver": render_solver()
    elif nav == "history": render_history()
    else: render_predictor()
'''

with open('app.py', 'w', encoding='utf-8') as f:
    f.write(get_app_code())

print("app.py successfully overwritten with Lucid Architect UI!")
