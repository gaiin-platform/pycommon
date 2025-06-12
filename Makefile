.PHONY: help test coverage clean format

help:
	@echo "Available commands:"
	@echo "  make test       - Run tests with pytest"
	@echo "  make coverage   - Run tests with coverage report"
	@echo "  make clean      - Clean up coverage files"
	@echo "  make format     - Format code with black"


# Run tests with pytest
test:
	pytest

# Format code with black
format:
	black .

# Run tests with coverage report
coverage:
	pytest --cov --cov-report=term-missing --cov-fail-under=100  -v --cov-report xml:cov.xml

# Clean up coverage files
clean:
	rm -rf .pytest_cache htmlcov .coverage
