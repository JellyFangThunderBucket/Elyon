"""Projection only: never infer edges from URL, category, timing or payload hashes."""

from typing import Any
from urllib.parse import urlsplit, urlunsplit

from .protocol import clone


def graph(events: list[dict[str, Any]]) -> dict[str, Any]:
    return {'nodes': clone([e for e in events if e['kind'] != 'Relationship']),
            'relationships': clone([e for e in events if e['kind'] == 'Relationship'])}


def redact(value: Any) -> Any:
    """Conservative portable export: remove free-form evidence/configuration values.

    Retain structural IDs, observation labels and supporting links. This intentionally
    sacrifices detail rather than promising an exhaustive secret-name heuristic.
    """
    if isinstance(value, list):
        return [redact(item) for item in value]
    if not isinstance(value, dict):
        return value
    result: dict[str, Any] = {}
    for key, item in value.items():
        if key in {'headers', 'body', 'plan', 'scope', 'details', 'reason'}:
            result[key] = {'certainty': 'redacted'}
        elif key == 'url' and isinstance(item, str):
            parsed = urlsplit(item)
            # No credentials, query or fragment. Path can contain secrets too.
            result[key] = urlunsplit((parsed.scheme, parsed.hostname or '', '/[redacted]', '', ''))
        else:
            result[key] = redact(item)
    return result
