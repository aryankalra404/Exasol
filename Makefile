PY ?= .venv/bin/python
SEED ?= 42
LOANS ?= 10000
DATASET := data/s$(SEED)_n$(LOANS)

.PHONY: setup generate load audit demo test oracle app web clean

setup:            ## python venv + dependencies, web build tools
	python3 -m venv .venv
	$(PY) -m pip install -q -r requirements.txt
	cd app/web && npm install --silent

generate:         ## synthetic loan book (deterministic for SEED and LOANS)
	$(PY) -m generator.generate --seed $(SEED) --loans $(LOANS)

load:             ## create schemas and IMPORT the CSVs into Exasol
	$(PY) -m scripts.load $(DATASET)

audit:            ## run the SQL pipeline inside Exasol
	$(PY) -m scripts.audit --label "make audit"

demo: generate load audit   ## everything: generate, load, audit

test:             ## unit + acceptance tests (db tests skip without .env)
	$(PY) -m pytest -q tests

oracle:           ## independent oracle vs latest run, all loans
	$(PY) -m eval.oracle_agreement $(DATASET)

web:              ## build the auditor UI into app/web/dist
	cd app/web && npm run build

app: web          ## serve API + UI on http://127.0.0.1:8000
	$(PY) -m uvicorn app.api.main:app --port 8000

clean:
	rm -rf data letters/out app/web/dist
