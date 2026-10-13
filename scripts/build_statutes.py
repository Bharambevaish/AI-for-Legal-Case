"""Build knowledge/statutes.json from Documents/BNS_IPC_Comparative.pdf.

The PDF is the BNS 2023 <-> IPC 1860 corresponding-section table (two columns,
23 pages). Each output record is one BNS section (or a deleted IPC section):

    {"bns": "103", "bns_title": "Punishment for murder.", "ipc": "302",
     "ipc_title": "Punishment for murder.", "status": "same|changed|new|deleted",
     "chapter_bns": "...", "chapter_ipc": "..."}

Run from the project root:  python scripts/build_statutes.py
"""
import json
import os
import re
import sys

import pymupdf

SRC = os.path.join("Documents", "BNS_IPC_Comparative.pdf")
OUT = os.path.join("knowledge", "statutes.json")

# "103. Punishment for murder." / "2(1) 'act'" / "171-I. Failure to ..." / "1(1)"
SEC_RE = re.compile(r"^\s*(\d+[A-Z]?(?:-[A-Z]+)?(?:\s?\(\d+\))*)\s*(?:[.\s]\s*(.*))?$")


def clean(cell):
    return re.sub(r"\s+", " ", (cell or "").replace("\n", " ")).strip()


def split_section(cell):
    """'103. Punishment for murder. (Change)' -> ('103', 'Punishment for murder.', changed?)"""
    changed = "(change)" in cell.lower()
    cell = re.sub(r"\(\s*change\s*\)", "", cell, flags=re.I).strip()
    m = SEC_RE.match(cell)
    if not m:
        return None, cell, changed
    num, title = re.sub(r"\s+", "", m.group(1)), (m.group(2) or "").strip()
    # "1. Short title, commencement and application. 1(1)" -> drop trailing sub-section ref
    title = re.sub(r"\s+\d+\s?\(\d+\)$", "", title).strip()
    return num.replace("-", ""), title, changed


def main():
    if not os.path.isfile(SRC):
        sys.exit(f"Not found: {SRC}")
    doc = pymupdf.open(SRC)
    rows = []
    for page in doc:
        for table in page.find_tables().tables:
            for r in table.extract():
                if len(r) >= 2:
                    rows.append((clean(r[0]), clean(r[1])))

    records, ch_bns, ch_ipc = [], "", ""
    for left, right in rows:
        if not left and not right:
            continue
        if left.startswith(("Bharatiya Nyaya", "2023 (BNS)", "Corresponding Section")):
            continue
        if left.upper().startswith("CHAPTER") or right.upper().startswith("CHAPTER"):
            ch_bns, ch_ipc = left or ch_bns, right or ch_ipc
            continue
        if left.isupper() and right.isupper() and not re.match(r"\d", left):
            # continuation of a chapter heading split across two rows
            ch_bns, ch_ipc = f"{ch_bns} {left}".strip(), f"{ch_ipc} {right}".strip()
            continue

        if left.lower() == "deleted":
            ipc, ipc_title, _ = split_section(right)
            if ipc:
                records.append({"bns": None, "bns_title": "", "ipc": ipc, "ipc_title": ipc_title,
                                "status": "deleted", "chapter_bns": ch_bns, "chapter_ipc": ch_ipc})
            continue

        bns, bns_title, changed = split_section(left)
        if not bns:
            continue
        r_low = right.lower()
        if r_low.startswith("new"):
            ipc, ipc_title, status = None, "", "new"
        else:
            ipc, ipc_title, _ = split_section(right)
            status = "changed" if changed else "same"
            if not ipc:
                ipc_title = right
        if not bns_title and records and records[-1]["bns"] and bns.startswith(records[-1]["bns"].split("(")[0]):
            bns_title = records[-1]["bns_title"]   # sub-section rows such as "1(2)" inherit the title
        records.append({"bns": bns, "bns_title": bns_title, "ipc": ipc, "ipc_title": ipc_title,
                        "status": status, "chapter_bns": ch_bns, "chapter_ipc": ch_ipc})

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(records, f, ensure_ascii=False, indent=1)
    by = {}
    for r in records:
        by[r["status"]] = by.get(r["status"], 0) + 1
    print(f"Wrote {len(records)} records to {OUT}: {by}")


if __name__ == "__main__":
    main()
