.PHONY: help test coverage clean format lint

help:
	@echo "Available commands:"
	@echo "  make test       - Run tests with pytest"
	@echo "  make coverage   - Run tests with coverage report"
	@echo "  make clean      - Clean up coverage files"
	@echo "  make format     - Format code with black"
	@echo "  make lint       - Run flake8 for code linting"


# Run tests with pytest
test:
	pytest

# Format code with black
format:
	black .

# Run flake8 for code linting
lint:
	flake8 --exclude=venv .

# Run tests with coverage report
coverage:
	pytest --cov=pycommon --cov-report=term-missing --cov-fail-under=100  -v --cov-report xml:cov.xml

# Clean up coverage files
clean:
	rm -rf .pytest_cache htmlcov .coverage

setup:
	@echo "Setting up the environment..."
	set -e; \
	python3 -m venv venv; \
	. venv/bin/activate && pip install -r requirements.txt; \
	chmod +x scripts/*.sh && \
	scripts/setup_precommit.sh
	@echo "Setup complete."
	@echo "To activate the virtual environment, run: . venv/bin/activate"
