from __future__ import annotations

import shutil
from pathlib import Path

from fastapi import FastAPI, File, HTTPException, UploadFile
from pydantic import BaseModel

from app.config import settings
from app.services.benchmark_orchestrator import BenchmarkOrchestrator
from app.services.package_publisher import PackagePublisher


app = FastAPI(title=settings.app_name, version=settings.app_version)


class BenchmarkRunRequest(BaseModel):
    package_path: str
    benchmark_profile: str = "default"


@app.get("/health")
def health() -> dict:
    return {
        "status": "ok",
        "app_name": settings.app_name,
        "version": settings.app_version,
        "default_language": settings.default_language,
    }


@app.post("/api/packages/upload")
async def upload_package(file: UploadFile = File(...)) -> dict:
    if not file.filename:
        raise HTTPException(status_code=400, detail="Missing filename")
    if not file.filename.lower().endswith(".zip"):
        raise HTTPException(status_code=400, detail="Only .zip knowledge packages are supported")
    target = settings.uploaded_knowledge_dir / file.filename
    with target.open("wb") as handle:
        shutil.copyfileobj(file.file, handle)
    return {"status": "uploaded", "filename": file.filename, "package_path": str(target)}


@app.post("/api/benchmark/run")
def run_benchmark(request: BenchmarkRunRequest) -> dict:
    package_path = Path(request.package_path)
    if not package_path.exists():
        raise HTTPException(status_code=404, detail=f"Package path not found: {package_path}")
    result = BenchmarkOrchestrator().run(package_path, benchmark_profile=request.benchmark_profile)
    return result


@app.get("/api/benchmark/runs/{run_id}")
def get_benchmark_run(run_id: str) -> dict:
    result_path = settings.benchmark_runs_dir / run_id / "output" / "benchmark_result.json"
    if not result_path.exists():
        raise HTTPException(status_code=404, detail=f"Run not found: {run_id}")
    return {"run_id": run_id, "result_path": str(result_path), "content": result_path.read_text(encoding="utf-8")}


@app.get("/api/feedback/{run_id}")
def get_feedback(run_id: str) -> dict:
    feedback_path = settings.feedback_dir / f"{run_id}_feedback.json"
    if not feedback_path.exists():
        raise HTTPException(status_code=404, detail=f"Feedback not found: {run_id}")
    return {"run_id": run_id, "feedback_path": str(feedback_path), "content": feedback_path.read_text(encoding="utf-8")}


@app.post("/api/publish/{run_id}")
def publish_approved_package(run_id: str) -> dict:
    result_path = settings.benchmark_runs_dir / run_id / "output" / "benchmark_result.json"
    input_dir = settings.benchmark_runs_dir / run_id / "input"
    if not result_path.exists() or not input_dir.exists():
        raise HTTPException(status_code=404, detail=f"Run not found: {run_id}")
    output_zip = settings.exports_dir / f"Approved_RAG_Ingestion_Package_{run_id}.zip"
    PackagePublisher().publish(input_dir, output_zip)
    return {"status": "published", "run_id": run_id, "output_zip": str(output_zip)}
