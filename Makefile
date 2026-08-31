PY := .venv/bin/python
PIP := .venv/bin/pip
# A RECORDED fixture, so `make replay` / `make baseline` / `make demo` typed with no arguments
# work from the committed cache with no keys — which is what README.md promises. The scaffold
# `sample` fixture has no recording, so the bare command used to exit 3 with "nothing is
# recorded for this fixture yet", which reads as a broken submission rather than a wrong flag.
FIXTURE ?= evals/fixtures/stableronaldo_2026-08-30T0723
CASES ?= all

.PHONY: setup setup-record test inspect capture enrich replay baseline ablation eval graph debrief demo review preflight scan archive clean

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

# --ablation is included so this command reproduces the COMMITTED evidence/report.md exactly.
# It was opt-in while recording, because each extra system was 11 more paid calls; on replay it
# is free, and a documented command that silently rewrites the committed table with fewer rows
# than the README quotes is a reproducibility trap.
eval:
	TS_LLM_MODE=replay $(PY) -m evals.run_eval --cases $(CASES) --ablation --out evidence

# The diagram is generated, never drawn by hand: it reads the agent's own constants, the gate's
# own codes and the committed trajectories. Regenerate it whenever any of those move.
graph:
	TS_LLM_MODE=replay $(PY) -m ts.report.graph

# The post-stream artifact. No model call - it reorganises what `make replay` already verified.
debrief:
	$(PY) -m ts.cli debrief --fixture $(FIXTURE) --out evidence/raw-results

demo:
	$(PY) -m ts.cli serve --fixture $(FIXTURE) --port 8000

# One command before submitting: is this ready to hand in? Reports and never fixes.
preflight:
	@$(PY) scripts/preflight.py

# Gold-label review. `--list` shows the state; confirming is deliberately one case at a time.
review:
	$(PY) scripts/confirm_gold.py --list

scan:
	@echo "Scanning for secrets before archiving..."
	$(PY) scripts/scan_secrets.py

# Package exactly what is committed — never the working tree, which holds .env, .venv and raw
# media. `git archive` cannot include an untracked file by accident, which is the property that
# matters here: .gitignore does not protect a directory that is zipped rather than committed.
archive:
	git archive --format=zip -o /tmp/twinky.zip HEAD
	@rm -rf /tmp/twinky-check && mkdir -p /tmp/twinky-check
	@unzip -qq /tmp/twinky.zip -d /tmp/twinky-check
	@$(PY) scripts/scan_secrets.py --root /tmp/twinky-check
	@echo "OK  /tmp/twinky.zip  ($$(find /tmp/twinky-check -type f | wc -l | tr -d ' ') files)"
	@echo "Now open it: cd /tmp/twinky-check && make setup && make test && make eval"

clean:
	rm -rf .venv __pycache__ .pytest_cache
