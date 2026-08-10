.PHONY: help install install-dev test lint format clean

# Default target
help:
	@echo "Better DNF - Development Commands"
	@echo "==================================="
	@echo ""
	@echo "Usage:"
	@echo "  make install      - Install the package"
	@echo "  make install-dev  - Install in development mode"
	@echo "  make test         - Run tests"
	@echo "  make lint         - Run linter"
	@echo "  make format       - Format code"
	@echo "  make clean        - Clean build artifacts"
	@echo "  make check        - Run all checks"
	@echo ""

# Install the package
install:
	pip install .

# Install in development mode
install-dev:
	pip install -e ".[dev]"

# Run tests
test:
	pytest tests/ -v

# Run tests with coverage
test-cov:
	pytest tests/ -v --cov=better_dnf --cov-report=html

# Run linter
lint:
	ruff check .

# Format code
format:
	black .

# Type checking
typecheck:
	mypy src/

# Clean build artifacts
clean:
	rm -rf build/
	rm -rf dist/
	rm -rf *.egg-info
	rm -rf htmlcov/
	rm -rf .coverage
	find . -type d -name __pycache__ -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete

# Run all checks
check: lint typecheck test

# Run the tool
run:
	better-dnf --help

# Development server (for future web interface)
dev:
	python -m better_dnf.cli

# Build documentation (if using mkdocs)
docs:
	mkdocs serve

# Build distribution
build:
	python -m build