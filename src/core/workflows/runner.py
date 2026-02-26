"""Workflow runner that converts DAG definitions to Celery canvas."""

from __future__ import annotations

from dataclasses import dataclass

from celery import Celery, chain, group, signature
from celery.canvas import Signature
from celery.result import AsyncResult

from src.core.workflows.schemas import WorkflowDefinition, WorkflowNode


@dataclass(frozen=True)
class WorkflowRunner:
    """Runner for workflow definitions."""

    app: Celery | None = None

    def build_canvas(self, definition: WorkflowDefinition) -> Signature:
        """Build a Celery canvas from a workflow definition."""
        return _build_canvas(definition, app=self.app)

    def run(self, definition: WorkflowDefinition) -> AsyncResult:
        """Build and trigger the workflow canvas."""
        canvas = self.build_canvas(definition)
        return canvas.apply_async()


def _build_canvas(definition: WorkflowDefinition, *, app: Celery | None) -> Signature:
    levels = _topological_levels(definition)
    stages: list[Signature] = []
    for level in levels:
        signatures = [_signature_for(node, app) for node in level]
        if len(signatures) == 1:
            stages.append(signatures[0])
        else:
            stages.append(group(signatures))
    if len(stages) == 1:
        return stages[0]
    return chain(*stages)


def _topological_levels(definition: WorkflowDefinition) -> list[list[WorkflowNode]]:
    nodes_by_id = {node.id: node for node in definition.nodes}
    dependents: dict[str, set[str]] = {node_id: set() for node_id in nodes_by_id}
    in_degree = {node.id: len(node.depends_on) for node in definition.nodes}
    for node in definition.nodes:
        for dependency in node.depends_on:
            dependents[dependency].add(node.id)
    ready = sorted(node_id for node_id, count in in_degree.items() if count == 0)
    levels: list[list[WorkflowNode]] = []
    processed = 0
    while ready:
        current_ids = ready
        levels.append([nodes_by_id[node_id] for node_id in current_ids])
        processed += len(current_ids)
        next_ready: list[str] = []
        for node_id in current_ids:
            for dependent in dependents[node_id]:
                in_degree[dependent] -= 1
                if in_degree[dependent] == 0:
                    next_ready.append(dependent)
        ready = sorted(next_ready)
    if processed != len(nodes_by_id):
        raise ValueError("Workflow contains cyclic dependencies")
    return levels


def _signature_for(node: WorkflowNode, app: Celery | None) -> Signature:
    kwargs = dict(node.params)
    if node.fanout is not None:
        kwargs["fanout_source"] = node.fanout.source
        kwargs["fanout_task"] = node.fanout.task
        kwargs["fanout_parameter_name"] = node.fanout.parameter_name
    if app:
        sig = app.signature(node.task, kwargs=kwargs)
    else:
        sig = signature(node.task, kwargs=kwargs)
    if node.retry_policy:
        sig = sig.set(
            retries=node.retry_policy.max_retries,
            countdown=node.retry_policy.countdown,
        )
    return sig


__all__ = ["WorkflowRunner"]
