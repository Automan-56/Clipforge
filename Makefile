.PHONY: install lint format test clean help

help:
	@echo "Commandes disponibles :"
	@echo "  make install    - Installer le package en mode développement"
	@echo "  make lint       - Exécuter ruff check"
	@echo "  make format     - Exécuter ruff format"
	@echo "  make test       - Exécuter pytest"
	@echo "  make test-cov   - Exécuter pytest avec couverture"
	@echo "  make clean      - Nettoyer les fichiers temporaires"

install:
	pip install -e .[dev]

lint:
	ruff check src/ tests/

format:
	ruff format src/ tests/

test:
	pytest

test-cov:
	pytest --cov=clipforge --cov-report=html

clean:
	rm -rf build/ dist/ *.egg-info .pytest_cache/ htmlcov/ .coverage .ruff_cache/
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
