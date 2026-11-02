"""Script de benchmark pour clipforge."""

import subprocess
import sys
import time
import tracemalloc
from pathlib import Path

# Test URL : vidéo libre de droits Big Buck Bunny (3 min)
TEST_URL = "https://www.youtube.com/watch?v=YE7VzlLtp-4"


def run_benchmark(model: str) -> dict[str, float]:
    """Exécute un benchmark avec un modèle Whisper donné."""
    print(f"Benchmark avec modèle {model}...")

    tracemalloc.start()
    start_time = time.time()

    try:
        # Exécuter le pipeline
        cmd = [
            "clipforge",
            "run",
            TEST_URL,
            "--model", model,
            "--provider", "heuristic",
            "--max-clips", "3",
            "--top", "1",
            "--draft",
        ]

        result = subprocess.run(cmd, check=True, capture_output=True, text=True)

        elapsed = time.time() - start_time
        current, peak = tracemalloc.get_traced_memory()
        tracemalloc.stop()

        return {
            "elapsed": elapsed,
            "memory_mb": peak / 1024 / 1024,
        }

    except subprocess.CalledProcessError as e:
        print(f"Erreur : {e}")
        print(f"stderr : {e.stderr}")
        return {"elapsed": 0, "memory_mb": 0}


def main() -> None:
    """Fonction principale."""
    print("=== Benchmark clipforge ===")
    print(f"URL de test : {TEST_URL}")
    print()

    models = ["tiny", "small", "medium"]
    results = {}

    for model in models:
        try:
            result = run_benchmark(model)
            results[model] = result
            print(f"{model}: {result['elapsed']:.2f}s, {result['memory_mb']:.1f} MB")
        except Exception as e:
            print(f"Erreur avec {model}: {e}")
            results[model] = {"elapsed": 0, "memory_mb": 0}

    # Écrire les résultats
    output = Path("docs/benchmarks.md")
    output.parent.mkdir(exist_ok=True)

    with open(output, "w", encoding="utf-8") as f:
        f.write("# Benchmarks clipforge\n\n")
        f.write(f"Test URL : {TEST_URL}\n\n")
        f.write("| Modèle | Temps (s) | Mémoire (MB) |\n")
        f.write("|--------|-----------|-------------|\n")
        for model, result in results.items():
            f.write(f"| {model} | {result['elapsed']:.2f} | {result['memory_mb']:.1f} |\n")

    print(f"\nRésultats écrits dans {output}")


if __name__ == "__main__":
    main()
