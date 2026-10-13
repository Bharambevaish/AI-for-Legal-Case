"""Add more past judgments to the study assistant's case library.

Writes knowledge/extra_cases.csv (columns: name,text,verdict,category,court,year), which
legal_assistant.py loads automatically on the next app start.

Examples (run from the project root, inside the venv):

  # the project's full training dataset (10,231 judgments) - only part of it, to keep RAM low
  python scripts/add_cases.py --csv eval_harness/original_data/labeled_case_categories.csv --limit 1500
  #   (reads the 530 MB file in 500-row chunks and keeps a balanced sample by category x verdict)

  # a folder of judgment PDFs (verdict is guessed from the final order, or left 'unknown')
  python scripts/add_cases.py --pdf-dir "C:/Users/vaish/Downloads/judgments"

Each case keeps at most --max-chars characters of text (default 15,000) so the search index
stays small enough for an 8 GB laptop. Roughly: 1,000 cases ~ 300 MB of RAM for the app.
At the end the search index is built once and cached (knowledge/.index_cache.joblib), so the
app starts in about a second instead of re-indexing every time.
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

from legal_assistant import _case_name_from_id, _final_order, _year_from_text  # noqa: E402

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


def from_csv(path, limit, max_chars, seed=42):
    """Two light passes over a (possibly huge) CSV, 500 rows at a time:
    1) read only the name/verdict/category columns and choose a balanced sample
       (equal share per category x verdict), 2) read the text of just those rows."""
    header = pd.read_csv(path, nrows=0)
    text_c = pick(header, "cleaned_text", "text", "judgment", "judgement", "content")
    if not text_c:
        sys.exit(f"No text column found in {path}. Columns: {list(header.columns)}")
    name_c = pick(header, "name", "case_name", "title", "case_id")
    verdict_c = pick(header, "verdict", "label", "raw_label", "outcome")
    cat_c = pick(header, "category", "case_category", "true_case_category")
    court_c = pick(header, "court")
    year_c = pick(header, "year")
    meta_cols = [c for c in (name_c, verdict_c, cat_c) if c]

    # never duplicate the 120 cases already loaded from benchmark_cohort.csv
    skip = set()
    if os.path.isfile(COHORT):
        skip = set(pd.read_csv(COHORT, usecols=["case_id"])["case_id"].astype(str))

    print("Pass 1/2: scanning case list ...")
    meta = pd.concat(pd.read_csv(path, usecols=meta_cols or [text_c], chunksize=500), ignore_index=True)
    if name_c:
        meta = meta[~meta[name_c].astype(str).isin(skip)]
    print(f"  {len(meta)} candidate cases")
    if limit and len(meta) > limit:
        groups = [g for g in (meta[cat_c].astype(str) if cat_c else [""] * len(meta),
                              meta[verdict_c].astype(str) if verdict_c else [""] * len(meta))]
        key = groups[0] + "|" + groups[1]
        per = max(1, limit // key.nunique())
        chosen = meta.groupby(key, group_keys=False).apply(lambda g: g.sample(min(len(g), per), random_state=seed))
        if len(chosen) < limit:   # top up from what is left
            rest = meta.drop(chosen.index)
            chosen = pd.concat([chosen, rest.sample(min(len(rest), limit - len(chosen)), random_state=seed)])
        wanted = set(chosen.index[:limit])
    else:
        wanted = set(meta.index)

    print(f"Pass 2/2: reading text of {len(wanted)} cases ...")
    rows, offset = [], 0
    usecols = list(dict.fromkeys([c for c in (name_c, text_c, verdict_c, cat_c, court_c, year_c) if c]))
    for chunk in pd.read_csv(path, usecols=usecols, chunksize=500):
        chunk.index = range(offset, offset + len(chunk))
        offset += len(chunk)
        for i, r in chunk[chunk.index.isin(wanted)].iterrows():
            text = str(r[text_c] or "")
            if len(text.strip()) < 500:
                continue
            raw_name = str(r[name_c]) if name_c else ""
            name, year = _case_name_from_id(raw_name) if raw_name else (f"Case {i}", None)
            verdict = VERDICT_ALIASES.get(str(r[verdict_c]).strip().lower(), "unknown") if verdict_c else guess_verdict(text)
            if year_c and str(r[year_c]).isdigit():
                year = int(r[year_c])
            rows.append({"name": name, "text": text[:max_chars], "verdict": verdict,
                         "category": str(r[cat_c]) if cat_c else "",
                         "court": str(r[court_c]) if court_c else "Supreme Court of India",
                         "year": year or _year_from_text(text)})
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
                     "category": "", "court": "", "year": year or _year_from_text(text)})
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
    del new, rows

    # Build the search index once now (saved to knowledge/.index_cache.joblib), so the next app start
    # just loads it instead of re-indexing every judgment.
    print("Building search index ...")
    import time
    from legal_assistant import CACHE_PATH, build_index_cache
    t0 = time.time()
    bot = build_index_cache()
    if bot.cache_status == "saved":
        print(f"  indexed {len(bot.cases)} cases in {time.time() - t0:.0f}s -> {os.path.relpath(CACHE_PATH, ROOT)}")
    else:
        print("  could not save the index cache; the app will build it on its first start instead")
    print("Restart the app (streamlit run app.py) to load them.")


if __name__ == "__main__":
    main()
