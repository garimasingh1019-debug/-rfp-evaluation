"""Validation Tool: turn raw (possibly broken) LLM output into a safe, normalized scorecard.

Rules (all recorded as warnings, never silently):
  * JSON may be wrapped in ```fences``` or surrounded by prose -> extract it.
  * Every active criterion gets exactly one result. Missing -> score 0, flagged `missing`.
  * Scores must be numeric (also accepts "8", "8/10"); otherwise -> 0, flagged.
  * Scores are clipped into [0, max_score]. max_score is ALWAYS taken from the database.
  * Unknown / duplicate criterion ids are ignored.
"""
import json
import math
import re

MAX_TEXT = 800


def parse_json_loose(raw):
    if isinstance(raw, dict):
        return raw
    if not isinstance(raw, str):
        return None
    text = raw.strip()
    text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text, flags=re.IGNORECASE)
    try:
        data = json.loads(text)
        return data if isinstance(data, dict) else None
    except json.JSONDecodeError:
        pass
    start, end = text.find("{"), text.rfind("}")
    if start != -1 and end > start:
        try:
            data = json.loads(text[start:end + 1])
            return data if isinstance(data, dict) else None
        except json.JSONDecodeError:
            return None
    return None


def _to_score(value):
    """Return float or None if not a usable number."""
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, (int, float)):
        num = float(value)
    elif isinstance(value, str):
        m = re.match(r"^\s*(-?\d+(?:\.\d+)?)\s*(?:/\s*\d+(?:\.\d+)?)?\s*$", value)
        if not m:
            return None
        num = float(m.group(1))
    else:
        return None
    return num if math.isfinite(num) else None


def _to_id(value):
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return None


def _text(value):
    if value is None:
        return ""
    if isinstance(value, (list, tuple)):
        value = "; ".join(str(v) for v in value)
    return str(value).strip()[:MAX_TEXT]


def validate_evaluation(raw, criteria, supplier_name):
    """Return (normalized_evaluation, warnings)."""
    warnings = []
    data = parse_json_loose(raw)
    status = "ok"
    if data is None:
        warnings.append(f"{supplier_name}: LLM output was not valid JSON; all criteria scored 0.")
        data = {}
        status = "failed"

    items = data.get("criteria")
    if not isinstance(items, list):
        if status != "failed":
            warnings.append(f"{supplier_name}: 'criteria' list missing or malformed.")
        items = []

    by_id, by_name = {}, {}
    for item in items:
        if not isinstance(item, dict):
            warnings.append(f"{supplier_name}: ignored a non-object entry in 'criteria'.")
            continue
        cid = _to_id(item.get("criterion_id"))
        if cid is not None:
            if cid in by_id:
                warnings.append(f"{supplier_name}: duplicate result for criterion {cid} ignored.")
            else:
                by_id[cid] = item
        nm = str(item.get("name", "")).strip().lower()
        if nm:
            by_name.setdefault(nm, item)

    valid_ids = {c["criterion_id"] for c in criteria}
    for cid in by_id:
        if cid not in valid_ids:
            warnings.append(f"{supplier_name}: unknown criterion_id {cid} ignored.")

    out = []
    for c in criteria:
        item = by_id.get(c["criterion_id"]) or by_name.get(c["name"].lower())
        entry = {"criterion_id": c["criterion_id"], "name": c["name"], "max_score": c["max_score"],
                 "score": 0.0, "justification": "", "evidence": "", "missing": False,
                 "adjusted": False}
        if item is None:
            entry["missing"] = True
            entry["justification"] = "No result returned by the model for this criterion."
            if status != "failed":
                warnings.append(f"{supplier_name}: no result for '{c['name']}'; scored 0.")
        else:
            score = _to_score(item.get("score"))
            if score is None:
                entry["missing"] = True
                entry["justification"] = "Model returned a non-numeric score."
                warnings.append(f"{supplier_name}: invalid score for '{c['name']}'; scored 0.")
            else:
                clipped = min(max(score, 0.0), float(c["max_score"]))
                if clipped != score:
                    entry["adjusted"] = True
                    warnings.append(f"{supplier_name}: score {score:g} for '{c['name']}' clipped "
                                    f"to {clipped:g} (allowed 0-{c['max_score']:g}).")
                entry["score"] = clipped
                entry["justification"] = _text(item.get("justification"))
                entry["evidence"] = _text(item.get("evidence"))
                if not entry["evidence"]:
                    warnings.append(f"{supplier_name}: no evidence quoted for '{c['name']}'.")
                reported_max = _to_score(item.get("max_score"))
                if reported_max is not None and reported_max != float(c["max_score"]):
                    warnings.append(f"{supplier_name}: model reported max_score {reported_max:g} for "
                                    f"'{c['name']}', database value {c['max_score']:g} used.")
        out.append(entry)

    if status != "failed" and any(e["missing"] for e in out):
        status = "partial"

    risks = data.get("risks")
    risks = [_text(r) for r in risks if _text(r)] if isinstance(risks, list) else []
    evaluation = {"supplier_name": supplier_name, "criteria": out, "risks": risks,
                  "overall_summary": _text(data.get("overall_summary")), "status": status}
    return evaluation, warnings
