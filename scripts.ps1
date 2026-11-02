# Scripts PowerShell pour clipforge (Windows)

function Install-Dev {
    pip install -e .[dev]
}

function Invoke-Lint {
    ruff check src/ tests/
}

function Invoke-Format {
    ruff format src/ tests/
}

function Invoke-Test {
    pytest
}

function Invoke-TestCov {
    pytest --cov=clipforge --cov-report=html
}

function Invoke-Clean {
    Remove-Item -Recurse -Force build, dist, *.egg-info, .pytest_cache, htmlcov, .coverage, .ruff_cache -ErrorAction SilentlyContinue
    Get-ChildItem -Recurse -Directory __pycache__ | Remove-Item -Recurse -Force -ErrorAction SilentlyContinue
}

# Exporter les fonctions
Export-ModuleMember -Function Install-Dev, Invoke-Lint, Invoke-Format, Invoke-Test, Invoke-TestCov, Invoke-Clean
