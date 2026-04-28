from pathlib import Path

from app.services.markdown_parser import parse_markdown_file


def test_parse_markdown_file(tmp_path: Path):
    p = tmp_path / "RB-P2-0014.md"
    p.write_text("# HTTP 429 Receiver Throttling\n\nartifact_type: \"runbook\"\npriority: \"P2\"\n\n## Diagnosis\nText", encoding="utf-8")
    doc = parse_markdown_file(p)
    assert doc.title == "HTTP 429 Receiver Throttling"
    assert doc.document_type == "runbook"
    assert doc.metadata["priority"] == "P2"
