.PHONY: install test evals audit daemon lint clean

install:
	pip install -e ".[dev]"

test:
	pytest -q

evals:
	droidcode eval --dir evals/tasks --tokens evals/tokens.json

audit:
	droidcode audit --scenario evals/tasks/checkout_low_contrast.json --tokens evals/tokens.json

daemon:
	droidcode daemon --socket /tmp/droidcode.sock --scenario evals/tasks/checkout_low_contrast.json

clean:
	rm -rf artifacts .pytest_cache **/__pycache__ *.egg-info
