.PHONY: install dev test lint format build curate stats clean help

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-15s\033[0m %s\n", $$1, $$2}'

install: ## Install the package
	pip install -e .

dev: ## Install with dev dependencies
	pip install -e ".[dev]"

test: ## Run tests
	pytest tests/ -v

lint: ## Run linter
	ruff check src/ tests/
	ruff format --check src/ tests/

format: ## Auto-format code
	ruff format src/ tests/
	ruff check --fix src/ tests/

build: ## Build the database from JSON sources
	prompt-db build --data-dir . --output prompts.db --force

curate: build ## Build and curate (remove noise)
	prompt-db --db prompts.db curate

stats: ## Show database statistics (build first if needed)
	@test -f prompts.db || $(MAKE) build
	prompt-db --db prompts.db stats

clean: ## Remove generated files
	rm -f prompts.db prompts.db-wal prompts.db-shm
	rm -rf __pycache__ .pytest_cache .ruff_cache
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
