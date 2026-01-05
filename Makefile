.PHONY: install dev lint format typecheck test clean docker-build

# Install production dependencies
install:
	pip install -e .

# Install development dependencies
dev:
	pip install -e ".[dev]"
	pre-commit install

# Run linter
lint:
	ruff check .

# Auto-fix linting issues
lint-fix:
	ruff check . --fix

# Format code
format:
	black .

# Check formatting without modifying
format-check:
	black . --check

# Run type checker
typecheck:
	mypy services/

# Run tests with coverage
test:
	pytest

# Run tests without coverage (faster)
test-fast:
	pytest --no-cov

# Clean build artifacts
clean:
	rm -rf build/
	rm -rf dist/
	rm -rf *.egg-info/
	rm -rf .pytest_cache/
	rm -rf .mypy_cache/
	rm -rf .ruff_cache/
	rm -rf htmlcov/
	rm -rf .coverage
	find . -type d -name __pycache__ -exec rm -rf {} +

# Build Docker containers (CPU profile)
docker-build:
	docker compose build

# Run all checks (CI simulation)
ci: lint typecheck test
	@echo "All CI checks passed!"
