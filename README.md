# AI for Legal Case Outcome Prediction (Legal AI Hub)

A Streamlit decision-support tool for Indian court judgments. It reads a judgment (PDF or TXT), extracts the facts and arguments, and uses two fine-tuned **InLegalBERT** models to predict the **jurisdiction** (Civil / Criminal / Constitutional) and the **appellate outcome** (Allowed / Dismissed). A SHAP panel shows which words pushed the outcome model toward its prediction.

It is a decision-support estimate, not legal advice.

---

## Key features

- **PDF parsing:** PyMuPDF extracts the text; regex cleaning drops reporter headers and splits the judgment into Facts, Arguments and Judgment.
- **Two InLegalBERT classifiers:** Module B predicts the jurisdiction, Module C predicts the outcome, each with a confidence percentage.
- **No leakage of the verdict:** facts and arguments are only taken from text *before* the judgment boundary ("in the result", "for the foregoing reasons", "conclusion", ...), so the final order never reaches the model.
- **AI Decision Drivers (SHAP):** click **Generate AI Decision Drivers** to run a SHAP Partition explainer with a text masker over the first 256 tokens of the facts and arguments. It shows the words pushing toward / against the predicted outcome and a highlighted passage. Takes roughly 30-90 seconds on CPU.
- **IPC → BNS tab:** lists the IPC sections found in the document with their Bharatiya Nyaya Sanhita (BNS) equivalents from [bns_mapping.json](bns_mapping.json). BNS is shown for reference only: the models read the original citations, and any BNS citations in newer judgments are mapped back to IPC before inference (the models were fine-tuned on IPC-era judgments).
- **Honest fallbacks:** if the models cannot be loaded, a keyword-based rule set gives a "rule-based estimate" with no confidence percentage. If inference fails, no prediction is shown.
- **Research Vault, IPC-BNS Lab, Case History and Role Requests** modules backed by Supabase, with role-based access (Student, Lawyer, Judge, Admin) and per-user row-level security.

---

## How a document is processed

1. **Ingestion:** upload a court judgment or appeal (PDF or TXT).
2. **Preprocessing** (`prepare_document()` in [app.py](app.py)): clean the text, cut at the judgment boundary, extract Facts + Arguments, map BNS citations back to IPC.
3. **Inference:** by default each model reads the **first 512 tokens** of the extracted Facts + Arguments. Optionally, tick **Analyse full document (sliding window, slower)** to score up to 8 overlapping 512-token windows (stride 128) and average the probabilities.
4. **Explainability:** optional SHAP decision drivers for the outcome model (see above).
5. **Output:** jurisdiction, outcome and confidence, plus Facts / Arguments / Judgment / IPC → BNS / Full Text tabs. Predictions are logged to the `case_predictions` table when the database is connected.

---

## Models on Hugging Face

The fine-tuned checkpoints are hosted at [Nick1027/legal-case-outcome-predictor](https://huggingface.co/Nick1027/legal-case-outcome-predictor) (subfolders `Module_B` and `Module_C`). The app loads them from `./models/Module_B/Final` and `./models/Module_C/Final`; if a local copy is missing it downloads it from Hugging Face on first run (needs internet). The `models/` folder is gitignored.

---

## Quick start

### Windows (one click)

After creating the virtual environment once (step 2 below), double-click [run_demo.bat](run_demo.bat). It activates `venv`, runs `check_setup.py` and starts the app at http://localhost:8501.

### Manual

1. Clone the repository:

   ```bash
   git clone https://github.com/Bharambevaish/AI-for-Legal-Case.git
   cd AI-for-Legal-Case
   ```

2. Create and activate a virtual environment (Python 3.10 or 3.11):

   ```bash
   python -m venv venv
   # Windows (PowerShell):
   .\venv\Scripts\Activate.ps1
   # macOS / Linux:
   source venv/bin/activate
   ```

3. Install dependencies:

   ```bash
   pip install -r requirements.txt
   ```

4. (Optional) Connect Supabase: create `.streamlit/secrets.toml` with `SUPABASE_URL` and `SUPABASE_KEY`, and run [schema.sql](schema.sql) in the Supabase SQL Editor. Full steps, including creating the first Admin, are in [SETUP.md](SETUP.md). Without these secrets the app runs in an offline demo mode where nothing is saved.

5. Run the app:

   ```bash
   python -m streamlit run app.py
   ```

   Open http://localhost:8501, sign in, upload a judgment PDF in **Case Predictor**, and optionally click **Generate AI Decision Drivers**. Sample judgments are in [Model Test pdfs/](<Model Test pdfs/>).

---

## Legal Study Assistant (chatbot)

The **IPC-BNS Lab** page is a study chatbot for law students. It is free and works offline: it retrieves from the project's own knowledge base and composes a cited answer, so it does not invent sections or cases.

| It answers | From | Example |
| --- | --- | --- |
| IPC ↔ BNS sections, both directions, including deleted and new sections | [`knowledge/statutes.json`](knowledge/statutes.json): 543 rows parsed from the official correspondence table (`Documents/BNS_IPC_Comparative.pdf`) by [`scripts/build_statutes.py`](scripts/build_statutes.py) | "what is 302 IPC in BNS?", "BNS 103 is which IPC section?" |
| Legal concepts, with old and new provisions and a source link | [`knowledge/concepts.json`](knowledge/concepts.json): 58 entries | "explain anticipatory bail", "murder vs culpable homicide" |
| Similar past judgments, with their real verdict and the court's final order | 124 judgments (`eval_harness/benchmark_cohort.csv` + `Model Test pdfs/`) | "conviction based only on circumstantial evidence" |

It also handles greetings, follow-ups ("what about 307?", "tell me more about the first case"), typos, off-topic questions, and requests for help breaking the law (refused, with lawful options).

**How it works:** [`legal_assistant.py`](legal_assistant.py) routes the question by intent, searches with TF-IDF (scikit-learn), and formats the answer. It has no Streamlit dependency, so you can try it in a terminal with `python legal_assistant.py`.

**Add more judgments:** `python scripts/add_cases.py --csv <dataset.csv> --limit 1500` or `--pdf-dir <folder>`. This writes `knowledge/extra_cases.csv`, which is loaded on the next start. Keep `--limit` modest on 8 GB laptops.

**Optional: more natural wording with a free model.** Add these to `.streamlit/secrets.toml`. The model only rewrites the retrieved facts, and the bot falls back to offline answers if the model is unreachable.

```toml
# Local and free: install Ollama from https://ollama.com, then run:  ollama pull qwen2.5:1.5b   (~1 GB download, ~2 GB RAM)
LLM_BASE_URL = "http://localhost:11434/v1"
LLM_MODEL = "qwen2.5:1.5b"
# Or any OpenAI-compatible free-tier API: also set LLM_API_KEY. Questions are then sent to that provider.
```

---

## Testing

```bash
python -m pytest tests -q   # pipeline + chatbot tests; model tests are skipped if ./models is missing
python check_setup.py       # demo-readiness check: venv, packages, RAM, models, a test prediction, Supabase
python check_setup.py --shap   # also times one SHAP explanation
python eval_harness/chatbot_eval.py   # chatbot harness: 67 positive and negative questions, scores intent, content and case retrieval
```

---

## Performance

Measured with [eval_harness/run_eval.py](eval_harness/run_eval.py) on a 120-case stratified benchmark cohort, after the chunking fix described in [eval_harness/RESULTS.md](eval_harness/RESULTS.md):

| Model | Accuracy | Macro F1 |
| :--- | :--- | :--- |
| Module B: jurisdiction (3 classes) | 76.67% | 68.47% |
| Module C: outcome (Allowed / Dismissed) | 67.50% | 66.66% |

These numbers were measured **before** the latest pipeline fixes (judgment-boundary cut, IPC/BNS handling) and may change. Re-run them with:

```bash
python eval_harness/run_eval.py
```

The benchmark cohort may include cases seen during training (no train/test split record is available); see [eval_harness/RESULTS.md](eval_harness/RESULTS.md) for details and limitations.

---

## Team & acknowledgments

- **Developed by:** Nikhil Raghuwanshi, Shital Kalekar, Shraddha Dhanwate, Amay Lohar
- **Guided by:** Prof. Priyanka Patil
- **Institution:** Dept. of CSE (Artificial Intelligence), Nutan College of Engineering and Research, Pune

---

## Future scope

- **BNS-native models:** fine-tune on post-July-2024 judgments that cite the Bharatiya Nyaya Sanhita directly, instead of mapping BNS back to IPC.
- **Multilingual support:** Marathi, Hindi and Tamil judgments.
- **Granular predictions:** sentence lengths and settlement amounts.

See [agent.md](agent.md) for the full technical reference and [implementation_summary.md](implementation_summary.md) for the module list and recent changes.
