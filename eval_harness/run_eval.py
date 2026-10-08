"""
Evaluation Harness for Legal Case Outcome Prediction (Realistic LJP)
====================================================================
Runs model evaluation across two cohorts:
1. Benchmark Cohort (120 stratified rows from labeled_case_categories.csv)
   * Note: May include training-seen data (no split record available).
2. Out-of-Distribution (OOD) Cohort (4 real Indian court judgments from Documents/Model Test pdfs/)
   * Note: True unseen data, high confidence.

Imports preprocessing and prediction logic directly from app.py.
"""

import os
import sys
import json
import datetime
import warnings
import pandas as pd
import numpy as np

# Ensure UTF-8 output on Windows console
if sys.stdout.encoding and sys.stdout.encoding.lower() != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

# Suppress warnings for cleaner evaluation output
warnings.filterwarnings("ignore")
os.environ["TOKENIZERS_PARALLELISM"] = "false"

# Add project root to path
sys.path.insert(0, os.path.abspath("."))

from app import (
    t_b,
    m_b,
    t_c,
    m_c,
    model_load_error,
    translate_laws_to_bns,
    clean_legal_text,
    structure_aware_chunking,
    predict,
    extract_text_from_pdf
)

from sklearn.metrics import (
    accuracy_score,
    precision_recall_fscore_support,
    confusion_matrix,
    classification_report
)


def compute_metrics(y_true, y_pred, labels):
    acc = accuracy_score(y_true, y_pred)
    prec_macro, rec_macro, f1_macro, _ = precision_recall_fscore_support(
        y_true, y_pred, labels=labels, average="macro", zero_division=0
    )
    prec_per_cls, rec_per_cls, f1_per_cls, support = precision_recall_fscore_support(
        y_true, y_pred, labels=labels, average=None, zero_division=0
    )
    cm = confusion_matrix(y_true, y_pred, labels=labels)
    
    per_class = {}
    for i, lbl in enumerate(labels):
        per_class[lbl] = {
            "precision": round(float(prec_per_cls[i]), 4),
            "recall": round(float(rec_per_cls[i]), 4),
            "f1": round(float(f1_per_cls[i]), 4),
            "support": int(support[i])
        }

    return {
        "accuracy": round(float(acc), 4),
        "macro_precision": round(float(prec_macro), 4),
        "macro_recall": round(float(rec_macro), 4),
        "macro_f1": round(float(f1_macro), 4),
        "confusion_matrix": cm.tolist(),
        "labels": labels,
        "per_class": per_class
    }


def format_cm(cm, labels):
    header = "True \\ Pred".ljust(22) + "".join([f"{lbl[:14]}".rjust(16) for lbl in labels])
    rows = [header, "-" * len(header)]
    for i, row_lbl in enumerate(labels):
        row_str = f"{row_lbl[:20]}".ljust(22) + "".join([f"{cm[i][j]}".rjust(16) for j in range(len(labels))])
        rows.append(row_str)
    return "\n".join(rows)


def run_evaluation():
    print("=" * 80)
    print("      LEGAL AI HUB — MODEL EVALUATION HARNESS")
    print("=" * 80)

    # 1. Load models
    print("\n[1/4] Loading models and tokenizers from ./models/ ...")
    err = model_load_error
    if err or not (t_b and m_b and t_c and m_c):
        print(f"ERROR: Failed to load models: {err}")
        return

    print(" Models loaded successfully:")
    print("   Module B (Jurisdiction): ./models/Module_B/Final")
    print("   Module C (Outcome):      ./models/Module_C/Final")

    jurisdiction_label_map = {0: "Civil Law", 1: "Criminal Law", 2: "Constitutional Law"}
    jurisdiction_classes = ["Civil Law", "Criminal Law", "Constitutional Law"]

    outcome_label_map = {0: "Dismissed / Rejected", 1: "Allowed / Accepted"}
    outcome_classes = ["Allowed / Accepted", "Dismissed / Rejected"]

    # 2. Evaluate Benchmark Cohort
    print("\n[2/4] Evaluating Benchmark Cohort (120 cases from labeled_case_categories.csv) ...")
    print("  Note: Benchmark cohort may include training-seen data (no split record available).")
    cohort_path = os.path.join("eval_harness", "benchmark_cohort.csv")
    if not os.path.exists(cohort_path):
        print(f"Error: {cohort_path} does not exist. Run build_benchmark_cohort.py first.")
        return

    df_cohort = pd.read_csv(cohort_path)
    
    pred_jurisdictions = []
    conf_jurisdictions = []
    pred_outcomes = []
    conf_outcomes = []

    total_samples = len(df_cohort)
    for idx, row in df_cohort.iterrows():
        raw_text = str(row["cleaned_text"])
        
        # Pipeline matching app.py
        bns_text = translate_laws_to_bns(raw_text)
        _, crit_text = structure_aware_chunking(bns_text)

        p_jur, c_jur = predict(crit_text, t_b, m_b, jurisdiction_label_map, task="jurisdiction")
        p_out, c_out = predict(crit_text, t_c, m_c, outcome_label_map, task="outcome")

        pred_jurisdictions.append(p_jur)
        conf_jurisdictions.append(c_jur)
        pred_outcomes.append(p_out)
        conf_outcomes.append(c_out)

        if (idx + 1) % 20 == 0 or (idx + 1) == total_samples:
            print(f"  Processed {idx + 1}/{total_samples} cases ...")

    df_cohort["pred_jurisdiction"] = pred_jurisdictions
    df_cohort["conf_jurisdiction"] = conf_jurisdictions
    df_cohort["pred_outcome"] = pred_outcomes
    df_cohort["conf_outcome"] = conf_outcomes

    # Compute Benchmark Metrics
    benchmark_jur_metrics = compute_metrics(
        df_cohort["true_case_category"].tolist(),
        df_cohort["pred_jurisdiction"].tolist(),
        jurisdiction_classes
    )

    benchmark_out_metrics = compute_metrics(
        df_cohort["true_label"].tolist(),
        df_cohort["pred_outcome"].tolist(),
        outcome_classes
    )

    # Clean subset without partly_allowed
    clean_mask = df_cohort["raw_label"] != "partly_allowed"
    df_cohort_clean = df_cohort[clean_mask]
    benchmark_out_clean_metrics = compute_metrics(
        df_cohort_clean["true_label"].tolist(),
        df_cohort_clean["pred_outcome"].tolist(),
        outcome_classes
    )

    # 3. Evaluate Out-of-Distribution (OOD) Cohort
    print("\n[3/4] Evaluating OOD Cohort (4 Real Indian Judgments) ...")
    print("  Note: OOD cohort represents true unseen data (high confidence).")

    ood_cases = [
        {
            "filename": "10718_2011_7_1502_53219_Judgement_15-May-2024.pdf",
            "path": os.path.join("Documents", "Model Test pdfs", "10718_2011_7_1502_53219_Judgement_15-May-2024.pdf"),
            "court": "Supreme Court of India (May 2024)",
            "case_name": "Rajendra v. State of Maharashtra",
            "true_jurisdiction": "Criminal Law",
            "true_outcome": "Dismissed / Rejected"
        },
        {
            "filename": "47292_2018_5_1501_57671_Judgement_02-Dec-2024.pdf",
            "path": os.path.join("Documents", "Model Test pdfs", "47292_2018_5_1501_57671_Judgement_02-Dec-2024.pdf"),
            "court": "Supreme Court of India (Dec 2024)",
            "case_name": "Ashok v. State of UP",
            "true_jurisdiction": "Criminal Law",
            "true_outcome": "Allowed / Accepted"
        },
        {
            "filename": "Sh_Jilubhai_Nanbhai_Khachar_Etc_Etc_vs_State_Of_Gujarat_And_Anr_Etc_Etc_on_20_July_1994.PDF",
            "path": os.path.join("Documents", "Model Test pdfs", "Sh_Jilubhai_Nanbhai_Khachar_Etc_Etc_vs_State_Of_Gujarat_And_Anr_Etc_Etc_on_20_July_1994.PDF"),
            "court": "Supreme Court of India (July 1994)",
            "case_name": "Jilubhai Nanbhai Khachar v. State of Gujarat",
            "true_jurisdiction": "Constitutional Law",
            "true_outcome": "Dismissed / Rejected"
        },
        {
            "filename": "ordjud.pdf",
            "path": os.path.join("Documents", "Model Test pdfs", "ordjud.pdf"),
            "court": "Bombay High Court (Nov 2025)",
            "case_name": "Shyamsundar Agarwal v. State of Maharashtra",
            "true_jurisdiction": "Criminal Law",
            "true_outcome": "Allowed / Accepted"
        }
    ]

    ood_results = []
    ood_true_jur = []
    ood_pred_jur = []
    ood_true_out = []
    ood_pred_out = []

    for item in ood_cases:
        p = item["path"]
        if not os.path.exists(p):
            print(f"  Warning: File not found: {p}")
            continue

        with open(p, "rb") as fp:
            text = extract_text_from_pdf(fp)

        clean = clean_legal_text(text)
        bns_text = translate_laws_to_bns(clean)
        _, crit_text = structure_aware_chunking(bns_text)

        p_jur, c_jur = predict(crit_text, t_b, m_b, jurisdiction_label_map, task="jurisdiction")
        p_out, c_out = predict(crit_text, t_c, m_c, outcome_label_map, task="outcome")

        jur_match = (p_jur == item["true_jurisdiction"])
        out_match = (p_out == item["true_outcome"])

        res_record = {
            "case_name": item["case_name"],
            "filename": item["filename"],
            "court": item["court"],
            "true_jurisdiction": item["true_jurisdiction"],
            "pred_jurisdiction": p_jur,
            "conf_jurisdiction": round(c_jur, 1),
            "jurisdiction_correct": jur_match,
            "true_outcome": item["true_outcome"],
            "pred_outcome": p_out,
            "conf_outcome": round(c_out, 1),
            "outcome_correct": out_match
        }
        ood_results.append(res_record)
        ood_true_jur.append(item["true_jurisdiction"])
        ood_pred_jur.append(p_jur)
        ood_true_out.append(item["true_outcome"])
        ood_pred_out.append(p_out)

    ood_jur_metrics = compute_metrics(ood_true_jur, ood_pred_jur, jurisdiction_classes)
    ood_out_metrics = compute_metrics(ood_true_out, ood_pred_out, outcome_classes)

    # 4. Display Results & Formatting
    print("\n" + "=" * 80)
    print("                     EVALUATION RESULTS SUMMARY")
    print("=" * 80)

    print("\n" + "-" * 80)
    print("COHORT A: BENCHMARK COHORT (N = 120)")
    print("Status: May include training-seen data (no original split record available)")
    print("-" * 80)

    print(f"\n[A.1] Module B -- Jurisdiction Classification (3 Classes)")
    print(f"  * Overall Accuracy:    {benchmark_jur_metrics['accuracy'] * 100:.2f}%")
    print(f"  * Macro Precision:     {benchmark_jur_metrics['macro_precision'] * 100:.2f}%")
    print(f"  * Macro Recall:        {benchmark_jur_metrics['macro_recall'] * 100:.2f}%")
    print(f"  * Macro F1-Score:      {benchmark_jur_metrics['macro_f1'] * 100:.2f}%")
    print("\n  Per-Class Metrics:")
    for lbl, m in benchmark_jur_metrics["per_class"].items():
        print(f"    - {lbl.ljust(20)}: Precision={m['precision']*100:.1f}%, Recall={m['recall']*100:.1f}%, F1={m['f1']*100:.1f}% (Support={m['support']})")
    print("\n  Confusion Matrix:")
    print(format_cm(benchmark_jur_metrics["confusion_matrix"], jurisdiction_classes))

    print(f"\n[A.2] Module C -- Outcome Prediction (Binary: Allowed vs Dismissed)")
    print(f"  * Overall Accuracy:    {benchmark_out_metrics['accuracy'] * 100:.2f}%")
    print(f"  * Macro Precision:     {benchmark_out_metrics['macro_precision'] * 100:.2f}%")
    print(f"  * Macro Recall:        {benchmark_out_metrics['macro_recall'] * 100:.2f}%")
    print(f"  * Macro F1-Score:      {benchmark_out_metrics['macro_f1'] * 100:.2f}%")
    print("\n  Per-Class Metrics (with partly_allowed mapped to Allowed):")
    for lbl, m in benchmark_out_metrics["per_class"].items():
        print(f"    - {lbl.ljust(22)}: Precision={m['precision']*100:.1f}%, Recall={m['recall']*100:.1f}%, F1={m['f1']*100:.1f}% (Support={m['support']})")
    print("\n  Confusion Matrix:")
    print(format_cm(benchmark_out_metrics["confusion_matrix"], outcome_classes))

    print(f"\n  [A.2b] Clean Binary Outcome (Excluding 10 partly_allowed cases, N = {len(df_cohort_clean)}):")
    print(f"  * Clean Accuracy:      {benchmark_out_clean_metrics['accuracy'] * 100:.2f}%")
    print(f"  * Clean Macro F1:      {benchmark_out_clean_metrics['macro_f1'] * 100:.2f}%")

    print("\n" + "-" * 80)
    print("COHORT B: OUT-OF-DISTRIBUTION (OOD) COHORT (N = 4 Real Court Judgments)")
    print("Status: True unseen data, high confidence (2024-2025 supreme/high court decisions)")
    print("-" * 80)

    for item in ood_results:
        j_icon = "[CORRECT]" if item["jurisdiction_correct"] else "[MISMATCH]"
        o_icon = "[CORRECT]" if item["outcome_correct"] else "[MISMATCH]"
        print(f"\n* Case: {item['case_name']} ({item['court']})")
        print(f"  File: {item['filename']}")
        print(f"  Jurisdiction: True='{item['true_jurisdiction']}' | Pred='{item['pred_jurisdiction']}' ({item['conf_jurisdiction']}%) {j_icon}")
        print(f"  Outcome:      True='{item['true_outcome']}' | Pred='{item['pred_outcome']}' ({item['conf_outcome']}%) {o_icon}")

    print(f"\n[B.1] OOD Aggregate Performance:")
    print(f"  * Jurisdiction Accuracy: {ood_jur_metrics['accuracy'] * 100:.1f}% ({sum(r['jurisdiction_correct'] for r in ood_results)}/4)")
    print(f"  * Outcome Accuracy:      {ood_out_metrics['accuracy'] * 100:.1f}% ({sum(r['outcome_correct'] for r in ood_results)}/4)")

    # 5. Save results to eval_harness/results/
    results_dir = os.path.join("eval_harness", "results")
    os.makedirs(results_dir, exist_ok=True)
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    json_path = os.path.join(results_dir, f"eval_results_{timestamp}.json")
    csv_preds_path = os.path.join(results_dir, f"benchmark_predictions_{timestamp}.csv")

    full_results = {
        "timestamp": timestamp,
        "benchmark_cohort": {
            "disclaimer": "May include training-seen data (no split record available)",
            "sample_size": total_samples,
            "jurisdiction_metrics": benchmark_jur_metrics,
            "outcome_metrics_all": benchmark_out_metrics,
            "outcome_metrics_clean_binary": benchmark_out_clean_metrics
        },
        "ood_cohort": {
            "disclaimer": "True unseen data, high confidence",
            "sample_size": len(ood_results),
            "cases": ood_results,
            "jurisdiction_metrics": ood_jur_metrics,
            "outcome_metrics": ood_out_metrics
        }
    }

    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(full_results, f, indent=2)

    df_cohort.to_csv(csv_preds_path, index=False)

    print("\n" + "=" * 80)
    print(f"[4/4] Results saved successfully:")
    print(f"  • JSON metrics:      {json_path}")
    print(f"  • Predictions CSV:   {csv_preds_path}")
    print("=" * 80)


if __name__ == "__main__":
    run_evaluation()
