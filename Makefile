.PHONY: install init-db index run test lint format check evals

PYTHON := python
STREAMLIT := streamlit

install:
	$(PYTHON) -m pip install -U pip
	$(PYTHON) -m pip install -r requirements.txt
	$(PYTHON) -m pip install -e .

init-db:
	$(PYTHON) scripts/init_db.py

index:
	$(PYTHON) scripts/build_rubric_index.py

run:
	$(STREAMLIT) run app/streamlit_app.py

test:
	$(PYTHON) -m pytest tests/ -v

lint:
	$(PYTHON) -m ruff check src/ app/ tests/ evals/ scripts/

format:
	$(PYTHON) -m ruff format src/ app/ tests/ evals/ scripts/

check: lint test

evals:
	$(PYTHON) evals/run_evals.py