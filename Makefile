PY ?= python3
export PYTHONPATH := src

.PHONY: help data mocks mock1 test app docs clean all

help:
	@echo "make data   - generate synthetic SYSPRO/Syteline extracts (deterministic)"
	@echo "make mocks  - run Mock 1, 2, 3 (profile, silver, IFS load, gates, reconciliation, gold)"
	@echo "make test   - run the test suite"
	@echo "make app    - launch the Streamlit governance app"
	@echo "make docs   - regenerate STTM / data dictionary / defect catalogue"
	@echo "make all    - data + mocks + docs + test"

data:
	$(PY) -m ifs_migration.datagen.generate --scale 1.0 --seed 42

mocks:
	$(PY) -m ifs_migration.pipeline --all-mocks

mock1:
	$(PY) -m ifs_migration.pipeline --mock 1

test:
	$(PY) -m pytest -q

app:
	streamlit run app/streamlit_app.py

docs:
	$(PY) -m ifs_migration.docgen

all: data mocks docs test

clean:
	rm -rf warehouse data/ifs_load data/id_registry reconciliation_logs/mock_* reconciliation_logs/*.md reconciliation_logs/*.csv
