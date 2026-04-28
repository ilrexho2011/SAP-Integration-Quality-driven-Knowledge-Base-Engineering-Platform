from __future__ import annotations

import json
from pathlib import Path

import requests
import streamlit as st

from app.config import settings


TEXT = {
    "EN": {
        "title": "AI4BIZ Knowledge Retrieval Quality Assessment Platform",
        "language": "Language",
        "api_status": "API Status",
        "monitor": "Monitor Actual Inventory and Events",
        "generate": "Generate Catalog Docs & KEDB + Runbooks",
        "benchmark": "Benchmark Knowledge Package & Build Reports",
        "feedback": "Dynamic Corrective Feedback",
        "publish": "Publish Approved RAG Ingestion Package",
        "upload": "Upload Knowledge Package",
        "run_benchmark": "Run Benchmark",
        "package_path": "Package path",
        "results": "Benchmark Results",
        "weak_docs": "Inspect Weak Documents",
        "top_docs": "Inspect Top Documents",
        "download_reports": "Download Enterprise Reports",
        "send_feedback": "Send Feedback to Generator",
        "placeholder": "This section is wired as the enterprise control plane for the backend services.",
    },
    "DE": {
        "title": "AI4BIZ Plattform zur Bewertung der Retrieval-Qualitaet",
        "language": "Sprache",
        "api_status": "API-Status",
        "monitor": "Aktuelles Inventar und Ereignisse ueberwachen",
        "generate": "Catalog Docs & KEDB + Runbooks generieren",
        "benchmark": "Knowledge Package benchmarken & Reports erstellen",
        "feedback": "Dynamisches Korrektur-Feedback",
        "publish": "Freigegebenes RAG-Ingestion-Paket veroeffentlichen",
        "upload": "Knowledge Package hochladen",
        "run_benchmark": "Benchmark starten",
        "package_path": "Paketpfad",
        "results": "Benchmark-Ergebnisse",
        "weak_docs": "Schwache Dokumente pruefen",
        "top_docs": "Top-Dokumente pruefen",
        "download_reports": "Enterprise Reports herunterladen",
        "send_feedback": "Feedback an Generator senden",
        "placeholder": "Dieser Bereich ist als Enterprise-Control-Plane fuer die Backend-Services vorgesehen.",
    },
}


def api_get(path: str) -> dict | None:
    try:
        response = requests.get(f"{settings.api_base_url}{path}", timeout=5)
        response.raise_for_status()
        return response.json()
    except Exception as exc:
        st.warning(f"API unavailable: {exc}")
        return None


def api_post(path: str, payload: dict) -> dict | None:
    try:
        response = requests.post(f"{settings.api_base_url}{path}", json=payload, timeout=120)
        response.raise_for_status()
        return response.json()
    except Exception as exc:
        st.error(f"API call failed: {exc}")
        return None


def main() -> None:
    st.set_page_config(page_title="AI4BIZ KRQA", layout="wide")
    language = st.sidebar.selectbox("Language / Sprache", ["EN", "DE"], index=0)
    t = TEXT[language]

    st.title(t["title"])
    status = api_get("/health")
    if status:
        st.success(f"{t['api_status']}: {status.get('status')} - v{status.get('version')}")
    else:
        st.info("Start backend with: uvicorn app.main:app --reload")

    section = st.sidebar.radio(
        "Navigation",
        [t["monitor"], t["generate"], t["benchmark"], t["feedback"], t["publish"]],
    )

    if section == t["monitor"]:
        st.header(t["monitor"])
        col1, col2, col3 = st.columns(3)
        col1.metric("Packages", "0")
        col2.metric("MPL Success", "0")
        col3.metric("MPL Errors", "0")
        st.info(t["placeholder"])

    elif section == t["generate"]:
        st.header(t["generate"])
        uploaded = st.file_uploader(t["upload"], type=["zip"])
        if uploaded:
            target = settings.uploaded_knowledge_dir / uploaded.name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(uploaded.getbuffer())
            st.success(f"Saved locally: {target}")
        st.info(t["placeholder"])

    elif section == t["benchmark"]:
        st.header(t["benchmark"])
        package_path = st.text_input(t["package_path"], value=str(settings.project_root / "sample_packages" / "demo_kedb_runbooks.zip"))
        if st.button(t["run_benchmark"]):
            result = api_post("/api/benchmark/run", {"package_path": package_path, "benchmark_profile": "default"})
            if result:
                st.subheader(t["results"])
                m1, m2, m3, m4 = st.columns(4)
                m1.metric("Overall RAG Readiness Score", result.get("final_score"))
                m2.metric("Policy Compliance Score", result.get("metrics", {}).get("policy_compliance"))
                m3.metric("Retrieval Precision", result.get("metrics", {}).get("retrieval_precision"))
                m4.metric("Retrieval Recall", result.get("metrics", {}).get("retrieval_recall"))
                st.json(result.get("feedback", {}))

    elif section == t["feedback"]:
        st.header(t["feedback"])
        run_id = st.text_input("Run ID")
        if run_id and st.button("Load Feedback"):
            feedback = api_get(f"/api/feedback/{run_id}")
            if feedback:
                st.json(json.loads(feedback["content"]))
        st.info(t["send_feedback"])

    elif section == t["publish"]:
        st.header(t["publish"])
        run_id = st.text_input("Approved Run ID")
        if run_id and st.button(t["publish"]):
            result = api_post(f"/api/publish/{run_id}", {})
            if result:
                st.success(result)


if __name__ == "__main__":
    main()
