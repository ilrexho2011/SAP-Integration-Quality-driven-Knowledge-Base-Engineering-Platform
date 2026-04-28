from pathlib import Path

from app.services.benchmark_orchestrator import BenchmarkOrchestrator

if __name__ == "__main__":
    package = Path("sample_packages/demo_kedb_runbooks.zip")
    result = BenchmarkOrchestrator().run(package)
    print("Run ID:", result["run_id"])
    print("Final Score:", result["final_score"])
    print("Status:", result["status"])
