.PHONY: play demo simulate test test-fast lint format notebook

play:
	python -m blackjack

demo:
	python -m blackjack --demo --rounds 1000

simulate:
	python -m blackjack --simulate 100000 --bet 10 --bankroll 1000000

test:
	python -m pytest -q

test-fast:
	python -m pytest -q -m "not slow"

lint:
	python -m flake8 blackjack tests

format:
	python -m black

notebook:
	jupyter notebook notebooks/Prog_Project.ipynb
