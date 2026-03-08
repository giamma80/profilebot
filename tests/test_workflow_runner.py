from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from src.core.workflows.loader import load_workflow
from src.core.workflows.runner import WorkflowRunner
from src.core.workflows.schemas import FanoutConfig, WorkflowDefinition, WorkflowNode


def _collect_task_names(signature: Any) -> list[str]:
    tasks = getattr(signature, "tasks", None)
    if tasks is not None:
        names: list[str] = []
        for task in tasks:
            names.extend(_collect_task_names(task))
        return names
    if isinstance(signature, dict):
        nested_tasks = signature.get("tasks")
        if isinstance(nested_tasks, list):
            nested_names: list[str] = []
            for task in nested_tasks:
                nested_names.extend(_collect_task_names(task))
            return nested_names
        task_name = signature.get("task")
        if isinstance(task_name, str):
            return [task_name]
        return []
    task_name = getattr(signature, "task", None)
    if isinstance(task_name, str):
        return [task_name]
    return []


def test_build_canvas__linear_dependencies__creates_chain() -> None:
    definition = WorkflowDefinition(
        workflow_id="workflow",
        nodes=[
            WorkflowNode(id="step_a", task="tasks.a"),
            WorkflowNode(id="step_b", task="tasks.b", depends_on=["step_a"]),
        ],
    )

    canvas = WorkflowRunner().build_canvas(definition)

    assert hasattr(canvas, "tasks")
    assert len(canvas.tasks) == 2
    assert canvas.tasks[0].task == "tasks.a"
    assert canvas.tasks[1].task == "tasks.b"


def test_build_canvas__cyclic_dependencies__raises_value_error() -> None:
    definition = WorkflowDefinition(
        workflow_id="workflow",
        nodes=[
            WorkflowNode(id="step_a", task="tasks.a", depends_on=["step_b"]),
            WorkflowNode(id="step_b", task="tasks.b", depends_on=["step_a"]),
        ],
    )

    with pytest.raises(ValueError, match="cyclic"):
        WorkflowRunner().build_canvas(definition)


def test_build_canvas__fanout_node__adds_fanout_kwargs() -> None:
    definition = WorkflowDefinition(
        workflow_id="workflow",
        nodes=[
            WorkflowNode(
                id="step_a",
                task="tasks.a",
                fanout=FanoutConfig(
                    source="redis:cache",
                    task="tasks.child",
                ),
            )
        ],
    )

    canvas = WorkflowRunner().build_canvas(definition)

    assert canvas.task == "tasks.a"
    assert canvas.kwargs["fanout_source"] == "redis:cache"
    assert canvas.kwargs["fanout_task"] == "tasks.child"
    assert canvas.kwargs["fanout_parameter_name"] == "res_id"


def test_build_canvas__workflow_includes_fanout_callback_params() -> None:
    definition = load_workflow(Path("config/workflows/res_id_workflow.yaml"))

    canvas = WorkflowRunner().build_canvas(definition)

    assert canvas.task == "workflow.best_effort_group"
    payload = canvas.kwargs.get("payload")
    assert payload is not None
    body = payload.get("body")
    assert body is not None

    fanout_signature = None
    tasks = getattr(body, "tasks", None)
    if isinstance(tasks, list):
        for task in tasks:
            if getattr(task, "task", None) == "workflow.fanout_by_res_id":
                fanout_signature = task
                break
    if fanout_signature is None and isinstance(body, dict):
        if body.get("task") == "workflow.fanout_by_res_id":
            fanout_signature = body
        else:
            nested_tasks = body.get("tasks")
            if isinstance(nested_tasks, list):
                for task in nested_tasks:
                    if isinstance(task, dict) and task.get("task") == "workflow.fanout_by_res_id":
                        fanout_signature = task
                        break

    assert fanout_signature is not None
    fanout_kwargs = getattr(fanout_signature, "kwargs", None)
    if fanout_kwargs is None and isinstance(fanout_signature, dict):
        fanout_kwargs = fanout_signature.get("kwargs", {})
    if fanout_kwargs is None:
        fanout_kwargs = {}
    options = fanout_kwargs.get("options", {})
    assert options["callback_task"] == "embedding.index_from_scraper"
    assert options["on_error_task"] == "workflow.log_failed_profiles"
