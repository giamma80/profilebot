"""Workflow definition loader."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, cast

import yaml
from pydantic import ValidationError

from src.core.workflows.schemas import WorkflowDefinition


def load_workflow(path: Path) -> WorkflowDefinition:
    """Load and validate a workflow definition from YAML/JSON."""
    payload = _load_payload(path)
    try:
        return cast(WorkflowDefinition, WorkflowDefinition.model_validate(payload))
    except ValidationError as exc:
        raise ValueError(f"Invalid workflow definition in {path}") from exc


def _load_payload(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(f"Workflow file not found: {path}")
    raw = path.read_text(encoding="utf-8")
    suffix = path.suffix.lower()
    if suffix in {".yaml", ".yml"}:
        payload = yaml.safe_load(raw)
        if payload is None:
            return {}
        if isinstance(payload, dict):
            return payload
        raise ValueError("Workflow YAML payload must be a mapping")
    if suffix == ".json":
        payload = json.loads(raw)
        if isinstance(payload, dict):
            return payload
        raise ValueError("Workflow JSON payload must be a mapping")
    raise ValueError(f"Unsupported workflow file type: {suffix}")


__all__ = ["load_workflow"]
