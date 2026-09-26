MLX_DIR := libs/mlx_CLXV-2.2/mlx_CLXV

.PHONY: install run debug test mlx-build graphics-manual lint docs clean

install: mlx-build
	python3 -m pip install -r requirements.txt
	python3 -m pip install -e ".[test]"

env: mlx-build
	python3 -m venv .venv
	. .venv/bin/activate && python3 -m pip install -r requirements.txt
	. .venv/bin/activate && python3 -m pip install -e ".[test]"

mlx-build:
	$(MAKE) -C $(MLX_DIR)

run:
	python3 -m fly_in $(ARGS)

debug:
	python3 -m pdb -m fly_in $(ARGS)

test:
	pytest -q

graphics-manual: mlx-build
	. .venv/bin/activate && python tests/manual_graphics.py

lint:
	flake8 .
	mypy . --warn-return-any --warn-unused-ignores --ignore-missing-imports --disallow-untyped-defs --check-untyped-defs

docs:
	mkdocs build

clean:
	find . -type f -name '*.pyc' -delete
	find . -type d -name '__pycache__' -prune -exec rm -rf {} +
	rm -rf .pytest_cache .mypy_cache build dist *.egg-info htmlcov

