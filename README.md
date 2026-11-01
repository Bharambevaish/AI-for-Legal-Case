# AI for Legal Case Outcome Prediction ⚖️🤖

An advanced, end-to-end Legal AI decision-support tool designed to modernize the Indian Judicial System. This system digests lengthy, unstructured court judgment PDFs, bypasses token limitations, and utilizes a fine-tuned **InLegalBERT** model to predict appellate outcomes with high accuracy.

Crucially, it breaks the "Black Box" of Deep Learning by integrating **Explainable AI (SHAP)**, visually highlighting the exact legal statutes, facts, and phrases that drove the AI's prediction.

---

## 🌟 Key Features
* **📄 Automated PDF Parsing:** Utilizes PyMuPDF and custom Regex to strip away irrelevant administrative metadata (Coram, headers) and extract pure legal facts.
* **🧠 Dual-Inference Pipeline:** Fine-tuned InLegalBERT models predict both the Jurisdiction (Civil/Criminal/Constitutional) and the Appellate Outcome (Allowed/Dismissed).
* **⚖️ Domain-Specific NLP:** Outperforms generic LLMs (like GPT-3.5/LLaMA) by understanding deep Indian legal semantics (e.g., IPC Sections, Bail, FIR).
* **🔍 Explainable AI (XAI):** Integrated SHAP (SHapley Additive exPlanations) generates interactive visual heatmaps, proving mathematically why the AI made its decision.
* **💻 Modern UI:** Built with Streamlit for a fast, intuitive, "drag-and-drop" user experience.

---

## 🤗 Models on Hugging Face
To enable seamless team collaboration and bypass GitHub storage limits, our fine-tuned models are hosted on Hugging Face:
* **Model Repository:** [vaishnavi1011/legal-case-outcome-predictor](https://huggingface.co/vaishnavi1011/legal-case-outcome-predictor)

The system is configured to automatically pull these weights during the first run.

---

## 🏗️ System Architecture
1.  **Ingestion:** User uploads a court Judgment/Appeal (PDF/TXT).
2.  **Preprocessing:** Dynamic chunking algorithm slices long legal texts (>4000 words) into overlapping 512-token segments.
3.  **Inference:** Text chunks are processed bidirectionally by InLegalBERT.
4.  **Explainability:** SHAP engine calculates the marginal contribution of every token.
5.  **Output:** Streamlit Dashboard renders Jurisdiction, Outcome (with confidence %), and the SHAP Force Plot.

---


2. Create a Virtual Environment (Recommended)
Bash
python -m venv venv
# On Windows:
venv\Scripts\activate  
# On Mac/Linux:
source venv/bin/activate
3. Install Dependencies
Bash
pip install -r requirements.txt
💻 Usage
To launch the Legal AI Engine locally:

Bash
streamlit run app.py
Open http://localhost:8501 in your browser.

Drag and drop a legal PDF (e.g., a Supreme Court Appeal).

Click Analyze Document to receive the prediction.

Click Generate AI Decision Drivers to view the SHAP explainability plot.

📊 Performance Metrics
Model: Fine-tuned InLegalBERT

Validation results from training (3 epochs):

Case type (Civil / Criminal / Constitutional): Accuracy 89.7% | F1-Score 0.895

Case outcome (Allowed / Dismissed): Accuracy 71.6% | F1-Score 0.764

On a separate 120-case benchmark of Supreme Court judgments: case type 76.7% accuracy, outcome 67.5% accuracy.

👨‍💻 Team & Acknowledgments
Developed by (Group F, Project IV): Ankita Kamble, Vaishnavi Bharambe, Shrutika Pagare

Guided by: Dr. Shefali Sonavane

Institution: Department of Information Technology, Walchand College of Engineering, Sangli (Academic year 2026–27)

🔮 Future Scope
BNS Translation: Transitioning from IPC to Bharatiya Nyaya Sanhita (BNS).

Multilingual Support: Integrating Marathi, Hindi, and Tamil.

Granular Predictions: Predicting sentence lengths and settlement amounts.

## 🚀 Installation & Setup

### 1. Clone the Repository
```bash
git clone https://github.com/Bharambevaish/AI-for-Legal-Case.git
cd AI-for-Legal-Case


