.PHONY: setup data test lint gate report ollama
setup:
	pip install -r requirements.txt
data:
	python -m t2s_eval.cli build-data
test:
	python -m pytest -q tests
lint:
	python -m t2s_eval.cli lint
gate:
	python -m t2s_eval.cli gate
report:
	python -m t2s_eval.cli run
ollama:
	python -m t2s_eval.cli run --bot ollama --model qwen2.5-coder:7b --llm-judge
