.PHONY: setup seed-db test run-dev run-heldout judge-validate report

setup:
	pip install -r requirements.txt

seed-db:
	python3 -m premise_eval.db

test:
	python3 -m pytest -q tests

run-dev:
	python3 -m premise_eval.runner --split dev --model fake --arm ordinary

run-heldout:
	python3 -m premise_eval.runner --split heldout --model fake --arm ordinary

judge-validate:
	@echo "milestone 3: two-reviewer judge validation protocol not yet implemented (judge.py is a stub)"

report:
	@echo "milestone 7: cost-framework report not yet implemented (see reports/report-*.json)"
