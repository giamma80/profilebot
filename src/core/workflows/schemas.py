"""Workflow schema models for DAG configuration."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field, model_validator


class FanoutConfig(BaseModel):
    """Configuration for fan-out execution."""

    source: str
    task: str
    parameter_name: str = "res_id"


class RetryPolicy(BaseModel):
    """Retry policy overrides for workflow nodes."""

    max_retries: int = Field(default=3, ge=0)
    countdown: int = Field(default=60, ge=0)


class WorkflowNode(BaseModel):
    """Single node definition for a workflow DAG."""

    id: str
    task: str
    depends_on: list[str] = Field(default_factory=list)
    params: dict[str, Any] = Field(default_factory=dict)
    fanout: FanoutConfig | None = None
    retry_policy: RetryPolicy | None = None


class WorkflowDefinition(BaseModel):
    """Top-level workflow definition."""

    version: int = 1
    workflow_id: str
    schedule: str | None = None
    best_effort_chord: bool = False
    min_success_ratio: float = Field(default=0.8, ge=0.0, le=1.0)
    nodes: list[WorkflowNode]

    @model_validator(mode="after")
    def _validate_nodes(self) -> WorkflowDefinition:
        if not self.nodes:
            raise ValueError("Workflow nodes must not be empty")
        node_ids = [node.id for node in self.nodes]
        if len(node_ids) != len(set(node_ids)):
            raise ValueError("Workflow node IDs must be unique")
        node_id_set = set(node_ids)
        missing = {
            dependency
            for node in self.nodes
            for dependency in node.depends_on
            if dependency not in node_id_set
        }
        if missing:
            raise ValueError(f"Unknown workflow dependencies: {sorted(missing)}")
        return self


__all__ = [
    "FanoutConfig",
    "RetryPolicy",
    "WorkflowDefinition",
    "WorkflowNode",
]
