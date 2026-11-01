"""Legal AI Hub - study assistant chatbot (offline, free).

Answers law-student questions from the project's own knowledge base:

* knowledge/statutes.json  - official BNS 2023 <-> IPC 1860 correspondence table (543 rows)
* knowledge/concepts.json  - glossary of legal concepts with old/new provisions and sources
* eval_harness/benchmark_cohort.csv + "Model Test pdfs/" - past judgments with real verdicts
* knowledge/extra_cases.csv (optional) - more judgments: columns name,text,verdict[,category,court,year]

How it works (retrieval, no paid API):
  1. route the question: greeting / help / unsafe / out_of_scope / statute / concept / case_search / unclear
  2. search the matching knowledge with TF-IDF (scikit-learn)
  3. compose a cited markdown answer; past cases come with their verdict and the court's final order

Optionally, set an OpenAI-compatible endpoint (free local Ollama, or a free-tier API key) and the
retrieved material is rewritten into a more conversational answer. Without it everything still works.

This module has no Streamlit dependency so it can be tested and evaluated directly.
"""
from __future__ import annotations

import importlib.util
import json
import logging
import os
import re
import time
from collections import Counter
from dataclasses import asdict, dataclass, field

import numpy as np
import scipy.sparse as sp
import sklearn
from sklearn.feature_extraction.text import ENGLISH_STOP_WORDS, TfidfVectorizer
from sklearn.metrics.pairwise import linear_kernel

logger = logging.getLogger(__name__)

HERE = os.path.dirname(os.path.abspath(__file__))
STATUTES_PATH = os.path.join(HERE, "knowledge", "statutes.json")
CONCEPTS_PATH = os.path.join(HERE, "knowledge", "concepts.json")
LEGACY_MAP_PATH = os.path.join(HERE, "bns_mapping.json")
COHORT_PATH = os.path.join(HERE, "eval_harness", "benchmark_cohort.csv")
EXTRA_CASES_PATH = os.path.join(HERE, "knowledge", "extra_cases.csv")
TEST_PDF_DIR = os.path.join(HERE, "Model Test pdfs")
# Fitted search indexes are saved here so the app does not rebuild them on every start.
CACHE_PATH = os.path.join(HERE, "knowledge", ".index_cache.joblib")
CACHE_VERSION = 1   # bump whenever the index format / chunking / scoring inputs change

DISCLAIMER = "_Study aid only, not legal advice. Always read the full judgment or bare act._"

# The four extra judgments in "Model Test pdfs/" (same metadata as eval_harness/run_eval.py)
TEST_JUDGMENTS = [
    ("10718_2011_7_1502_53219_Judgement_15-May-2024.pdf", "Rajendra v. State of Maharashtra",
     "Supreme Court of India", 2024, "Criminal Law", "dismissed"),
    ("47292_2018_5_1501_57671_Judgement_02-Dec-2024.pdf", "Ashok v. State of UP",
     "Supreme Court of India", 2024, "Criminal Law", "allowed"),
    ("Sh_Jilubhai_Nanbhai_Khachar_Etc_Etc_vs_State_Of_Gujarat_And_Anr_Etc_Etc_on_20_July_1994.PDF",
     "Jilubhai Nanbhai Khachar v. State of Gujarat", "Supreme Court of India", 1994, "Constitutional Law", "dismissed"),
    ("ordjud.pdf", "Shyamsundar Agarwal v. State of Maharashtra", "Bombay High Court", 2025, "Criminal Law", "allowed"),
]

VERDICT_TEXT = {
    "allowed": "Allowed (the appeal/petition succeeded)",
    "dismissed": "Dismissed (the appeal/petition failed)",
    "partly_allowed": "Partly allowed",
}

# ── Intent vocabularies ──────────────────────────────────────────────────
GREETING_RE = re.compile(
    r"^\s*(hi+|hello+|hey+|hii+|helo|namaste|namaskar|good\s+(morning|afternoon|evening|night)|greetings|yo|hola)\b[\s,!.]*",
    re.I)
NAME_RE = re.compile(r"\b(?:my\s+name\s+is|my\s+name's|this\s+is|i\s+am\s+called)\s+([A-Za-z][A-Za-z]{1,20})", re.I)
THANKS_RE = re.compile(r"^\s*(thanks?|thank\s+you|thx|ty|great|nice|cool|awesome|got it)\b[\s!.]*$", re.I)
HELP_RE = re.compile(
    r"\b(what\s+can\s+you\s+do|how\s+(do|can)\s+i\s+use|how\s+to\s+use|what\s+can\s+i\s+ask|help\s+me\s+use|"
    r"what\s+do\s+you\s+do|who\s+are\s+you|what\s+are\s+you)\b|^\s*help\s*[?!.]*$", re.I)

UNSAFE_RE = re.compile(
    r"\b(destroy|tamper(\s+with)?|hide|get\s+rid\s+of|fabricate|plant|forge|fake|delete|erase|burn)\b.{0,30}\b"
    r"(evidence|proof|records?|documents?|fir|complaint|cctv|footage|witness|body|weapon)\b"
    r"|\b(escape|evade|avoid|dodge|beat|get\s+away\s+(with|from)|get\s+out\s+of)\b.{0,40}\b"
    r"(charges?|arrest|police|conviction|case|trial|punishment|murder|crime|caught)\b"
    r"|\bwithout\s+(getting\s+)?(caught|arrested|detected|trace)\b"
    r"|\b(hide|conceal|stash|transfer)\b.{0,30}\b(money|cash|assets|property|gold)\b.{0,30}\b(police|court|investigat\w*|ed|cbi|attach\w*|seiz\w*)"
    r"|\bhide\b.{0,30}\bfrom\s+(the\s+)?(police|court|investigat\w*)"
    r"|\b(bribe|pay\s+off|influence|threaten|intimidate|silence)\b.{0,25}\b(judge|police|officer|witness|magistrate|investigator)\b"
    r"|\b(make|file|lodge|register|create)\s+(a\s+)?(fake|false|fabricated)\s+(fir|case|complaint|evidence|charge)"
    r"|\bhow\s+(to|do\s+i|can\s+i)\s+(kill|murder|poison|rob|steal|kidnap|launder)\b",
    re.I)

OFF_TOPIC_RE = re.compile(
    r"\b(weather|temperature|rain|recipe|cook|cooking|cricket|ipl|football|match\s+score|score|movie|film|song|lyrics|"
    r"poem|poetry|joke|story|game|gaming|stock|share\s+price|bitcoin|crypto|python\s+code|javascript|programming|"
    r"girlfriend|boyfriend|horoscope|astrology|travel|hotel|restaurant|pizza|paneer|biryani|news\s+today|celebrity|"
    r"solve|equation|calculate|math|maths|moon|sun|planet)\b"
    r"|\d\s*[a-z]?\s*[+\-*/^=]\s*\d",
    re.I)

LEGAL_WORDS = set("""
law laws legal court courts judge judges judgment judgement verdict appeal appellant respondent petition petitioner
writ article constitution constitutional section sections act acts code ipc bns bnss crpc bsa evidence bail fir
police arrest accused crime crimes criminal offence offense offences punishment sentence convict conviction acquittal
murder theft cheating rape dowry custody remand trial witness rights precedent case cases tribunal tax property
contract civil suit decree tort lawyer advocate prosecution prosecutor investigation charge chargesheet magistrate
sessions supreme high cognizable bailable quash quashing compensation divorce maintenance land acquisition sedition
""".split())

CASE_HINT_RE = re.compile(
    r"\b(case|cases|precedent|precedents|judgment|judgments|judgement|ruling|rulings|decided|held|past|earlier|"
    r"similar|example|facts|where|wherein|court\s+(said|held|ruled))\b", re.I)
CONCEPT_HINT_RE = re.compile(
    r"\b(what\s+is|what\s+are|what's|define|definition|meaning|means|explain|difference|differentiate|vs\.?|versus|"
    r"tell\s+me\s+about|information\s+about|infomation|info\s+about|learn|concept|understand|kya\s+hai)\b", re.I)
STATUTE_HINT_RE = re.compile(r"\b(ipc|bns|section|sec|s\.|sections|i\.p\.c|penal\s+code|nyaya\s+sanhita)\b", re.I)

SECTION_NUM_RE = re.compile(r"(?<![\w.])(\d{1,3}[A-Za-z]{0,2}(?:\s?\(\d{1,2}\))?)(?![\w])")

CASE_STOP_WORDS = list(ENGLISH_STOP_WORDS | {
    "court", "courts", "appellant", "appellants", "respondent", "respondents", "learned", "counsel", "hon", "ble",
    "honble", "para", "paras", "vs", "versus", "judgment", "judgement", "order", "case", "cases", "said", "also",
    "would", "shall", "may", "upon", "thereof", "therein", "whereas", "hereby", "dated", "mr", "dr", "sri", "shri",
    "smt", "ms", "mrs", "past", "precedent", "precedents", "similar", "show", "find", "tell", "ruling", "decided",
    "held", "example", "examples", "want", "know", "give", "please", "earlier", "previous", "previously", "happened",
})


@dataclass
class Case:
    id: str
    name: str
    court: str
    year: int | None
    category: str
    verdict: str          # allowed | dismissed | partly_allowed
    text: str
    final_order: str = ""
    source: str = ""


@dataclass
class Result:
    intent: str
    text: str
    cases: list = field(default_factory=list)       # [{name, court, year, verdict, category, passage, final_order}]
    sources: list = field(default_factory=list)     # short strings shown under the answer
    context: dict = field(default_factory=dict)     # carried into the next turn (follow-ups)

    def as_dict(self):
        return {"intent": self.intent, "text": self.text, "cases": self.cases,
                "sources": self.sources, "context": self.context}


# ── Helpers ───────────────────────────────────────────────────────────────
def _norm(s):
    s = (s or "").lower().replace(".", "")
    s = re.sub(r"[^a-z0-9()\s]", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def _norm_section(s):
    """'318 (4)' / '318(4)' / '498a' -> '318(4)' / '498A'"""
    s = re.sub(r"\s+", "", s or "")
    m = re.match(r"(\d+)([A-Za-z]*)(.*)", s)
    return (m.group(1) + m.group(2).upper() + m.group(3)) if m else s


def _clean_ws(s):
    return re.sub(r"\s+", " ", s or "").strip()


def _strip_boilerplate(text):
    text = re.sub(r"Indian Kanoon\s*-\s*http\S+\s*\d*", " ", text or "")
    return re.sub(r"Signature Not Verified.*?(?=\n|$)", " ", text)


def _case_name_from_id(case_id):
    base = re.sub(r"\.(pdf|PDF)$", "", case_id)
    base = re.sub(r"_\d+$", "", base)
    m = re.search(r"_on_(\d{1,2})_([A-Za-z]+)_(\d{4})$", base)
    year = int(m.group(3)) if m else None
    name = base[:m.start()] if m else base
    name = name.replace("_", " ").strip()
    return name, year


def _final_order(text):
    """The court's concluding words: last 'In the result / accordingly / appeal is allowed...' passage."""
    t = _clean_ws(text)
    if not t:
        return ""
    tail_start = int(len(t) * 0.6)
    pat = re.compile(r"(in the result|in view of the (above|foregoing)|for the (foregoing |above )?reasons|"
                     r"accordingly|(appeals?|petitions?|writ petitions?) (is|are|stands?) (hereby )?"
                     r"(allowed|dismissed|disposed)|we (therefore )?(allow|dismiss|set aside|uphold))", re.I)
    hits = [m.start() for m in pat.finditer(t) if m.start() >= tail_start]
    start = hits[-1] if hits else max(0, len(t) - 600)
    snippet = t[start:start + 650]
    if start > 0:
        snippet = "…" + snippet
    if start + 650 < len(t):
        snippet = snippet.rsplit(" ", 1)[0] + "…"
    return snippet


_MONTHS = "January|February|March|April|May|June|July|August|September|October|November|December"
_DATE = rf"(\d{{1,2}})(?:st|nd|rd|th)?\s+(?:{_MONTHS}),?\s+((?:19|20)\d\d)"
_DATE_ANY = rf"(?:{_DATE}|(?:{_MONTHS})\s+\d{{1,2}},?\s+((?:19|20)\d\d)|\d{{1,2}}[/.-]\d{{1,2}}[/.-]((?:19|20)\d\d))"
# Indian Kanoon page header repeated through the text: "X vs Y on 12 February, 1980"
YEAR_HEADER_RE = re.compile(rf"\b(?:vs?\.?|versus)\s.{{0,250}}?\son\s+{_DATE}", re.I | re.S)
YEAR_EXPLICIT_RE = re.compile(
    rf"(?:date\s+of\s+(?:the\s+)?(?:judg?e?ment|decision|order)|decided\s+on|judgment\s+(?:delivered|pronounced)\s+on)"
    rf"\s*[:\-]?\s*{_DATE_ANY}", re.I)
YEAR_ON_DATE_RE = re.compile(rf"\bon\s+{_DATE}", re.I)
YEAR_CITE_RE = re.compile(r"\bAIR\s+((?:19|20)\d\d)\s+(?:SC|Supreme)\b|[(\[]((?:19|20)\d\d)[)\]]\s*\d*\s*(?:SCC|SCR|S\.C\.R)"
                          r"|\b((?:19|20)\d\d)\s+(?:\(\d+\)\s+)?(?:SCR|SCC|S\.C\.R)\b", re.I)


def _plausible_year(y):
    return y is not None and 1950 <= int(y) <= 2026


def _year_from_text(text, head=3000):
    """Best guess of the decision year of a judgment whose name carries no date (None if nothing plausible).

    1. the "X vs Y on 12 February, 1980" header (most frequent year; ~99% right on the benchmark cohort)
    2. "Date of Judgment: ..." / "decided on ..." in the first `head` characters
    3. the latest "on 12 February, 1980" date in the first `head` characters
    4. the latest law-report citation there ("AIR 1978 SC", "(1990) 1 SCC", "1975 SCR") - a judgment
       only cites earlier ones, so the latest is the closest lower bound
    Years outside 1950-2026 are ignored."""
    if not text:
        return None
    t = re.sub(r"\s+", " ", text)
    ys = [int(m.group(2)) for m in YEAR_HEADER_RE.finditer(t) if _plausible_year(m.group(2))]
    if ys:
        return Counter(ys).most_common(1)[0][0]
    h = t[:head]
    for m in YEAR_EXPLICIT_RE.finditer(h):
        y = next(g for g in (m.group(2), m.group(3), m.group(4)) if g)
        if _plausible_year(y):
            return int(y)
    ys = [int(m.group(2)) for m in YEAR_ON_DATE_RE.finditer(h) if _plausible_year(m.group(2))]
    if ys:
        return max(ys)
    cites = [int(g) for m in YEAR_CITE_RE.finditer(h) for g in m.groups() if g and _plausible_year(g)]
    return max(cites) if cites else None


def _chunks(text, size=900, overlap=150):
    """Overlapping chunks of ~`size` chars that start and end on word boundaries."""
    t = _clean_ws(text)
    if len(t) <= size:
        return [t] if t else []
    out, i, n = [], 0, len(t)
    while i < n:
        end = min(i + size, n)
        if end < n:
            sp_ = t.rfind(" ", i + size // 2, end + 1)
            if sp_ > i:
                end = sp_
        piece = t[i:end].strip()
        if piece:
            out.append(piece)
        if end >= n:
            break
        nxt = max(end - overlap, i + 1)
        if t[nxt - 1] != " ":                      # move to the start of the next word
            sp_ = t.find(" ", nxt, end)
            nxt = sp_ + 1 if sp_ != -1 else end + 1
        i = nxt
    return out


def _best_window(passage, query_terms, width=380, lead=60, continued=False):
    """Trim a passage to the ~`width`-char window that contains the most distinct query terms.

    The window starts and ends on word boundaries (preferring a sentence start just before the first hit).
    `continued`: the passage is itself taken from the middle of a longer text (adds a leading "…")."""
    passage = _clean_ws(passage)
    if len(passage) <= width:
        return ("…" if continued and passage else "") + passage
    low = passage.lower()
    occ = sorted((m.start(), t) for t in {w.lower() for w in query_terms if len(w) >= 3}
                 for m in re.finditer(r"\b" + re.escape(t), low))
    start = 0
    if occ:
        best, anchor = -1, 0
        for j, (p, _) in enumerate(occ):
            inside = {t for q, t in occ[j:] if q + len(t) <= p + width - lead}
            if len(inside) > best:
                best, anchor = len(inside), p
        start = max(0, anchor - lead)
        if start > 0:
            dot = passage.rfind(". ", start, anchor)
            if dot != -1:
                start = dot + 2
            elif passage[start - 1] != " ":
                sp_ = passage.find(" ", start, anchor)
                start = sp_ + 1 if sp_ != -1 else anchor
    end = min(len(passage), start + width)
    if end < len(passage):
        sp_ = passage.rfind(" ", start + width // 2, end + 1)
        if sp_ != -1:
            end = sp_
    s = passage[start:end].strip().lstrip(",;:)]").strip()
    return ("…" if start > 0 or continued else "") + s + ("…" if end < len(passage) else "")


# ── Knowledge loading ────────────────────────────────────────────────────
def load_cases(include_pdfs=True, extra_csv=EXTRA_CASES_PATH, max_chars=60_000):
    cases = []
    try:
        import pandas as pd
        if os.path.isfile(COHORT_PATH):
            df = pd.read_csv(COHORT_PATH)
            for _, r in df.iterrows():
                name, year = _case_name_from_id(str(r["case_id"]))
                text = str(r.get("cleaned_text") or "")[:max_chars]
                cases.append(Case(id=str(r["case_id"]), name=name, court="Supreme Court of India", year=year,
                                  category=str(r.get("true_case_category") or ""),
                                  verdict=str(r.get("raw_label") or "").strip().lower(),
                                  text=text, source="benchmark_cohort.csv"))
        if extra_csv and os.path.isfile(extra_csv):
            df = pd.read_csv(extra_csv)
            for i, r in df.iterrows():
                text = str(r.get("text") or "")[:max_chars]
                if not text.strip():
                    continue
                verdict = str(r.get("verdict") or "").strip().lower().replace(" ", "_")
                try:   # pandas reads a year column with blanks as floats (1980.0 / nan)
                    year = int(float(r.get("year")))
                except (TypeError, ValueError):
                    year = None
                cases.append(Case(id=f"extra_{i}", name=str(r.get("name") or f"Case {i}"),
                                  court=str(r.get("court") or ""), year=year if _plausible_year(year) else None,
                                  category=str(r.get("category") or ""), verdict=verdict, text=text,
                                  source="extra_cases.csv"))
    except Exception as e:
        logger.warning(f"Could not load case CSVs: {e}")

    if include_pdfs and os.path.isdir(TEST_PDF_DIR):
        try:
            import pymupdf
            for fname, name, court, year, cat, verdict in TEST_JUDGMENTS:
                path = os.path.join(TEST_PDF_DIR, fname)
                if os.path.isfile(path):
                    doc = pymupdf.open(path)
                    text = "\n".join(p.get_text() for p in doc)[:max_chars]
                    cases.append(Case(id=fname, name=name, court=court, year=year, category=cat,
                                      verdict=verdict, text=text, source="Model Test pdfs"))
        except Exception as e:
            logger.warning(f"Could not read test judgment PDFs: {e}")

    for c in cases:
        c.text = _strip_boilerplate(c.text)
        c.final_order = _final_order(c.text)
        if c.year is None:
            c.year = _year_from_text(c.text)
    return cases


def _input_fingerprint():
    """Everything the cached index depends on: input files (path, size, mtime) + code/library versions."""
    files = [STATUTES_PATH, CONCEPTS_PATH, LEGACY_MAP_PATH, COHORT_PATH, EXTRA_CASES_PATH]
    files += [os.path.join(TEST_PDF_DIR, j[0]) for j in TEST_JUDGMENTS]
    fp = [("cache_version", CACHE_VERSION), ("sklearn", sklearn.__version__),
          ("pymupdf", importlib.util.find_spec("pymupdf") is not None)]
    for f in files:
        try:
            st = os.stat(f)
            fp.append((os.path.relpath(f, HERE), st.st_size, st.st_mtime_ns))
        except OSError:
            fp.append((os.path.relpath(f, HERE), None, None))
    return tuple(fp)


def build_index_cache(path=CACHE_PATH):
    """(Re)build the search index from the knowledge files and save it to `path`. Returns the assistant."""
    return LegalAssistant(cache_path=path, rebuild=True)


def _load_json(path, default):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        logger.warning(f"Could not load {path}: {e}")
        return default


# ── The assistant ────────────────────────────────────────────────────────
class LegalAssistant:
    # fitted state saved in / restored from the index cache (besides statutes, concepts, legacy_map, cases)
    _CACHED = ("stat_vec", "stat_mat", "con_vec", "con_mat", "con_word_vec", "con_word_mat",
               "chunk_text", "chunk_case", "case_vec", "case_mat", "case_norm")

    def __init__(self, statutes=None, concepts=None, cases=None, legacy_map=None, llm=None,
                 use_cache=True, cache_path=None, rebuild=False):
        """Knowledge passed explicitly (as the tests do) is indexed fresh and never cached.
        Otherwise the fitted indexes are loaded from `cache_path` (default knowledge/.index_cache.joblib)
        when the input files are unchanged, and rebuilt + saved when they changed or the cache is unreadable."""
        self.llm = llm  # optional dict: {"base_url", "api_key", "model"}
        self.cache_path = cache_path or CACHE_PATH
        self.cache_status = "off"
        explicit = any(x is not None for x in (statutes, concepts, cases, legacy_map))
        cacheable = use_cache and not explicit
        if not (cacheable and not rebuild and self._load_cache(self.cache_path)):
            self.statutes = statutes if statutes is not None else _load_json(STATUTES_PATH, [])
            self.concepts = concepts if concepts is not None else _load_json(CONCEPTS_PATH, [])
            self.legacy_map = legacy_map if legacy_map is not None else _load_json(LEGACY_MAP_PATH, {})
            self.cases = cases if cases is not None else load_cases()
            self._fit_statutes()
            self._fit_concepts()
            self._fit_cases()
            if cacheable:
                self._save_cache(self.cache_path)
        self._lookups()

    # ── index cache ──
    def _load_cache(self, path):
        if not os.path.isfile(path):
            self.cache_status = "missing"
            return False
        try:
            import joblib
            t0 = time.time()
            data = joblib.load(path)
            if not isinstance(data, dict) or data.get("fingerprint") != _input_fingerprint():
                self.cache_status = "stale"
                return False
            self.statutes, self.concepts, self.legacy_map = data["statutes"], data["concepts"], data["legacy_map"]
            self.cases = [Case(**c) for c in data["cases"]]
            for k in self._CACHED:
                setattr(self, k, data[k])
            self.cache_status = "loaded"
            logger.info(f"Loaded search index cache ({len(self.cases)} cases) in {time.time() - t0:.1f}s")
            return True
        except Exception as e:   # corrupt / truncated / incompatible pickle -> rebuild
            logger.warning(f"Ignoring unreadable index cache {path}: {e}")
            self.cache_status = "corrupt"
            return False

    def _save_cache(self, path):
        try:
            import joblib
            data = {"fingerprint": _input_fingerprint(), "statutes": self.statutes, "concepts": self.concepts,
                    "legacy_map": self.legacy_map, "cases": [asdict(c) for c in self.cases]}
            data.update({k: getattr(self, k) for k in self._CACHED})
            os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
            tmp = f"{path}.{os.getpid()}.tmp"
            joblib.dump(data, tmp)
            os.replace(tmp, path)   # atomic: a crash mid-write never leaves a half-written cache
            self.cache_status = "saved"
        except Exception as e:
            logger.warning(f"Could not save index cache {path}: {e}")
            try:
                os.remove(tmp)
            except Exception:
                pass

    # ── indexes ──
    def _lookups(self):
        """Cheap derived structures, rebuilt on every start (from fresh or cached data)."""
        self.by_ipc, self.by_bns = {}, {}
        for row in self.statutes:
            if row.get("ipc"):
                self.by_ipc.setdefault(_norm_section(row["ipc"]), []).append(row)
            if row.get("bns"):
                self.by_bns.setdefault(_norm_section(row["bns"]), []).append(row)
        self.alias_index = []  # (normalized alias, concept)
        for c in self.concepts:
            for a in set([c.get("term", "")] + list(c.get("aliases", []))):
                na = _norm(re.sub(r"\(.*?\)", "", a))
                if na:
                    self.alias_index.append((na, c))
        self.alias_index.sort(key=lambda x: -len(x[0]))   # longest (most specific) aliases first
        self.vocab = set(self.case_vec.vocabulary_) | set(self.con_word_vec.vocabulary_) | set(self.stat_vec.vocabulary_)
        self._case_analyzer = self.case_vec.build_analyzer()
        counts = np.bincount(self.chunk_case, minlength=len(self.cases)) if len(self.chunk_case) else \
            np.zeros(len(self.cases), dtype=int)
        self.case_chunk_start = np.concatenate([[0], np.cumsum(counts)[:-1]]).astype(int) if len(counts) else counts
        self.case_chunk_count = counts

    @staticmethod
    def _slim(vec):
        """Drop the (potentially huge) set of pruned terms; sklearn keeps it only for introspection."""
        if hasattr(vec, "stop_words_"):
            try:
                delattr(vec, "stop_words_")
            except Exception:
                pass
        # numpy-int values unpickle ~10x slower than plain ints (matters for a 200k-term vocabulary)
        if hasattr(vec, "vocabulary_"):
            vec.vocabulary_ = {k: int(v) for k, v in vec.vocabulary_.items()}
        return vec

    def _fit_statutes(self):
        docs = [f"{r.get('bns_title', '')} {r.get('ipc_title', '')}" for r in self.statutes] or ["placeholder"]
        self.stat_vec = TfidfVectorizer(stop_words="english", ngram_range=(1, 2), sublinear_tf=True)
        self.stat_mat = self.stat_vec.fit_transform(docs)
        self._slim(self.stat_vec)

    def _fit_concepts(self):
        docs = [" ".join([c.get("term", "")] + c.get("aliases", [])) for c in self.concepts] or ["placeholder"]
        # character n-grams make the fallback tolerant of typos ("bial", "anticipatry")
        self.con_vec = TfidfVectorizer(analyzer="char_wb", ngram_range=(3, 5), sublinear_tf=True)
        self.con_mat = self.con_vec.fit_transform(docs)
        body = [" ".join([c.get("term", ""), " ".join(c.get("aliases", [])), c.get("answer", "")]) for c in self.concepts] or ["placeholder"]
        self.con_word_vec = TfidfVectorizer(stop_words="english", sublinear_tf=True)
        self.con_word_mat = self.con_word_vec.fit_transform(body)
        self._slim(self.con_vec)
        self._slim(self.con_word_vec)

    @staticmethod
    def _chunk_head(c):
        return f"{c.name}. {c.category}. "

    def _fit_cases(self):
        chunk_case, chunk_text = [], []
        for ci, c in enumerate(self.cases):
            head = self._chunk_head(c)
            for ch in _chunks(c.text):
                chunk_case.append(ci)
                chunk_text.append(head + ch)
        self.chunk_text = chunk_text
        self.chunk_case = np.array(chunk_case, dtype=np.int32)
        self.case_vec = TfidfVectorizer(stop_words=CASE_STOP_WORDS, ngram_range=(1, 2), sublinear_tf=True,
                                        min_df=1, max_df=0.6 if len(chunk_text) > 4 else 1.0,
                                        max_features=200_000, dtype=np.float32)
        self.case_mat = self.case_vec.fit_transform(chunk_text or ["placeholder"]).tocsr()
        self._slim(self.case_vec)
        # Norm of each case's summed chunk vectors, so that  sum_i(q·chunk_i) / norm  is the cosine between the
        # query and the whole case. Computed in blocks of cases to keep peak RAM low.
        n = len(self.cases)
        self.case_norm = np.zeros(n, dtype=np.float32)
        if len(self.chunk_case) and self.case_mat.shape[0] == len(self.chunk_case):
            bounds = np.searchsorted(self.chunk_case, np.arange(n + 1))
            for b in range(0, n, 256):
                e = min(n, b + 256)
                r0, r1 = bounds[b], bounds[e]
                if r1 == r0:
                    continue
                rows = self.chunk_case[r0:r1] - b
                ind = sp.csr_matrix((np.ones(r1 - r0, dtype=np.float32), (rows, np.arange(r1 - r0))),
                                    shape=(e - b, r1 - r0))
                agg = ind @ self.case_mat[r0:r1]
                self.case_norm[b:e] = np.sqrt(np.asarray(agg.multiply(agg).sum(axis=1)).ravel())

    # ── public API ──
    def answer(self, question, history=None):
        """history: list of previous result dicts (as returned by this method), oldest first."""
        q = (question or "").strip()
        prev = (history or [])[-1].get("context", {}) if history else {}
        res = self._route(q, prev)
        if self.llm and res.intent in ("statute", "concept", "case_search"):
            res = self._polish_with_llm(q, res)
        return res.as_dict()

    # ── routing ──
    def _route(self, q, prev):
        if not re.search(r"[A-Za-z0-9]", q):
            return self._unclear(q)

        greeting_prefix, name = "", None
        m = NAME_RE.search(q)
        if m:
            name = m.group(1).capitalize()
        g = GREETING_RE.match(q)
        rest = q[g.end():] if g else q
        rest = NAME_RE.sub("", rest)
        rest = re.sub(r"^[\s,.!&]*(and\s+)?(i\s+)?", "", rest, flags=re.I).strip()
        if g or name:
            greeting_prefix = f"Hi {name}! " if name else "Hi! "
        if (g or name) and len(re.findall(r"[a-z]{3,}", rest.lower())) < 2:
            return self._greeting(name)
        q_main = rest if (g or name) else q

        if THANKS_RE.match(q_main):
            return Result("greeting", "You're welcome! Ask me about any IPC/BNS section, a legal concept, "
                                      "or describe facts to find similar past cases.")
        if UNSAFE_RE.search(q_main):
            return self._unsafe()
        if HELP_RE.search(q_main):
            return self._help()

        if OFF_TOPIC_RE.search(q_main) and not self._has_legal_signal(q_main):
            return self._out_of_scope()
        res = self._legal(q_main, prev)
        if res is None:
            if self._has_legal_signal(q_main):
                res = self._no_match(q_main)
            elif self._looks_like_words(q_main):
                res = self._out_of_scope()
            else:
                res = self._unclear(q_main)
        if greeting_prefix and res.intent not in ("greeting",):
            res.text = greeting_prefix + res.text
        return res

    def _looks_like_words(self, q):
        """At least 3 real words that appear in the knowledge base vocabulary (vs. gibberish like 'sdkjfh')."""
        words = re.findall(r"[a-z]{2,}", q.lower())
        known = [w for w in words if w in self.vocab or w in ENGLISH_STOP_WORDS]
        return len(words) >= 3 and len(known) >= 0.6 * len(words)

    def _has_legal_signal(self, q):
        words = set(re.findall(r"[a-z]+", q.lower()))
        return bool(words & LEGAL_WORDS) or bool(SECTION_NUM_RE.search(q) and STATUTE_HINT_RE.search(q))

    def _legal(self, q, prev):
        nq = _norm(q)
        # 1. follow-up about a case shown in the previous answer
        if prev.get("cases") and re.search(r"\b(first|second|third|1st|2nd|3rd|that|this|the)\s+(case|one|judgment)\b|"
                                           r"\bmore\s+(about|details)\b|\bfull\s+(judgment|details)\b", q, re.I):
            r = self._case_detail(q, prev)
            if r:
                return r

        # 2. statute: explicit section numbers
        nums = self._section_numbers(q)
        if nums and (STATUTE_HINT_RE.search(q) or prev.get("code") or len(nq.split()) <= 4
                     or re.search(r"\b(kya|which|what|equivalent|new|old|replaced|corresponding)\b", q, re.I)):
            r = self._statute_by_number(q, nums, prev)
            if r:
                return r

        concepts = self._concepts_by_alias(nq)
        definitional = bool(CONCEPT_HINT_RE.search(q)) or len(nq.split()) <= 5
        long_facts = not definitional

        # 3. statute by topic when a code/section is named ("which bns section deals with organised crime")
        if STATUTE_HINT_RE.search(q) and not CASE_HINT_RE.search(q):
            r = self._statute_by_topic(q)
            if r:
                specific = [c for c in concepts if c.get("category") != "Statutes"]
                if specific:
                    c = specific[0]
                    r.text += f"\n\n**About {c['term']}:** {c['answer']}"
                return r

        # 4. concept by alias (most specific alias wins) for definitional or short questions
        if concepts and definitional:
            return self._concept_answer(concepts, q)

        # 5. concept by fuzzy match (typos) when phrased as a concept question
        if CONCEPT_HINT_RE.search(q) and not long_facts:
            fuzzy = self._concepts_fuzzy(q)
            if fuzzy:
                return self._concept_answer(fuzzy, q)

        # 6. past cases
        if self._has_legal_signal(q) or CASE_HINT_RE.search(q) or len(nq.split()) >= 6:
            r = self._case_search(q)
            if r:
                return r
            if concepts:
                return self._concept_answer(concepts, q)
        return None

    # ── statutes ──
    def _section_numbers(self, q):
        out = []
        for m in SECTION_NUM_RE.finditer(q):
            tok = m.group(1)
            if re.fullmatch(r"\d{4}", tok) or (tok.isdigit() and int(tok) > 600):
                continue   # years / big numbers are not sections
            out.append((_norm_section(tok), m.start()))
        return out

    def _code_for(self, q, pos, prev):
        """Is the number at `pos` an IPC or a BNS section? Look at the nearest code word."""
        best, dist = None, 10 ** 6
        for m in re.finditer(r"\b(ipc|i\.p\.c|indian\s+penal|penal\s+code|bns|nyaya\s+sanhita)\b", q, re.I):
            d = abs(m.start() - pos)
            if d < dist:
                best, dist = ("bns" if re.match(r"(bns|nyaya)", m.group(1), re.I) else "ipc"), d
        if best and re.search(r"\b(bns)\b.{0,25}\b(is\s+which|which|to|in)\s+(ipc|old)", q, re.I) and best == "ipc":
            best = "bns"
        return best or prev.get("code")

    def _statute_by_number(self, q, nums, prev):
        lines, used_code, found = [], None, 0
        for sec, pos in nums[:6]:
            code = self._code_for(q, pos, prev)
            rows, code_used = [], code
            if code in (None, "ipc"):
                rows = self.by_ipc.get(sec) or self.by_ipc.get(sec.split("(")[0], [])
                code_used = "ipc"
            if not rows and code in (None, "bns"):
                rows = self.by_bns.get(sec) or self.by_bns.get(sec.split("(")[0], [])
                code_used = "bns"
            if not rows and code == "ipc":
                rows, code_used = (self.by_bns.get(sec) or []), "bns"
            used_code = used_code or code_used
            if not rows:
                legacy = self._legacy_lookup(sec)
                if legacy:
                    lines.append(f"- **IPC {sec}** → **{legacy}** _(from the project's IPC–BNS mapping)_")
                    found += 1
                else:
                    lines.append(f"- I couldn't find section **{sec}** in the IPC–BNS correspondence table.")
                continue
            found += 1
            for r in rows[:3]:
                lines.append(self._fmt_statute_row(r, code_used))
        if not found:
            return None
        text = "\n".join(lines)
        if any(r.get("status") == "deleted" for sec, _ in nums for r in self.by_ipc.get(sec, [])):
            text += ("\n\n_A **deleted** section has no direct BNS equivalent in the official table; "
                     "offences committed before 1 July 2024 are still tried under the IPC._")
        concept = self._concept_for_sections([s for s, _ in nums])
        if concept:
            text += f"\n\n**Related concept – {concept['term']}:** {concept['answer']}"
        text += "\n\nSource: official BNS 2023 ↔ IPC 1860 correspondence table."
        return Result("statute", text, sources=["BNS–IPC correspondence table"], context={"code": used_code})

    def _fmt_statute_row(self, r, asked_code):
        status = {"same": "same offence, renumbered", "changed": "**changed** in BNS",
                  "new": "**new** in BNS (no IPC equivalent)", "deleted": "**deleted** – not in BNS"}[r["status"]]
        ipc = f"IPC {r['ipc']}" if r.get("ipc") else "—"
        bns = f"BNS {r['bns']}" if r.get("bns") else "—"
        title = r.get("bns_title") or r.get("ipc_title") or ""
        if r["status"] == "deleted":
            legacy = self._legacy_lookup(r["ipc"])
            extra = f" The nearest provision in the project's mapping is **{legacy}**." if legacy else ""
            return f"- **{ipc}** ({r.get('ipc_title', '')}) → {status}.{extra}"
        if r["status"] == "new":
            return f"- **{bns}** – {title} → {status}."
        if not r.get("ipc"):
            return f"- **{bns}** – {title} (sub-section in BNS)"
        first, second = (ipc, bns) if asked_code == "ipc" else (bns, ipc)
        ipc_t = r.get("ipc_title") or ""
        alt = f" (IPC title: {ipc_t})" if ipc_t and _norm(ipc_t) != _norm(title) else ""
        return f"- **{first}** → **{second}** – {title}{alt} ({status})"

    def _legacy_lookup(self, sec):
        key = f"section {sec.lower()}"
        v = self.legacy_map.get(key) or self.legacy_map.get(f"{key} of the ipc")
        return v

    def _statute_by_topic(self, q):
        if not self.statutes:
            return None
        topic = re.sub(r"\b(ipc|bns|bnss|i\.p\.c|section|sections|sec|s\.|code|act|acts|law|laws|indian|penal|"
                       r"bharatiya|nyaya|sanhita|deals?|dealing|with|which|what|is|are|the|in|of|to|and|removed|"
                       r"punishment|offence|offences|under|new|old|conversion|convert|learn|information|about)\b",
                       " ", q.lower())
        if len(re.findall(r"[a-z]{3,}", topic)) == 0:
            return None
        qv = self.stat_vec.transform([topic])
        sims = linear_kernel(qv, self.stat_mat).ravel()
        top = [i for i in np.argsort(-sims)[:4] if sims[i] >= 0.35]
        if not top:
            return None
        lines = ["Here are the matching sections from the official IPC–BNS table:"]
        lines += [self._fmt_statute_row(self.statutes[i], "ipc") for i in top]
        lines.append("\nAsk with a section number (e.g. *“what is 302 IPC in BNS”*) for one exact mapping.")
        return Result("statute", "\n".join(lines), sources=["BNS–IPC correspondence table"], context={"code": "ipc"})

    # ── concepts ──
    def _concepts_by_alias(self, nq):
        found, taken = [], []
        padded = f" {nq} "
        for alias, c in self.alias_index:
            if len(alias) < 3 and alias not in ("pil",):
                continue
            pos = padded.find(f" {alias} ")
            if pos < 0:
                continue
            span = (pos, pos + len(alias))
            if any(not (span[1] <= a or span[0] >= b) for a, b in taken):
                continue   # overlaps a longer alias already matched
            if c not in found:
                found.append(c)
            taken.append(span)
            if len(found) >= 2:
                break
        return found

    def _concepts_fuzzy(self, q):
        if not self.concepts:
            return []
        stripped = re.sub(CONCEPT_HINT_RE, " ", q.lower())
        sims_char = linear_kernel(self.con_vec.transform([stripped]), self.con_mat).ravel()
        sims_word = linear_kernel(self.con_word_vec.transform([q]), self.con_word_mat).ravel()
        sims = np.maximum(sims_char, sims_word * 1.2)
        best = int(np.argmax(sims))
        return [self.concepts[best]] if sims[best] >= 0.30 else []

    def _concept_for_sections(self, secs):
        for c in self.concepts:
            al = " ".join(c.get("aliases", []))
            if any(re.search(rf"\b{re.escape(s.lower())}\s+ipc\b|\bipc\s+{re.escape(s.lower())}\b", al) for s in secs):
                return c
        return None

    def _concept_answer(self, concepts, q):
        parts, sources = [], []
        for c in concepts[:2]:
            block = f"**{c['term']}**\n\n{c['answer']}"
            prov = []
            if c.get("old_law"):
                prov.append(f"Old law: {c['old_law']}")
            if c.get("new_law"):
                prov.append(f"New law: {c['new_law']}")
            if prov:
                block += "\n\n" + " · ".join(prov)
            if c.get("source"):
                block += f"\n\nSource: [{c['source'].split('/')[2]}]({c['source']})"
                sources.append(c["source"])
            parts.append(block)
        text = "\n\n---\n\n".join(parts)
        # add up to two illustrative past cases when the concept appears in the judgments
        cases = self._search_cases(f"{concepts[0]['term']} {q}", k=2, min_score=0.12)
        res = Result("concept", text, sources=sources, context={"concept": concepts[0]["id"]})
        if cases:
            res.cases = cases
            res.text += "\n\n**Past judgments that discuss this:** " + "; ".join(
                f"*{c['name']}* ({c['year'] or 'n.d.'}) – {c['verdict_short']}" for c in cases)
            res.context["cases"] = [c["id"] for c in cases]
        return res

    # ── cases ──
    def _search_cases(self, q, k=3, min_score=0.08):
        if not self.cases or self.case_mat.shape[0] == 0:
            return []
        qv = self.case_vec.transform([q])
        if qv.nnz == 0:
            return []
        n = len(self.cases)
        sims = np.asarray((self.case_mat @ qv.T).todense()).ravel()
        # (a) best single chunk per case, (b) cosine with the whole case
        best = np.zeros(n, dtype=np.float64)
        np.maximum.at(best, self.chunk_case, sims)
        whole = np.bincount(self.chunk_case, weights=sims, minlength=n)
        whole = np.divide(whole, self.case_norm, out=np.zeros(n), where=self.case_norm > 0)

        # candidates: strongest cases by either signal that pass the relevance threshold
        cand = set(np.argsort(-best)[:40].tolist()) | set(np.argsort(-whole)[:40].tolist())
        cand = [ci for ci in cand if best[ci] >= min_score]
        if not cand:
            return []

        # (c) coverage: share of the distinct informative query words that occur anywhere in the case
        words = list(dict.fromkeys(t for t in self._case_analyzer(q) if " " not in t))
        term_idx = [self.case_vec.vocabulary_[t] for t in words if t in self.case_vec.vocabulary_]
        rows = np.concatenate([np.arange(self.case_chunk_start[ci], self.case_chunk_start[ci] + self.case_chunk_count[ci])
                               for ci in cand])
        if term_idx:
            present = (self.case_mat[rows][:, term_idx] > 0).toarray()     # chunks x terms
        else:
            present = np.ones((len(rows), 1), dtype=bool)
        info, pos = {}, 0
        for ci in cand:
            m = int(self.case_chunk_count[ci])
            p = present[pos:pos + m]
            r = rows[pos:pos + m]
            pos += m
            cov = p.any(axis=0).mean()
            # passage chunk: the one with the most distinct query words, then the most similar
            hits = p.sum(axis=1)
            j = max(range(m), key=lambda x: (hits[x], sims[r[x]]))
            score = (0.6 * best[ci] + 0.4 * whole[ci]) * (0.3 + 0.7 * cov)
            info[ci] = (float(score), int(r[j]))
        ranked = sorted(info.items(), key=lambda kv: -kv[1][0])

        terms = [t for t in words if len(t) >= 3] or \
            [t for t in re.findall(r"[a-z]{4,}", q.lower()) if t not in CASE_STOP_WORDS]
        out = []
        for ci, (score, chunk_i) in ranked[:k]:
            c = self.cases[ci]
            passage = self.chunk_text[chunk_i][len(self._chunk_head(c)):]
            out.append({
                "id": c.id, "name": c.name, "court": c.court, "year": c.year, "category": c.category,
                "verdict": VERDICT_TEXT.get(c.verdict, c.verdict or "Unknown"),
                "verdict_short": {"allowed": "Allowed", "dismissed": "Dismissed",
                                  "partly_allowed": "Partly allowed"}.get(c.verdict, c.verdict or "Unknown"),
                "score": round(score, 3),
                "passage": _best_window(passage, terms, continued=chunk_i != self.case_chunk_start[ci]),
                "final_order": c.final_order,
            })
        return out

    def _case_search(self, q):
        cases = self._search_cases(q, k=3)
        if not cases:
            return None
        lines = [f"I found **{len(cases)} past judgment{'s' if len(cases) > 1 else ''}** related to your question "
                 f"(most similar first):"]
        for n, c in enumerate(cases, 1):
            lines.append(f"\n**{n}. {c['name']}** — {c['court']}, {c['year'] or 'year n/a'} · {c['category']}\n"
                         f"- **Verdict:** {c['verdict']}\n"
                         f"- **Relevant passage:** “{c['passage']}”")
        lines.append("\nAsk *“tell me more about the first case”* to see what the court finally ordered.")
        lines.append(DISCLAIMER)
        return Result("case_search", "\n".join(lines), cases=cases,
                      sources=[c["name"] for c in cases], context={"cases": [c["id"] for c in cases]})

    def _case_detail(self, q, prev):
        ids = prev.get("cases") or []
        idx = 0
        for word, i in (("second", 1), ("2nd", 1), ("third", 2), ("3rd", 2)):
            if word in q.lower():
                idx = i
        if idx >= len(ids):
            return None
        c = next((x for x in self.cases if x.id == ids[idx]), None)
        if not c:
            return None
        facts = _clean_ws(c.text[:760])
        if len(facts) > 700:
            facts = facts[:700].rsplit(" ", 1)[0]
        text = (f"**{c.name}** — {c.court}, {c.year or 'year n/a'} · {c.category}\n\n"
                f"**Verdict:** {VERDICT_TEXT.get(c.verdict, c.verdict)}\n\n"
                f"**Opening of the judgment:** {facts}…\n\n"
                f"**What the court finally ordered:** {c.final_order}\n\n{DISCLAIMER}")
        card = {"id": c.id, "name": c.name, "court": c.court, "year": c.year, "category": c.category,
                "verdict": VERDICT_TEXT.get(c.verdict, c.verdict), "verdict_short": c.verdict,
                "passage": _best_window(facts, []), "final_order": c.final_order, "score": None}
        return Result("case_search", text, cases=[card], sources=[c.name], context={"cases": ids})

    # ── fixed replies ──
    def _greeting(self, name=None):
        hi = f"Hi {name}! " if name else "Hello! "
        return Result("greeting", hi + "I'm the Legal AI Hub study assistant. You can ask me:\n"
                      "- **Sections:** *“what is 302 IPC in BNS?”* or *“BNS 103 is which IPC section?”*\n"
                      "- **Concepts:** *“what is anticipatory bail?”*, *“murder vs culpable homicide”*\n"
                      "- **Past cases:** describe the facts, e.g. *“conviction based only on circumstantial evidence”*, "
                      "and I'll show similar judgments with their verdicts.")

    def _help(self):
        n = len(self.cases)
        return Result("help", "I answer from this project's own legal knowledge base, offline:\n"
                      f"- the official **IPC ↔ BNS correspondence table** ({len(self.statutes)} sections),\n"
                      f"- a glossary of **{len(self.concepts)} legal concepts** (bail, FIR, writs, mens rea, …) with "
                      "old and new provisions,\n"
                      f"- **{n} past judgments** with their real verdicts.\n\n"
                      "Ask about a section number, a concept, or describe a fact situation to find similar past cases. "
                      "Follow up with *“tell me more about the first case”*.\n\n" + DISCLAIMER)

    def _unsafe(self):
        return Result("unsafe", "I can't help with avoiding the law, hiding or fabricating evidence, or influencing "
                      "judges, police or witnesses — these are themselves serious offences (for example, causing "
                      "disappearance of evidence and fabricating false evidence are offences under the BNS).\n\n"
                      "If you or someone you know is facing a criminal case, the lawful options are:\n"
                      "- speak to a **lawyer** — every accused has the right to be defended by one (Article 22),\n"
                      "- ask the **District Legal Services Authority** for free legal aid if you can't afford a lawyer,\n"
                      "- apply for **bail / anticipatory bail** through the court.\n\n"
                      "I'm happy to explain any of these, or the law on evidence, for your studies.")

    def _out_of_scope(self):
        return Result("out_of_scope", "That's outside what I can help with — I'm a legal study assistant for Indian "
                      "law. Try asking about an IPC/BNS section, a legal concept, or past court judgments.")

    def _unclear(self, q):
        return Result("unclear", "Sorry, I didn't understand that. Try one of these:\n"
                      "- *“what is 420 IPC in BNS?”*\n- *“explain anticipatory bail”*\n"
                      "- *“past cases where an FIR was quashed after a compromise”*")

    def _no_match(self, q):
        return Result("unclear", "I couldn't find anything on that in my knowledge base. I cover IPC/BNS sections, "
                      "core legal concepts and a set of past Supreme Court / High Court judgments. Try rephrasing with "
                      "a section number, a legal term, or the key facts of the case.")

    # ── optional LLM polishing ──
    def _polish_with_llm(self, q, res):
        """Rewrite the retrieved answer with an OpenAI-compatible model. Falls back to `res` on any error."""
        try:
            import httpx
            cfg = self.llm
            context = res.text
            for c in res.cases:
                context += f"\n\nCASE {c['name']} ({c['year']}), verdict: {c['verdict']}. Final order: {c['final_order']}"
            body = {
                "model": cfg["model"],
                "temperature": 0.2,
                "messages": [
                    {"role": "system", "content": (
                        "You are a study assistant for Indian law students. Answer ONLY from the CONTEXT. "
                        "Keep every section number, case name and verdict exactly as given; never invent cases, "
                        "sections or facts. If the context does not answer the question, say so. "
                        "Write clearly in under 200 words using markdown, and end with: 'Study aid only, not legal advice.'")},
                    {"role": "user", "content": f"QUESTION: {q}\n\nCONTEXT:\n{context}"},
                ],
            }
            headers = {"Authorization": f"Bearer {cfg.get('api_key') or 'none'}"}
            r = httpx.post(cfg["base_url"].rstrip("/") + "/chat/completions", json=body, headers=headers,
                           timeout=float(cfg.get("timeout", 45)))
            r.raise_for_status()
            text = r.json()["choices"][0]["message"]["content"].strip()
            if text:
                res.text = text
                res.sources = res.sources + [f"rewritten by {cfg['model']}"]
        except Exception as e:
            logger.warning(f"LLM polishing skipped: {e}")
        return res


def llm_config_from(get):
    """Build the optional LLM config from a getter (st.secrets.get / os.environ.get). None if not configured."""
    base = get("LLM_BASE_URL")
    model = get("LLM_MODEL")
    if not (base and model):
        return None
    return {"base_url": base, "model": model, "api_key": get("LLM_API_KEY") or "", "timeout": get("LLM_TIMEOUT") or 45}


if __name__ == "__main__":
    import sys
    bot = LegalAssistant()
    print(f"Loaded {len(bot.statutes)} statutes, {len(bot.concepts)} concepts, {len(bot.cases)} cases.")
    hist = []
    for line in (sys.argv[1:] or iter(lambda: input("\nYou: "), "")):
        out = bot.answer(line, hist)
        hist.append(out)
        print(f"\n[{out['intent']}]\n{out['text']}")
