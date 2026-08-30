PY := .venv/bin/python
PIP := .venv/bin/pip
FIXTURE ?= evals/fixtures/sample
CASES ?= all

.PHONY: setup test inspect capture enrich replay baseline ablation eval debrief demo scan clean

PYTHON ?= python3

# Everything the graded path needs, on whatever `python3` the reviewer has. Capture-only
# packages are NOT installed here: streamlink needs 3.10+, and requiring it made this target
# fail from a clean clone on macOS system Python 3.9, before `make test` could even run.
setup:
	@$(PYTHON) -c 'import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)' || \
		{ echo ""; \
		  echo "  This project needs CPython 3.10+ (it uses dataclass slots)."; \
		  echo "  '$(PYTHON)' is $$($(PYTHON) -V 2>&1) — macOS ships 3.9 as the system python3."; \
		  echo ""; \
		  echo "  Re-run naming a newer interpreter, e.g.:"; \
		  echo "      make setup PYTHON=python3.12"; \
		  echo ""; exit 1; }
	$(PYTHON) -m venv .venv
	$(PIP) install --upgrade pip
	$(PIP) install -r requirements.txt
	$(PIP) install -e .
	@echo "OK. No API keys needed for test, inspect, baseline, replay, eval, debrief or demo."

# Only for `make capture`, which reads a live broadcast. Needs Python 3.10+.
setup-record:
	$(PIP) install -r requirements-record.txt
	@echo "OK. Capture extras installed. Export TS_LLM_API_KEY and DEEPGRAM_API_KEY to enrich."

test:
	$(PY) -m pytest tests -q

# Sanity-check a fixture without any model call.
inspect:
	$(PY) -m ts.cli inspect --fixture $(FIXTURE)

# Stage 1: RAW CAPTURE. NO API KEYS. Time-critical - the stream must be live.
#   make capture CHANNEL=somestreamer MINUTES=10
capture:
	$(PY) -m ts.cli capture --channel $(CHANNEL) --minutes $(MINUTES) --out evals/fixtures

# Stage 2: enrichment. Needs keys. Runs any time afterwards from the recorded bytes.
#   make enrich FIXTURE=evals/fixtures/somestreamer_2026-08-29T2140
enrich:
	TS_LLM_MODE=record $(PY) -m ts.cli enrich --fixture $(FIXTURE)

# Everything below runs offline from cached model responses. NO KEYS REQUIRED.
replay:
	TS_LLM_MODE=replay $(PY) -m ts.cli replay --fixture $(FIXTURE) --out evidence/raw-results

baseline:
	TS_LLM_MODE=replay $(PY) -m ts.cli baseline --fixture $(FIXTURE) --out evidence/raw-results

ablation:
	TS_LLM_MODE=replay $(PY) -m ts.cli baseline --fixture $(FIXTURE) --chat-only --out evidence/raw-results

eval:
	TS_LLM_MODE=replay $(PY) -m evals.run_eval --cases $(CASES) --out evidence

# The post-stream artifact. No model call - it reorganises what `make replay` already verified.
debrief:
	$(PY) -m ts.cli debrief --fixture $(FIXTURE) --out evidence/raw-results

demo:
	$(PY) -m ts.cli serve --fixture $(FIXTURE) --port 8000

scan:
	@echo "Scanning for secrets before archiving..."
	$(PY) scripts/scan_secrets.py

clean:
	rm -rf .venv __pycache__ .pytest_cache
