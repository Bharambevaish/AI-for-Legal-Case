"""
Build Benchmark Cohort for Legal AI Model Evaluation
===================================================
Extracts a stratified sample of 120 rows from labeled_case_categories.csv
preserving jurisdiction proportions:
  - 60 Civil Law
  - 40 Criminal Law
  - 20 Constitutional Law
and stratified across outcome classes (allowed, dismissed, partly_allowed)
using fixed random_state=42.
"""

import os
import pandas as pd

def build_cohort():
    input_path = os.path.join("eval_harness", "original_data", "labeled_case_categories.csv")
    output_path = os.path.join("eval_harness", "benchmark_cohort.csv")

    if not os.path.exists(input_path):
        raise FileNotFoundError(f"Input file not found: {input_path}")

    print(f"Loading {input_path} ...")
    # Read only needed columns to keep memory light
    df = pd.read_csv(
        input_path,
        usecols=["case_id", "cleaned_text", "label", "case_category"]
    )
    print(f"Loaded {len(df)} total rows.")

    # Target jurisdiction allocations
    quotas = {
        "Civil Law": 60,
        "Criminal Law": 40,
        "Constitutional Law": 20
    }

    sampled_dfs = []
    for category, n_samples in quotas.items():
        sub_df = df[df["case_category"] == category]
        
        # Stratify within category by outcome label
        stratified_sample = sub_df.groupby("label", group_keys=False).apply(
            lambda x: x.sample(
                n=max(1, int(round(len(x) / len(sub_df) * n_samples))),
                random_state=42
            )
        )
        
        # Adjust if rounding gave slightly different count
        if len(stratified_sample) > n_samples:
            stratified_sample = stratified_sample.sample(n=n_samples, random_state=42)
        elif len(stratified_sample) < n_samples:
            needed = n_samples - len(stratified_sample)
            remaining = sub_df.drop(stratified_sample.index)
            top_up = remaining.sample(n=needed, random_state=42)
            stratified_sample = pd.concat([stratified_sample, top_up])

        print(f"Sampled {len(stratified_sample)} rows for {category}:")
        print(stratified_sample["label"].value_counts().to_dict())
        sampled_dfs.append(stratified_sample)

    cohort = pd.concat(sampled_dfs).sample(frac=1.0, random_state=42).reset_index(drop=True)

    # Outcome Mapping:
    # 'allowed' -> 'Allowed / Accepted'
    # 'partly_allowed' -> 'Allowed / Accepted' (Appellate relief was partially granted)
    # 'dismissed' -> 'Dismissed / Rejected'
    cohort["raw_label"] = cohort["label"]
    cohort["true_case_category"] = cohort["case_category"]
    cohort["true_label"] = cohort["label"].apply(
        lambda x: "Allowed / Accepted" if x in ["allowed", "partly_allowed"] else "Dismissed / Rejected"
    )

    final_df = cohort[["case_id", "cleaned_text", "true_case_category", "true_label", "raw_label"]]

    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    final_df.to_csv(output_path, index=False)
    file_size_mb = round(os.path.getsize(output_path) / (1024 * 1024), 2)
    print("=" * 60)
    print(f"Benchmark cohort saved to: {output_path} ({file_size_mb} MB)")
    print(f"Total rows: {len(final_df)}")
    print("\nJurisdiction breakdown:")
    print(final_df["true_case_category"].value_counts())
    print("\nMapped Outcome breakdown:")
    print(final_df["true_label"].value_counts())
    print("\nRaw Outcome breakdown:")
    print(final_df["raw_label"].value_counts())
    print("=" * 60)

if __name__ == "__main__":
    build_cohort()
