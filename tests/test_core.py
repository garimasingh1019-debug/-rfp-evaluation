"""Run with:  python -m unittest discover -s tests -v   (no extra packages needed)"""
import json
import os
import sys
import tempfile
import unittest
from itertools import permutations
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import db  # noqa: E402
import orchestrator  # noqa: E402
from tools import llm_agent, ranking, validation  # noqa: E402

CRIT = [
    {"criterion_id": 1, "name": "Technical", "description": "", "weight": 60, "max_score": 10},
    {"criterion_id": 2, "name": "Price", "description": "", "weight": 40, "max_score": 10},
]


def ev(scores, missing=()):
    return {"status": "ok", "risks": [], "overall_summary": "", "supplier_name": "x",
            "criteria": [{"criterion_id": i + 1, "score": s, "missing": (i + 1) in missing,
                          "adjusted": False, "justification": "j", "evidence": "e"}
                         for i, s in enumerate(scores)]}


def sup(name, scores, date="2026-01-10", exp=5, **kw):
    return {"supplier_name": name, "submission_date": date, "experience_rating": exp,
            "evaluation": ev(scores, **kw)}


class TestFormulas(unittest.TestCase):
    def test_hand_calculated_example(self):
        # A: 8/10 tech, 5/10 price ; B: 6/10 tech, 10/10 price
        ranked, _ = ranking.compute_ranking([sup("A", [8, 5]), sup("B", [6, 10])], CRIT)
        a = next(r for r in ranked if r["supplier_name"] == "A")
        b = next(r for r in ranked if r["supplier_name"] == "B")
        self.assertAlmostEqual(a["absolute_score"], (0.8 * 0.6 + 0.5 * 0.4) * 100)  # 68
        self.assertAlmostEqual(b["absolute_score"], (0.6 * 0.6 + 1.0 * 0.4) * 100)  # 76
        # benchmarks: tech 8, price 10
        self.assertAlmostEqual(a["ppi"], (100 * 0.6) + (50 * 0.4))                   # 80
        self.assertAlmostEqual(b["ppi"], (75 * 0.6) + (100 * 0.4))                   # 85
        d = a["criteria_detail"]
        self.assertEqual((d[0]["gap"], d[1]["gap"]), (0, -5))
        self.assertEqual([r["supplier_name"] for r in ranked], ["B", "A"])
        self.assertEqual([r["rank"] for r in ranked], [1, 2])

    def test_zero_benchmark_is_safe(self):
        ranked, _ = ranking.compute_ranking([sup("A", [0, 5]), sup("B", [0, 5])], CRIT)
        for r in ranked:
            self.assertEqual(r["criteria_detail"][0]["relative_pct"], 100.0)
            self.assertEqual(r["ppi"], 100.0)

    def test_weights_not_100_are_rescaled_with_warning(self):
        crit = [dict(c, weight=c["weight"] / 2) for c in CRIT]  # totals 50
        ranked, info = ranking.compute_ranking([sup("A", [10, 10])], crit)
        self.assertAlmostEqual(ranked[0]["absolute_score"], 100.0)
        self.assertTrue(info["warnings"])

    def test_missing_score_not_used_as_benchmark(self):
        ranked, info = ranking.compute_ranking(
            [sup("A", [0, 5], missing=(1,)), sup("B", [0, 5], missing=(1,))], CRIT)
        self.assertEqual(info["benchmarks"]["1"], 0.0)


class TestTieBreaks(unittest.TestCase):
    def order(self, suppliers):
        ranked, info = ranking.compute_ranking(suppliers, CRIT)
        return [r["supplier_name"] for r in ranked], ranked, info

    def test_each_rule_in_order(self):
        same = [7, 7]
        # rule 2: earlier date beats higher experience
        names, *_ = self.order([sup("Late", same, "2026-02-01", 9), sup("Early", same, "2026-01-01", 1)])
        self.assertEqual(names, ["Early", "Late"])
        # rule 3: same date -> higher experience
        names, *_ = self.order([sup("Low", same, exp=3), sup("High", same, exp=8)])
        self.assertEqual(names, ["High", "Low"])
        # rule 4: everything equal -> name ascending
        names, *_ = self.order([sup("Zeta", same), sup("Alpha", same), sup("Mid", same)])
        self.assertEqual(names, ["Alpha", "Mid", "Zeta"])
        # rule 1 beats all others
        names, *_ = self.order([sup("Early", [5, 5], "2025-01-01", 10), sup("Best", [9, 9], "2026-12-31", 0)])
        self.assertEqual(names, ["Best", "Early"])

    def test_explanation_mentions_deciding_rule(self):
        _, ranked, info = self.order([sup("A", [7, 7], "2026-01-01"), sup("B", [7, 7], "2026-02-01")])
        self.assertIn("earlier submission date", info["tie_break_explanation"][0])
        self.assertTrue(ranked[1]["rank_reason"].startswith("Tie-break"))

    def test_result_independent_of_input_order(self):
        base = [sup("A", [7, 7], "2026-01-01", 5), sup("B", [7, 7], "2026-01-01", 5),
                sup("C", [9, 3], "2026-01-02", 2), sup("D", [4, 9], "2026-01-03", 9)]
        outcomes = {tuple((r["supplier_name"], r["rank"], r["ppi"]) for r in
                          ranking.compute_ranking(list(p), CRIT)[0]) for p in permutations(base)}
        self.assertEqual(len(outcomes), 1)

    def test_invalid_date_goes_last_in_tie(self):
        names, *_ = self.order([sup("Bad", [7, 7], "not-a-date", 9), sup("Ok", [7, 7], "2026-01-01", 1)])
        self.assertEqual(names, ["Ok", "Bad"])


class TestValidation(unittest.TestCase):
    def good(self):
        return {"supplier_name": "S", "criteria": [
            {"criterion_id": 1, "score": 8, "max_score": 10, "justification": "j", "evidence": "e"},
            {"criterion_id": 2, "score": 6, "max_score": 10, "justification": "j", "evidence": "e"}],
            "risks": ["r"], "overall_summary": "ok"}

    def test_valid_passes_clean(self):
        out, w = validation.validate_evaluation(json.dumps(self.good()), CRIT, "S")
        self.assertEqual(w, [])
        self.assertEqual(out["status"], "ok")
        self.assertEqual([c["score"] for c in out["criteria"]], [8, 6])

    def test_markdown_fences_and_prose_are_tolerated(self):
        raw = "Sure!\n```json\n" + json.dumps(self.good()) + "\n```"
        out, w = validation.validate_evaluation(raw, CRIT, "S")
        self.assertEqual(out["status"], "ok")

    def test_out_of_range_is_clipped_with_warning(self):
        d = self.good()
        d["criteria"][0]["score"] = 15
        d["criteria"][1]["score"] = -3
        out, w = validation.validate_evaluation(d, CRIT, "S")
        self.assertEqual([c["score"] for c in out["criteria"]], [10, 0])
        self.assertEqual(len([x for x in w if "clipped" in x]), 2)

    def test_missing_criterion_defaults_to_zero_and_flags(self):
        d = self.good()
        d["criteria"].pop()
        out, w = validation.validate_evaluation(d, CRIT, "S")
        self.assertTrue(out["criteria"][1]["missing"])
        self.assertEqual(out["status"], "partial")

    def test_bad_score_types(self):
        d = self.good()
        d["criteria"][0]["score"] = "7/10"
        d["criteria"][1]["score"] = "excellent"
        out, _ = validation.validate_evaluation(d, CRIT, "S")
        self.assertEqual(out["criteria"][0]["score"], 7.0)
        self.assertTrue(out["criteria"][1]["missing"])
        for bad in (True, None, float("nan"), [8]):
            d["criteria"][0]["score"] = bad
            o, _ = validation.validate_evaluation(d, CRIT, "S")
            self.assertTrue(o["criteria"][0]["missing"], bad)

    def test_unknown_and_duplicate_ids_ignored(self):
        d = self.good()
        d["criteria"] += [{"criterion_id": 99, "score": 10}, {"criterion_id": 1, "score": 1}]
        out, w = validation.validate_evaluation(d, CRIT, "S")
        self.assertEqual(out["criteria"][0]["score"], 8)
        self.assertEqual(len(out["criteria"]), 2)

    def test_garbage_output_gives_all_zero_failed(self):
        for raw in ("I cannot do that", "", None, "[1,2,3]", "{broken"):
            out, w = validation.validate_evaluation(raw, CRIT, "S")
            self.assertEqual(out["status"], "failed")
            self.assertTrue(all(c["score"] == 0 and c["missing"] for c in out["criteria"]))
            self.assertTrue(w)

    def test_db_max_score_wins_over_model_claim(self):
        d = self.good()
        d["criteria"][0]["max_score"] = 100
        out, w = validation.validate_evaluation(d, CRIT, "S")
        self.assertEqual(out["criteria"][0]["max_score"], 10)
        self.assertTrue(any("max_score" in x for x in w))


class FlakyLLM:
    mode = "test"
    model = "flaky"

    def __init__(self, outputs):
        self.outputs, self.calls = list(outputs), 0

    def complete(self, system, user):
        self.calls += 1
        out = self.outputs.pop(0)
        if isinstance(out, Exception):
            raise out
        return out


class TestPipeline(unittest.TestCase):
    def setUp(self):
        self.db = os.path.join(tempfile.mkdtemp(), "t.db")
        db.init_db(self.db)
        self.pdfs = {p.name: p.read_bytes() for p in (ROOT / "sample_pdfs").glob("*.pdf")}
        self.assertGreaterEqual(len(self.pdfs), 4)

    def rows(self):
        meta = {"Apex": ("2026-03-02", 8), "BrightPath": ("2026-03-05", 4),
                "NexaWorks": ("2026-03-04", 7), "Orbit": ("2026-03-01", 9)}
        out = []
        for fname, data in sorted(self.pdfs.items()):
            key = next(k for k in meta if fname.startswith(k))
            out.append({"name": key, "submission_date": meta[key][0], "experience_rating": meta[key][1],
                        "filename": fname, "pdf_bytes": data})
        return out

    def test_end_to_end_is_deterministic_and_persisted(self):
        a = orchestrator.run_evaluation(self.rows(), llm_agent.MockLLM(), self.db)
        b = orchestrator.run_evaluation(self.rows(), llm_agent.MockLLM(), self.db)
        self.assertEqual(a["leaderboard"], b["leaderboard"])
        self.assertNotEqual(a["rfp_run_id"], b["rfp_run_id"])
        loaded = db.load_run(a["rfp_run_id"], self.db)
        self.assertEqual(loaded["leaderboard"], a["leaderboard"])
        with db.connect(self.db) as c:
            n = c.execute("SELECT COUNT(*) FROM supplier_results WHERE rfp_run_id=?",
                          (a["rfp_run_id"],)).fetchone()[0]
        self.assertEqual(n, 4)

    def test_uses_latest_active_criteria(self):
        rows = db.get_criteria(self.db, active_only=False)
        rows[-1]["is_active"] = 0
        db.update_criteria(rows, self.db)
        res = orchestrator.run_evaluation(self.rows(), llm_agent.MockLLM(), self.db)
        self.assertEqual(len(res["criteria"]), 4)
        self.assertTrue(any("rescaled" in w for w in res["warnings"]))  # 90% total -> rescaled

    def test_llm_failure_and_garbage_are_handled(self):
        rows = self.rows()[:2]
        llm = FlakyLLM([RuntimeError("boom"), RuntimeError("boom"), "not json at all"])
        res = orchestrator.run_evaluation(rows, llm, self.db)
        self.assertEqual(res["status"], "completed_with_warnings")
        self.assertEqual(llm.calls, 3)  # first supplier: 1 try + 1 retry; second: 1
        self.assertTrue(all(s["absolute_score"] == 0 for s in res["suppliers"]))
        self.assertEqual([s["rank"] for s in res["suppliers"]], [1, 2])

    def test_input_validation_errors(self):
        good = self.rows()[0]
        bad_cases = [
            [],
            [dict(good, name="")],
            [dict(good), dict(good, name=good["name"].upper())],
            [dict(good, submission_date="31/31/2026")],
            [dict(good, experience_rating=11)],
            [dict(good, pdf_bytes=b"hello this is not a pdf")],
            [dict(good, pdf_bytes=b"")],
        ]
        for case in bad_cases:
            errors, _ = orchestrator.validate_inputs(case)
            self.assertTrue(errors, case)
            with self.assertRaises(ValueError):
                orchestrator.run_evaluation(case, llm_agent.MockLLM(), self.db)

    def test_no_active_criteria(self):
        rows = db.get_criteria(self.db, active_only=False)
        for r in rows:
            r["is_active"] = 0
        db.update_criteria(rows, self.db)
        with self.assertRaises(ValueError):
            orchestrator.run_evaluation(self.rows()[:1], llm_agent.MockLLM(), self.db)


if __name__ == "__main__":
    unittest.main()
