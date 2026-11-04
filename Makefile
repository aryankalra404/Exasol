PY ?= .venv/bin/python
SEED ?= 42
LOANS ?= 10000
DATASET := data/s$(SEED)_n$(LOANS)

.PHONY: setup generate load audit demo review-reset test oracle robustness red-team red-team-template scale ask-setup ask-smoke app web clean

setup:            ## python venv + dependencies, web build tools
	python3 -m venv .venv
	$(PY) -m pip install -q -r requirements.txt
	cd app/web && npm ci --silent

generate:         ## synthetic loan book (deterministic for SEED and LOANS)
	$(PY) -m generator.generate --seed $(SEED) --loans $(LOANS)

load:             ## create schemas and IMPORT the CSVs into Exasol
	$(PY) -m scripts.load $(DATASET)

audit:            ## run the SQL pipeline inside Exasol
	$(PY) -m scripts.audit --label "Baseline audit"

demo: generate load audit   ## everything: generate, load, audit

review-reset:     ## clear review records for the loaded synthetic book, to rehearse the demo
	$(PY) -m scripts.review_reset

test:             ## unit + acceptance tests (db tests skip without .env)
	$(PY) -m pytest -q tests

oracle:           ## independent oracle vs latest run, all loans
	$(PY) -m eval.oracle_agreement $(DATASET)

scale:            ## generate, load and audit a big book in SCALE_* schemas, report in eval/reports/ (LOANS=500000)
	$(PY) -m eval.scale --seed 7 --loans $(LOANS)

robustness:       ## same book at defect levels 0, 1, 3 in separate ROB_* schemas, scored against truth
	$(PY) -m eval.robustness --seed $(SEED) --loans $(LOANS)

red-team-template: ## blank-format CSVs for the blind red team, in tests/fixtures/red_team
	$(PY) -m eval.red_team --template

red-team:         ## audit the blind red-team book in separate RT_* schemas and score it, see docs/RED_TEAM.md
	$(PY) -m eval.red_team

ask-setup:        ## SAHI_ASK views + read-only ASK_READER user for the MCP server (password into .env)
	$(PY) -m scripts.ask_setup

ask-smoke:        ## start the MCP server as ASK_READER, run example questions, check it cannot read SAHI_TRUTH
	uvx --from exasol-mcp-server@2.3.0 python -m eval.ask_smoke

web:              ## build the auditor UI into app/web/dist
	cd app/web && npm run build

app: web          ## serve API + UI on http://127.0.0.1:8000
	$(PY) -m uvicorn app.api.main:app --port 8000

clean:
	rm -rf data letters/out app/web/dist
