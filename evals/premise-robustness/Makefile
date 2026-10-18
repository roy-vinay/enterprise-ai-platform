.PHONY: setup seed-db test run-dev run-heldout judge-validate judge-validate-sample report

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
	python3 -m validation.score_judge

judge-validate-sample:
	python3 -m validation.sample

report:
	@echo "milestone 7: cost-framework report not yet implemented (see reports/report-*.json)"
