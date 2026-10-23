# Agentic RFP Evaluation and Supplier Ranking

An AI-assisted Streamlit app that reads supplier RFP proposals (PDF), scores them against
configurable criteria, benchmarks suppliers against their peers and produces an explainable,
deterministic leaderboard.

**Golden rule:** the LLM only *judges proposal content*. All arithmetic, benchmarks, tie-breaks and
ranks are plain Python, so the same validated scorecards always give the same ranking.

Live app: `<paste your Streamlit Community Cloud URL here>`

## Quick start (local)

```bash
python -m venv .venv && source .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python seed_db.py                                       # creates rfp.db with the 5 sample criteria
python sample_pdfs/generate_pdfs.py                     # (optional) regenerates the 4 fictional PDFs
streamlit run app.py
```

In the sidebar either tick **Demo mode** (offline keyword scorer, no key needed) or untick it and paste
your OpenAI API key. To use a key without typing it each time, create `.streamlit/secrets.toml`:

```toml
OPENAI_API_KEY = "sk-..."
```

(This file is git-ignored. Never commit a key.)

Tests: `python -m unittest discover -s tests -v`  ·  CLI demo: `python run_demo.py`

## Folder structure

```
app.py                  Streamlit UI (5 tabs)
orchestrator.py         Orchestrator Agent: runs the workflow in order
db.py / seed_db.py      SQLite schema, seed criteria, persistence
tools/pdf_tool.py       Document Tool      - PDF -> clean text (pypdf)
tools/llm_agent.py      Evaluation Agent   - prompt + OpenAI call (and offline demo scorer)
tools/validation.py     Validation Tool    - parse, normalise, clip, warn
tools/ranking.py        Ranking Tool       - formulas, benchmarks, PPI, tie-breaks (no LLM)
sample_pdfs/            4 fictional supplier proposals + generator script
sample_output/          exported JSON of a completed run
tests/test_core.py      21 unit/integration tests
```

## Architecture and data flow

1. Start app -> `init_db()` creates/seeds SQLite -> active criteria shown.
2. User uploads PDFs and enters supplier name, submission date, experience rating (0-10).
3. Inputs validated (names unique, dates valid, rating range, real PDF) -> `RFP_RUN_ID` created.
4. For each supplier: **latest active criteria reloaded** -> text extracted -> prompt built -> LLM called (1 retry).
5. **Validation Tool** parses the JSON and fixes it (below).
6. **Ranking Tool** computes absolute scores, benchmarks, gaps, relative %, PPI.
7. Stable sort with the mandatory tie-break order, then ranks 1, 2, 3 ... are assigned.
8. Everything is written to SQLite under one `RFP_RUN_ID`.
9. UI shows leaderboard, scorecards, run details and a JSON download.

### What validation does (every fix is logged as a warning)
- Accepts JSON wrapped in markdown fences or surrounding prose.
- Exactly one result per active criterion: missing -> score 0 and flagged `missing/invalid`.
- Non-numeric scores (`"excellent"`, `null`, `true`, NaN) -> 0 and flagged; `"7/10"` -> 7.
- Scores clipped into `0..max_score`; `max_score` always comes from the database, not the model.
- Unknown or duplicate `criterion_id`s ignored. Totally unusable output -> all zeros, status `failed`.
- Prompt injection guard: the prompt tells the model to treat the document as untrusted data.

## Formulas

| Item | Formula |
|---|---|
| Weight fraction | `weight / sum(active weights)` (so weights are rescaled, with a warning, if they don't total 100) |
| Absolute weighted score | `sum(score / max_score x weight_fraction) x 100` |
| Criterion benchmark | highest **valid** score for that criterion across all suppliers |
| Criterion gap | `score - benchmark` (0 for the leader, otherwise negative) |
| Relative performance % | `score / benchmark x 100` |
| Peer Performance Index (PPI) | `sum(relative % x weight_fraction)` |

**Tie-break order:** higher PPI -> earlier submission date -> higher experience rating -> supplier name A-Z.
Ranks are assigned only after this one stable sort. The Run details tab explains which rule decided each tie.

## Assumptions

- Benchmark = 0 (nobody scored on a criterion): relative % is defined as **100** for everyone (nobody is behind).
- A criterion the model failed to score counts as 0 for that supplier but is **not** used as a benchmark.
- PPIs equal to 6 decimals are treated as tied (removes floating-point noise).
- An unparsable submission date is treated as the latest possible date and warned about.
- Experience rating scale is 0-10 (higher = more experienced).
- Proposals longer than 60,000 characters are truncated (warned). Scanned/image-only PDFs have no text and will
  score 0 with a warning (no OCR).
- SQLite on Streamlit Community Cloud is **temporary** (reset when the app restarts). Download the JSON to keep a run.

## Sample data

Four fictional proposals for the same request (a procurement platform for "Meridian Manufacturing Ltd") with
different strengths: **Apex Systems** (technical + security, higher price), **BrightPath Tech** (cheapest, weak
compliance), **NexaWorks** (balanced; best plan and support), **Orbit Digital** (strong references, vague integration).
No real supplier data is used.

`sample_output/sample_run_demo_mode.json` was produced with the offline demo scorer. After running with your own
OpenAI key, export the JSON from the Run details tab and save it as `sample_output/sample_run.json`.

## Deploy on Streamlit Community Cloud

1. Push this folder to a public GitHub repo (`rfp.db` and secrets are git-ignored).
2. On share.streamlit.io choose **New app**, pick the repo, main file `app.py`.
3. Under **Advanced settings -> Secrets** add `OPENAI_API_KEY = "sk-..."`.
4. Deploy and put the public URL at the top of this README.

## Screenshots

Add after running the app: criteria tab, supplier input with a validation error, leaderboard, scorecard, run details.
