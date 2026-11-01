"""Chatbot evaluation harness for the Legal AI Hub study assistant.

Runs every question in eval_harness/chatbot_questions.json through
legal_assistant.LegalAssistant and checks:
  * intent      - the bot routed the question correctly
  * content     - every `must_include` string is in the answer, no `must_not_include` string is
  * case        - for case_search questions with `expected_case`, that case is in the top 3

Run from the project root:   python eval_harness/chatbot_eval.py [--verbose]
Writes eval_harness/results/chatbot_eval_results.json
"""
import json
import os
import sys
import time
from collections import Counter, defaultdict

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, ROOT)

from legal_assistant import LegalAssistant  # noqa: E402

QUESTIONS = os.path.join(ROOT, "eval_harness", "chatbot_questions.json")
OUT = os.path.join(ROOT, "eval_harness", "results", "chatbot_eval_results.json")

# Questions that legitimately start with a greeting may be answered as the substantive intent.
EQUIVALENT = {("concept", "greeting"), ("greeting", "concept")}


def check(q, out):
    text = out["text"].lower()
    intent_ok = out["intent"] == q["expected_intent"] or (q["expected_intent"], out["intent"]) in EQUIVALENT
    missing = [s for s in q.get("must_include", []) if s.lower() not in text]
    forbidden = [s for s in q.get("must_not_include", []) if s.lower() in text]
    case_ok = None
    if q.get("expected_case"):
        names = [c["name"].lower() for c in out.get("cases", [])][:3]
        case_ok = any(q["expected_case"].lower() in n for n in names)
    passed = intent_ok and not missing and not forbidden and case_ok is not False
    return {"id": q["id"], "question": q["question"], "expected_intent": q["expected_intent"],
            "intent": out["intent"], "intent_ok": intent_ok, "missing": missing, "forbidden": forbidden,
            "expected_case": q.get("expected_case"), "case_ok": case_ok,
            "top_cases": [c["name"] for c in out.get("cases", [])][:3], "passed": passed}


def main(verbose=False):
    qs = json.load(open(QUESTIONS, encoding="utf-8"))
    t0 = time.time()
    bot = LegalAssistant()
    load_s = time.time() - t0
    rows, times = [], []
    for q in qs:
        t = time.time()
        out = bot.answer(q["question"])
        times.append(time.time() - t)
        rows.append(check(q, out))

    by_intent = defaultdict(lambda: [0, 0])
    for r in rows:
        by_intent[r["expected_intent"]][0] += r["passed"]
        by_intent[r["expected_intent"]][1] += 1
    case_rows = [r for r in rows if r["case_ok"] is not None]
    summary = {
        "questions": len(rows),
        "passed": sum(r["passed"] for r in rows),
        "pass_rate": round(100 * sum(r["passed"] for r in rows) / len(rows), 1),
        "intent_accuracy": round(100 * sum(r["intent_ok"] for r in rows) / len(rows), 1),
        "case_hit_at_3": round(100 * sum(r["case_ok"] for r in case_rows) / max(1, len(case_rows)), 1),
        "by_intent": {k: f"{v[0]}/{v[1]}" for k, v in sorted(by_intent.items())},
        "load_seconds": round(load_s, 1),
        "avg_answer_ms": round(1000 * sum(times) / len(times), 1),
        "corpus": {"statutes": len(bot.statutes), "concepts": len(bot.concepts), "cases": len(bot.cases)},
    }
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    json.dump({"summary": summary, "results": rows}, open(OUT, "w", encoding="utf-8"), indent=1, ensure_ascii=False)

    print("=" * 70)
    print(" LEGAL AI HUB - CHATBOT EVALUATION")
    print("=" * 70)
    for k, v in summary.items():
        print(f" {k:16}: {v}")
    fails = [r for r in rows if not r["passed"]]
    if fails:
        print("-" * 70)
        print(f" {len(fails)} failing question(s):")
        for r in fails:
            why = []
            if not r["intent_ok"]:
                why.append(f"intent {r['intent']} (expected {r['expected_intent']})")
            if r["missing"]:
                why.append(f"missing {r['missing']}")
            if r["forbidden"]:
                why.append(f"contains {r['forbidden']}")
            if r["case_ok"] is False:
                why.append(f"expected case '{r['expected_case']}' not in {r['top_cases']}")
            print(f"  {r['id']:5} {r['question'][:60]!r}: " + "; ".join(why))
    print(f"\nSaved {OUT}")
    return summary


if __name__ == "__main__":
    main(verbose="--verbose" in sys.argv)
