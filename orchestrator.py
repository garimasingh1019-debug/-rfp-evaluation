"""Orchestrator Agent: runs the workflow, calling each tool in order.

  load criteria -> create run -> [for each supplier: extract PDF -> LLM -> validate]
  -> rank (deterministic) -> persist -> return full result
"""
import math
from datetime import datetime, timezone

import db
from tools import llm_agent, pdf_tool, ranking, validation

FORMULAS = {
    "absolute_score": "sum(score / max_score x weight_fraction) x 100",
    "benchmark": "highest valid score for the criterion across all suppliers",
    "gap": "score - benchmark (0 for the leader, otherwise negative)",
    "relative_pct": "score / benchmark x 100 (100 when benchmark is 0)",
    "ppi": "weighted average of criterion relative percentages",
    "tie_break": "higher PPI > earlier submission date > higher experience rating > name A-Z",
}


def validate_inputs(rows):
    """rows: list of dicts(name, submission_date, experience_rating, filename, pdf_bytes).
    Returns (errors, warnings) as lists of messages."""
    errors, warnings = [], []
    if not rows:
        errors.append("Upload at least one supplier PDF.")
    if len(rows) == 1:
        warnings.append("Only one supplier: benchmarks and ranking are trivial. Add more to compare.")
    seen = set()
    for i, r in enumerate(rows, 1):
        label = r.get("filename") or f"row {i}"
        name = str(r.get("name", "")).strip()
        if not name:
            errors.append(f"{label}: supplier name is required.")
        elif name.casefold() in seen:
            errors.append(f"{label}: duplicate supplier name '{name}'.")
        seen.add(name.casefold())
        try:
            ranking.parse_date(r.get("submission_date"))
        except (ValueError, TypeError):
            errors.append(f"{label}: submission date must be a valid date (YYYY-MM-DD).")
        try:
            rating = float(r.get("experience_rating"))
            if not math.isfinite(rating) or not 0 <= rating <= 10:
                raise ValueError
        except (ValueError, TypeError):
            errors.append(f"{label}: experience rating must be a number from 0 to 10.")
        data = r.get("pdf_bytes") or b""
        if not data:
            errors.append(f"{label}: file is empty.")
        elif not data.lstrip()[:5].startswith(b"%PDF"):
            errors.append(f"{label}: not a valid PDF file.")
    return errors, warnings


def run_evaluation(rows, llm, db_path=None, progress=None):
    """Execute the full workflow and return the complete result payload."""
    errors, input_warnings = validate_inputs(rows)
    if errors:
        raise ValueError("; ".join(errors))

    def say(msg):
        if progress:
            progress(msg)

    criteria = db.get_criteria(db_path, active_only=True)  # always the LATEST active criteria
    if not criteria:
        raise ValueError("No active evaluation criteria. Activate at least one criterion.")
    run_id, created_at = db.create_run(db_path)
    warnings = list(input_warnings)
    try:
        evaluated = []
        for r in rows:
            name = r["name"].strip()
            sw = []
            say(f"Reading {r['filename']} ...")
            text, w = pdf_tool.extract_text(r["pdf_bytes"])
            sw += [f"{name}: {m}" for m in w]
            if len(text) > llm_agent.MAX_DOC_CHARS:
                sw.append(f"{name}: document truncated to {llm_agent.MAX_DOC_CHARS} characters.")
            if not text:
                raw = None
            else:
                say(f"Evaluating {name} ...")
                try:
                    raw = llm_agent.evaluate_supplier(llm, name, criteria, text)
                except llm_agent.LLMError as exc:
                    raw = None
                    sw.append(f"{name}: {exc}")
            evaluation, vw = validation.validate_evaluation(raw, criteria, name)
            sw += vw
            warnings += sw
            evaluated.append({
                "supplier_name": name, "submission_date": str(ranking.parse_date(r["submission_date"])),
                "experience_rating": float(r["experience_rating"]), "source_file": r["filename"],
                "evaluation": evaluation, "warnings": sw})

        say("Scoring, benchmarking and ranking ...")
        ranked, info = ranking.compute_ranking(evaluated, criteria)
        warnings += info["warnings"]
        any_failed = any(s["evaluation_status"] != "ok" for s in ranked)
        payload = {
            "rfp_run_id": run_id, "created_at": created_at,
            "status": "completed_with_warnings" if (warnings or any_failed) else "completed",
            "llm": {"mode": getattr(llm, "mode", "custom"), "model": getattr(llm, "model", "")},
            "criteria": [{"criterion_id": c["criterion_id"], "name": c["name"],
                          "description": c["description"], "weight": c["weight"],
                          "max_score": c["max_score"]} for c in criteria],
            "formulas": FORMULAS, "benchmarks": info["benchmarks"],
            "tie_break_explanation": info["tie_break_explanation"],
            "warnings": warnings, "suppliers": ranked,
            "leaderboard": [{"rank": s["rank"], "supplier_name": s["supplier_name"],
                             "absolute_score": s["absolute_score"], "ppi": s["ppi"],
                             "submission_date": s["submission_date"],
                             "experience_rating": s["experience_rating"]} for s in ranked],
        }
        say("Saving results ...")
        db.save_run(payload, db_path)
        return payload
    except Exception as exc:
        db.mark_run_failed(run_id, str(exc), db_path)
        raise
