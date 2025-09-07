# Contributing

Thanks for your interest!

## Dev setup
- Python 3.11+
- Create venv and install deps:
  - `pip install -r requirements.txt`
  - `pip install pytest ruff black isort pre-commit`
- Install pre-commit hooks: `pre-commit install`

## Running tests
- `pytest -q`

## Formatting & linting
- `ruff check --fix .`
- `ruff format .` (or `black .`)
- `isort .`

## Pull requests
- Describe the change and motivation.
- Include tests for new behavior.
- Avoid secrets in commits.

