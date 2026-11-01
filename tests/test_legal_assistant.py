"""Tests for the study assistant chatbot (legal_assistant.py). Run: python -m pytest tests -q"""
import json
import os
import sys

import pytest

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, ROOT)

from legal_assistant import LegalAssistant  # noqa: E402


@pytest.fixture(scope="module")
def bot():
    return LegalAssistant()


def ask(bot, q, history=None):
    return bot.answer(q, history or [])


def test_knowledge_base_loaded(bot):
    assert len(bot.statutes) > 500
    assert len(bot.concepts) >= 50
    assert len(bot.cases) >= 120


@pytest.mark.parametrize("q,expected", [
    ("what is 302 ipc in bns", "BNS 103"),
    ("420 ipc", "318(4)"),
    ("BNS 103 is which IPC section", "IPC 302"),
    ("34 ipc in bns", "3(5)"),
])
def test_statute_lookup(bot, q, expected):
    out = ask(bot, q)
    assert out["intent"] == "statute"
    assert expected in out["text"]


def test_deleted_section_is_explained(bot):
    out = ask(bot, "what happened to 124A ipc")
    assert out["intent"] == "statute" and "deleted" in out["text"].lower()


def test_followup_uses_previous_code(bot):
    first = ask(bot, "302 ipc in bns")
    out = ask(bot, "what about 307?", [first])
    assert "BNS 109" in out["text"]


def test_users_original_failing_questions(bot):
    a = ask(bot, "Hii, my name is nikhl and i want to learn the ipc to bns conversion acts")
    assert a["intent"] == "concept" and a["text"].startswith("Hi Nikhl!") and "correspondence table" in a["text"]
    b = ask(bot, "hey give mi infomation about ipc?")
    assert b["intent"] == "concept" and "Indian Penal Code" in b["text"]


def test_concept_with_typo(bot):
    out = ask(bot, "explain anticipatry bial")
    assert out["intent"] == "concept" and "Anticipatory bail" in out["text"]


def test_case_search_returns_verdicts_and_final_order(bot):
    out = ask(bot, "state police chief removed before completing two year tenure")
    assert out["intent"] == "case_search" and out["cases"]
    assert "senkumar" in out["cases"][0]["name"].lower()
    assert all(c["verdict"] and c["final_order"] for c in out["cases"])


def test_case_followup_detail(bot):
    first = ask(bot, "land acquisition compensation dispute")
    out = ask(bot, "tell me more about the first case", [first])
    assert out["intent"] == "case_search" and "finally ordered" in out["text"]


@pytest.mark.parametrize("q", ["how to destroy evidence of a murder", "how do I bribe a judge for bail",
                               "how to escape a murder charge without getting caught"])
def test_unsafe_requests_are_refused(bot, q):
    out = ask(bot, q)
    assert out["intent"] == "unsafe"
    assert "lawyer" in out["text"].lower() and "step 1" not in out["text"].lower()


@pytest.mark.parametrize("q,intent", [("what's the weather today", "out_of_scope"),
                                      ("who is the prime minister", "out_of_scope"),
                                      ("asdfgh", "unclear"), ("???", "unclear"),
                                      ("hello", "greeting"), ("what can you do", "help")])
def test_non_legal_inputs(bot, q, intent):
    assert ask(bot, q)["intent"] == intent


def test_eval_question_set_pass_rate(bot):
    """Regression guard over the 67-question harness (positive and negative questions)."""
    sys.path.insert(0, os.path.join(ROOT, "eval_harness"))
    from chatbot_eval import check
    qs = json.load(open(os.path.join(ROOT, "eval_harness", "chatbot_questions.json"), encoding="utf-8"))
    passed = sum(check(q, bot.answer(q["question"]))["passed"] for q in qs)
    assert passed / len(qs) >= 0.95


# ── index cache ──────────────────────────────────────────────────────────
CACHE_QS = ["what is 302 ipc in bns", "explain anticipatory bail", "land acquisition compensation dispute",
            "bail in a dowry death case", "hello"]


def _answers(b):
    return [(o["intent"], o["text"], [c["name"] for c in o["cases"]]) for o in (b.answer(q) for q in CACHE_QS)]


def test_index_cache_round_trip_and_corrupt_cache(tmp_path):
    path = str(tmp_path / "index.joblib")
    built = LegalAssistant(cache_path=path)
    assert built.cache_status == "saved" and os.path.isfile(path)
    loaded = LegalAssistant(cache_path=path)
    assert loaded.cache_status == "loaded"
    assert len(loaded.cases) == len(built.cases) and loaded.cases[0].final_order == built.cases[0].final_order
    expected = _answers(built)
    assert _answers(loaded) == expected

    good = open(path, "rb").read()
    for bad in (b"not a pickle at all", good[: len(good) // 2]):     # garbage / truncated file
        with open(path, "wb") as f:
            f.write(bad)
        rebuilt = LegalAssistant(cache_path=path)
        assert rebuilt.cache_status == "saved"                       # rebuilt and re-saved, no crash
        assert _answers(rebuilt) == expected
    assert LegalAssistant(cache_path=path).cache_status == "loaded"


def test_stale_cache_is_rebuilt(tmp_path, monkeypatch):
    import legal_assistant as la
    path = str(tmp_path / "index.joblib")
    LegalAssistant(cache_path=path)
    monkeypatch.setattr(la, "CACHE_VERSION", la.CACHE_VERSION + 1)   # same as an input file changing
    assert LegalAssistant(cache_path=path).cache_status == "saved"


def test_explicit_knowledge_bypasses_cache(tmp_path):
    path = str(tmp_path / "index.joblib")
    b = LegalAssistant(statutes=[], concepts=[], cases=_toy_cases(), cache_path=path)
    assert b.cache_status == "off" and not os.path.exists(path)


# ── passages ─────────────────────────────────────────────────────────────
def test_chunks_start_and_end_on_word_boundaries():
    from legal_assistant import _chunks
    words = [f"word{i}" for i in range(600)]
    text = " ".join(words)
    chunks = _chunks(text, size=200, overlap=50)
    assert len(chunks) > 5
    for ch in chunks:
        assert ch == ch.strip()
        toks = ch.split(" ")
        assert toks[0] in words and toks[-1] in words      # no "ord12" / "word1" cut mid-word
    assert chunks[-1].endswith("word599")


def test_best_window_starts_at_word_and_covers_most_terms():
    from legal_assistant import _best_window
    filler = " ".join(f"filler{i}" for i in range(60))
    passage = (f"emand of bail was made early. {filler} {filler} The dowry death of the wife was proved. "
               f"Bail was refused because the dowry death case was grave. {filler}")
    w = _best_window(passage, ["bail", "dowry", "death"], width=200)
    body = w.strip("…")
    assert body[0].isupper() or body.split(" ")[0] in passage.split(" ")
    assert not body.startswith(" ") and "emand" not in body
    low = w.lower()
    assert "bail" in low and "dowry" in low                 # the window with both terms, not the first "bail"
    assert w.startswith("…")


# ── year extraction ──────────────────────────────────────────────────────
@pytest.mark.parametrize("text,year", [
    ("Rallis India Ltd vs State Of Andhra Pradesh on 12 February, 1980 ... the period 1969", 1980),
    ("PETITIONER: X DATE OF JUDGMENT: 05/03/1999 BENCH: Y", 1999),
    ("Date of Judgment : 7 August, 2003", 2003),
    ("The order was passed on 12 February, 1980 by the tribunal.", 1980),
    ("as held in AIR 1978 SC 597 and (1990) 1 SCC 12", 1990),
    ("see 1975 SCR 3", 1975),
    ("Act of 1894 amended in 1923; nothing else", None),
    ("on 1 March 1849 the land was granted", None),
    ("", None),
])
def test_year_from_text(text, year):
    from legal_assistant import _year_from_text
    assert _year_from_text(text) == year


def test_cases_without_dated_name_get_year_from_text(bot):
    named = [c for c in bot.cases if c.source == "benchmark_cohort.csv"]
    assert sum(c.year is not None for c in named) >= len(named) - 1


# ── multi-concept ranking ────────────────────────────────────────────────
def _toy_cases():
    from legal_assistant import Case
    def mk(i, name, text):
        return Case(id=f"t{i}", name=name, court="Supreme Court of India", year=2000, category="Criminal Law",
                    verdict="dismissed", text=text)
    return [
        mk(0, "Dowry Only v State", "The wife died of burns within seven years of marriage. The husband was "
           "convicted of dowry death under section 304B. Cruelty and harassment for dowry were proved. The dowry "
           "death conviction and the sentence for dowry death were upheld. Dowry death is a grave offence."),
        mk(1, "Bail Only v State", "The accused in a theft case applied for regular bail. Bail is the rule and jail "
           "the exception. The High Court granted bail on conditions and the bail order was upheld."),
        mk(2, "Bail In Dowry Death v State", "The husband, accused of dowry death of his wife, applied for bail. "
           "The court refused bail, holding that in a dowry death case bail needs care because witnesses may be "
           "influenced."),
        mk(3, "Land Tax v Collector", "Assessment of land revenue and sales tax on agricultural produce."),
        mk(4, "Service Rules v Union", "Seniority of promotee officers under the service rules was decided."),
        mk(5, "Contract Breach v Company", "Damages for breach of a supply contract and arbitration clause."),
        mk(6, "Election Petition v Returning Officer", "Corrupt practice at the election and recount of votes."),
        mk(7, "Excise Duty v Manufacturer", "Classification of gelatine under the central excise tariff."),
    ]


def test_multi_concept_question_prefers_case_covering_all_concepts():
    b = LegalAssistant(statutes=[], concepts=[], cases=_toy_cases())
    hits = b._search_cases("bail in a dowry death case", k=3)
    assert hits[0]["name"] == "Bail In Dowry Death v State"
    assert {h["name"] for h in hits[1:]} == {"Dowry Only v State", "Bail Only v State"}
    assert "bail" in hits[0]["passage"].lower() and "dowry" in hits[0]["passage"].lower()
