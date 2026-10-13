"""Add more past judgments to the study assistant's case library.

Writes knowledge/extra_cases.csv (columns: name,text,verdict,category,court,year), which
legal_assistant.py loads automatically on the next app start.

Examples (run from the project root, inside the venv):

  # the project's full training dataset (10,231 judgments) - only part of it, to keep RAM low
  python scripts/add_cases.py --csv eval_harness/original_data/labeled_case_categories.csv --limit 1500

  # a folder of judgment PDFs (verdict is guessed from the final order, or left 'unknown')
  python scripts/add_cases.py --pdf-dir "C:/Users/vaish/Downloads/judgments"

Each case keeps at most --max-chars characters of text (default 15,000) so the search index
stays small enough for an 8 GB laptop. Roughly: 1,500 cases ~ 150-250 MB of RAM.
"""
import argparse
import os
import re
import sys

import pandas as pd

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, ROOT)
OUT = os.path.join(ROOT, "knowledge", "extra_cases.csv")
COHORT = os.path.join(ROOT, "eval_harness", "benchmark_cohort.csv")

from legal_assistant import _case_name_from_id, _final_order  # noqa: E402

VERDICT_ALIASES = {"allowed": "allowed", "accepted": "allowed", "1": "allowed", "dismissed": "dismissed",
                   "rejected": "dismissed", "0": "dismissed", "partly_allowed": "partly_allowed",
                   "partly allowed": "partly_allowed", "partially allowed": "partly_allowed", "2": "partly_allowed"}


def pick(df, *names):
    for n in names:
        for c in df.columns:
            if c.lower() == n:
                return c
    return None


def guess_verdict(text):
    order = _final_order(text).lower()
    if re.search(r"partly allowed|partially allowed|allowed in part", order):
        return "partly_allowed"
    if re.search(r"(appeals?|petitions?) (is|are|stands?) (hereby )?allowed|we allow", order):
        return "allowed"
    if re.search(r"(appeals?|petitions?) (is|are|stands?) (hereby )?dismissed|we dismiss|devoid of merit", order):
        return "dismissed"
    return "unknown"


def from_csv(path, limit, max_chars):
    df = pd.read_csv(path)
    text_c = pick(df, "cleaned_text", "text", "judgment", "judgement", "content")
    if not text_c:
        sys.exit(f"No text column found in {path}. Columns: {list(df.columns)}")
    name_c = pick(df, "name", "case_name", "title", "case_id")
    verdict_c = pick(df, "verdict", "label", "raw_label", "outcome")
    cat_c = pick(df, "category", "case_category", "true_case_category")
    court_c = pick(df, "court")
    year_c = pick(df, "year")

    # never duplicate the 120 cases already loaded from benchmark_cohort.csv
    skip = set()
    if os.path.isfile(COHORT):
        skip = set(pd.read_csv(COHORT, usecols=["case_id"])["case_id"].astype(str))

    rows = []
    for _, r in df.iterrows():
        raw_name = str(r[name_c]) if name_c else ""
        if raw_name in skip:
            continue
        text = str(r[text_c] or "")
        if len(text.strip()) < 500:
            continue
        name, year = _case_name_from_id(raw_name) if raw_name else (f"Case {len(rows) + 1}", None)
        verdict = VERDICT_ALIASES.get(str(r[verdict_c]).strip().lower(), "unknown") if verdict_c else guess_verdict(text)
        rows.append({"name": name, "text": text[:max_chars], "verdict": verdict,
                     "category": str(r[cat_c]) if cat_c else "",
                     "court": str(r[court_c]) if court_c else "Supreme Court of India",
                     "year": int(r[year_c]) if year_c and str(r[year_c]).isdigit() else year})
        if limit and len(rows) >= limit:
            break
    return rows


def from_pdfs(folder, limit, max_chars):
    import pymupdf
    rows = []
    for fn in sorted(os.listdir(folder)):
        if not fn.lower().endswith(".pdf"):
            continue
        try:
            doc = pymupdf.open(os.path.join(folder, fn))
            text = "\n".join(doc[i].get_text() for i in range(min(doc.page_count, 150)))
        except Exception as e:
            print(f"  skipped {fn}: {e}")
            continue
        if len(text.strip()) < 500:
            print(f"  skipped {fn}: no text (scanned PDF?)")
            continue
        name, year = _case_name_from_id(fn)
        rows.append({"name": name, "text": text[:max_chars], "verdict": guess_verdict(text),
                     "category": "", "court": "", "year": year})
        if limit and len(rows) >= limit:
            break
    return rows


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--csv")
    ap.add_argument("--pdf-dir")
    ap.add_argument("--limit", type=int, default=1500, help="max cases to add (default 1500)")
    ap.add_argument("--max-chars", type=int, default=15000)
    ap.add_argument("--append", action="store_true", help="add to an existing extra_cases.csv")
    a = ap.parse_args()
    if not (a.csv or a.pdf_dir):
        ap.error("give --csv or --pdf-dir")

    rows = from_csv(a.csv, a.limit, a.max_chars) if a.csv else from_pdfs(a.pdf_dir, a.limit, a.max_chars)
    new = pd.DataFrame(rows, columns=["name", "text", "verdict", "category", "court", "year"])
    if a.append and os.path.isfile(OUT):
        new = pd.concat([pd.read_csv(OUT), new], ignore_index=True).drop_duplicates(subset=["name"])
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    new.to_csv(OUT, index=False)
    print(f"Wrote {len(new)} cases to {OUT}")
    print(new["verdict"].value_counts().to_string())
    print("Restart the app (streamlit run app.py) to load them.")


if __name__ == "__main__":
    main()
