PYTHON ?= python3

.PHONY: install format lint typecheck test check migrate seed compose-up compose-down

install:
	$(PYTHON) -m pip install --requirement requirements/dev.txt

format:
	$(PYTHON) -m ruff format .
	$(PYTHON) -m ruff check --fix .

lint:
	$(PYTHON) -m ruff format --check .
	$(PYTHON) -m ruff check .

typecheck:
	$(PYTHON) -m mypy firstbrief tests tools

test:
	$(PYTHON) -m pytest --cov=firstbrief --cov-report=term-missing

check: lint typecheck test
	$(PYTHON) manage.py check
	$(PYTHON) manage.py makemigrations --check --dry-run

migrate:
	$(PYTHON) manage.py migrate

seed:
	$(PYTHON) manage.py seed_development

compose-up:
	docker compose up --build

compose-down:
	docker compose down
