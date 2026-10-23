"""Ranking Tool: ALL arithmetic, benchmarking, tie-breaks and ranks. Deterministic Python only.

Formulas
  weight fraction      w_i = weight_i / sum(active weights)           (so weights always sum to 1)
  absolute score       sum( score_i / max_i * w_i ) * 100             (0-100)
  benchmark_i          highest VALID score for criterion i across all suppliers
                       (a defaulted 'missing' score is not a valid observation)
  gap_i                score_i - benchmark_i                          (0 for the leader, else negative)
  relative %_i         score_i / benchmark_i * 100
                       if benchmark_i == 0 -> 100  (nobody scored; nobody is behind anyone)
  PPI                  sum(relative %_i * w_i)                        (weighted average, 0-100)

Tie-break order (applied by one stable sort, ranks assigned afterwards)
  1. higher PPI   2. earlier submission date   3. higher experience rating   4. supplier name A-Z
"""
from datetime import date, datetime

PPI_PRECISION = 6  # PPIs equal to 6 decimals are treated as tied (removes float noise)


def parse_date(value):
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    return date.fromisoformat(str(value))


def weight_fractions(criteria):
    total = sum(float(c["weight"]) for c in criteria)
    warnings = []
    if total <= 0:
        raise ValueError("Active criteria weights must total more than 0.")
    if abs(total - 100.0) > 1e-6:
        warnings.append(f"Active criteria weights total {total:g}%, not 100%; "
                        "weights were rescaled proportionally.")
    return {c["criterion_id"]: float(c["weight"]) / total for c in criteria}, warnings


def absolute_score(scores, criteria, fractions):
    return sum(scores[c["criterion_id"]] / float(c["max_score"]) * fractions[c["criterion_id"]]
               for c in criteria) * 100.0


def relative_pct(score, benchmark):
    return 100.0 if benchmark <= 0 else score / benchmark * 100.0


def compute_ranking(suppliers, criteria):
    """
    suppliers: list of dicts with supplier_name, submission_date, experience_rating,
               evaluation (validated scorecard from validation.validate_evaluation)
    Returns (ranked_suppliers, info) where info has warnings + tie_break_explanation.
    """
    warnings = []
    fractions, w = weight_fractions(criteria)
    warnings += w

    # 1) per-supplier score maps and the benchmark per criterion
    rows = []
    for s in suppliers:
        ev = s["evaluation"]
        entries = {e["criterion_id"]: e for e in ev["criteria"]}
        try:
            sub_date = parse_date(s["submission_date"])
        except ValueError:
            sub_date = date.max
            warnings.append(f"{s['supplier_name']}: invalid submission date "
                            f"'{s['submission_date']}'; treated as latest possible.")
        rows.append({"src": s, "entries": entries, "date": sub_date})

    benchmark = {}
    for c in criteria:
        valid = [r["entries"][c["criterion_id"]]["score"] for r in rows
                 if not r["entries"][c["criterion_id"]]["missing"]]
        benchmark[c["criterion_id"]] = max(valid) if valid else 0.0

    # 2) per-supplier metrics
    results = []
    for r in rows:
        s, entries = r["src"], r["entries"]
        scores = {cid: e["score"] for cid, e in entries.items()}
        detail, ppi = [], 0.0
        for c in criteria:
            cid = c["criterion_id"]
            e = entries[cid]
            bench = benchmark[cid]
            rel = relative_pct(e["score"], bench)
            ppi += rel * fractions[cid]
            detail.append({
                "criterion_id": cid, "criterion": c["name"],
                "weight": float(c["weight"]), "weight_fraction": round(fractions[cid], 6),
                "max_score": float(c["max_score"]), "score": e["score"],
                "benchmark": bench, "gap": round(e["score"] - bench, 6),
                "relative_pct": round(rel, 4),
                "weighted_points": round(e["score"] / float(c["max_score"]) * fractions[cid] * 100, 4),
                "justification": e["justification"], "evidence": e["evidence"],
                "flag": "missing/invalid" if e["missing"] else ("clipped" if e["adjusted"] else ""),
            })
        results.append({
            "supplier_name": s["supplier_name"],
            "submission_date": str(s["submission_date"]),
            "experience_rating": s["experience_rating"],
            "source_file": s.get("source_file", ""),
            "absolute_score": round(absolute_score(scores, criteria, fractions), 4),
            "ppi": round(ppi, 4),
            "_ppi_key": round(ppi, PPI_PRECISION),
            "_date": r["date"],
            "criteria_detail": detail,
            "risks": s["evaluation"]["risks"],
            "overall_summary": s["evaluation"]["overall_summary"],
            "evaluation_status": s["evaluation"]["status"],
            "warnings": s.get("warnings", []),
        })

    # 3) one stable sort with the mandatory tie-break order
    results.sort(key=lambda x: (-x["_ppi_key"], x["_date"], -float(x["experience_rating"]),
                                x["supplier_name"].casefold(), x["supplier_name"]))
    explanation = []
    for i, cur in enumerate(results):
        cur["rank"] = i + 1
        if i == 0:
            cur["rank_reason"] = "Highest PPI."
            continue
        prev = results[i - 1]
        if prev["_ppi_key"] != cur["_ppi_key"]:
            cur["rank_reason"] = (f"Lower PPI than rank {i} ({cur['ppi']:.2f} vs {prev['ppi']:.2f}).")
            continue
        pair = f"{prev['supplier_name']} (rank {i}) vs {cur['supplier_name']} (rank {i + 1})"
        if prev["_date"] != cur["_date"]:
            why = (f"tied on PPI ({cur['ppi']:.2f}); earlier submission date wins "
                   f"({prev['submission_date']} before {cur['submission_date']})")
        elif float(prev["experience_rating"]) != float(cur["experience_rating"]):
            why = (f"tied on PPI and submission date; higher experience rating wins "
                   f"({prev['experience_rating']} vs {cur['experience_rating']})")
        else:
            why = "tied on PPI, date and experience; supplier name A-Z decides"
        cur["rank_reason"] = "Tie-break: " + why + "."
        explanation.append(f"{pair}: {why}.")
    for r in results:
        r.pop("_ppi_key"), r.pop("_date")
    if not explanation:
        explanation.append("No ties on PPI; the ranking was decided by PPI alone.")

    info = {"warnings": warnings, "tie_break_explanation": explanation,
            "benchmarks": {str(k): v for k, v in benchmark.items()}}
    return results, info
