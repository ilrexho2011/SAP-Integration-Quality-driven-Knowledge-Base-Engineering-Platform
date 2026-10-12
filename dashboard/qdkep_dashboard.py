from __future__ import annotations

# Backward-compatible entrypoint kept for Sprint 9 users. The actual Blueprint v1
# console lives in qdkep_enterprise_quality_console.py.
exec(
    open(
        __file__.replace("qdkep_dashboard.py", "qdkep_enterprise_quality_console.py"),
        encoding="utf-8",
    ).read()
)
