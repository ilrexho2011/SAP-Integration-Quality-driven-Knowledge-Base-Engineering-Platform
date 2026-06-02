from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any

from jinja2 import Environment, FileSystemLoader, StrictUndefined, select_autoescape

TEMPLATE_DIR = Path(__file__).resolve().parents[1] / "templates" / "knowledge"


@lru_cache(maxsize=1)
def _environment() -> Environment:
    """Build the Jinja2 environment once.

    trim_blocks + lstrip_blocks make `{% for %}` control lines disappear cleanly
    so the rendered Markdown matches the previous hand-joined output exactly.
    StrictUndefined turns a missing context key into an error rather than a
    silent blank, which keeps templates and the service contract in lock-step.
    """
    return Environment(
        loader=FileSystemLoader(str(TEMPLATE_DIR)),
        autoescape=select_autoescape(enabled_extensions=(), default=False),
        trim_blocks=True,
        lstrip_blocks=True,
        keep_trailing_newline=True,
        undefined=StrictUndefined,
    )


class DocumentTemplateService:
    """Render knowledge-document bodies from Jinja2 templates.

    v2.0.7 (2.6): the document STRUCTURE (headings, metadata block, section
    order) now lives in app/templates/knowledge/*.md.j2 instead of being
    hand-joined string lists inside the generator. The generator still owns all
    logic (IDs, signatures, evidence, AI enrichment) and passes a fully prepared
    context; the template only decides layout. This makes headings stable from a
    single source and lets the structure change without touching Python.
    """

    TEMPLATES = {
        "kedb": "kedb.md.j2",
        "runbook": "runbook.md.j2",
    }

    def render(self, document_type: str, context: dict[str, Any]) -> str:
        template_name = self.TEMPLATES.get(document_type)
        if not template_name:
            raise ValueError(f"No template registered for document type: {document_type}")
        template = _environment().get_template(template_name)
        rendered = template.render(**context)
        return self._normalize(rendered)

    def _normalize(self, text: str) -> str:
        """Match the legacy '\\n'.join(lines) + '\\n' output exactly.

        The previous generator produced lines joined by single newlines with a
        single trailing newline and no trailing blank lines. We strip any
        trailing whitespace and re-append exactly one newline.
        """
        return text.rstrip("\n") + "\n"

    def available_templates(self) -> dict[str, str]:
        return dict(self.TEMPLATES)
