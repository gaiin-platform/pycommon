.PHONY: help test coverage clean format

help:
	@echo "Available commands:"
	@echo "  make test       - Run tests with pytest"
	@echo "  make coverage   - Run tests with coverage report"
	@echo "  make clean      - Clean up coverage files"
	@echo "  make format     - Format code with black"


# Run tests with pytest
test:
	cd .. && python -m pytest pycommon/tests/ -v

# Format code with black
format:
	black .

# Run tests with coverage report
coverage:
	cd .. && python -m pytest pycommon/tests/ --cov=pycommon --cov-report=term-missing --cov-fail-under=100 -v --cov-report xml:pycommon/cov.xml

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
