from __future__ import annotations

import re
from collections import OrderedDict
from dataclasses import dataclass
from typing import Any
from collections.abc import Mapping

from app.contracts.constants import MANDATORY_METADATA_ORDER, STABLE_METADATA_ORDER

META_LINE_RE = re.compile(r"^(?P<key>[A-Za-z][A-Za-z0-9_]*):\s*(?P<value>.*)$")
HEADING_RE = re.compile(r"^(#{1,6}\s+|\d+\.\s+|[A-Z][A-Z0-9 _/-]{2,}$)")


@dataclass(frozen=True)
class MetadataNormalizationResult:
    metadata: OrderedDict[str, str]
    missing_required: tuple[str, ...]
    order_issues: tuple[str, ...]

    @property
    def valid(self) -> bool:
        return not self.missing_required and not self.order_issues

    def to_dict(self) -> dict:
        return {
            "valid": self.valid,
            "metadata": dict(self.metadata),
            "missing_required": list(self.missing_required),
            "order_issues": list(self.order_issues),
        }


class MetadataNormalizer:
    """Parses and normalizes QDKEP flat metadata blocks with stable contract order."""

    def parse_markdown_metadata(self, markdown_text: str) -> OrderedDict[str, str]:
        metadata: OrderedDict[str, str] = OrderedDict()
        started = False
        for raw_line in markdown_text.splitlines():
            line = raw_line.strip()
            if not line:
                if started:
                    continue
                continue
            match = META_LINE_RE.match(line)
            if match:
                started = True
                key = match.group("key")
                value = match.group("value").strip().strip('"').strip("'")
                metadata[key] = value
                continue
            if started and HEADING_RE.match(line):
                break
        return metadata

    def normalize(self, metadata: Mapping[str, Any]) -> MetadataNormalizationResult:
        string_metadata = {
            str(k).strip(): "" if v is None else str(v).strip().strip('"').strip("'")
            for k, v in metadata.items()
        }
        ordered: OrderedDict[str, str] = OrderedDict()
        for key in STABLE_METADATA_ORDER:
            if key in string_metadata:
                ordered[key] = string_metadata[key]
        for key in sorted(k for k in string_metadata if k not in ordered):
            ordered[key] = string_metadata[key]
        missing = tuple(key for key in MANDATORY_METADATA_ORDER if not ordered.get(key))
        observed_keys = [key for key in string_metadata if key in STABLE_METADATA_ORDER]
        expected_keys = [key for key in STABLE_METADATA_ORDER if key in observed_keys]
        order_issues: list[str] = []
        if observed_keys != expected_keys:
            order_issues.append("Metadata fields must follow the stable QDKEP contract order")
        return MetadataNormalizationResult(ordered, missing, tuple(order_issues))

    def normalize_markdown(self, markdown_text: str) -> MetadataNormalizationResult:
        return self.normalize(self.parse_markdown_metadata(markdown_text))

    def render_block(self, metadata: Mapping[str, Any]) -> str:
        normalized = self.normalize(metadata).metadata
        return "\n".join(f'{key}: "{value}"' for key, value in normalized.items())
