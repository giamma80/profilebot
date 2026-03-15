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


def _find_signature_by_task(signature: Any, task_name: str) -> Any | None:
    stack: list[Any] = [signature]
    while stack:
        current = stack.pop()
        if current is None:
            continue
        data = (
            current
            if isinstance(current, dict)
            else {
                "task": getattr(current, "task", None),
                "body": getattr(current, "body", None),
                "header": getattr(current, "header", None),
                "tasks": getattr(current, "tasks", None),
                "kwargs": getattr(current, "kwargs", None),
                "args": getattr(current, "args", None),
            }
        )
        task_value = data.get("task")
        if task_value == task_name:
            return current
        candidates: list[Any] = []
        candidates.extend([data.get("body"), data.get("header")])
        tasks = data.get("tasks")
        if isinstance(tasks, list):
            candidates.extend(tasks)
        kwargs = data.get("kwargs")
        if isinstance(kwargs, dict):
            candidates.extend([kwargs.get("body"), kwargs.get("header")])
            nested_tasks = kwargs.get("tasks")
            if isinstance(nested_tasks, list):
                candidates.extend(nested_tasks)
        args = data.get("args")
        if isinstance(args, list | tuple):
            candidates.extend(args)
        for candidate in candidates:
            if candidate is not None:
                stack.append(candidate)
    return None


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


def test_build_canvas__workflow_uses_fanout_task() -> None:
    definition = load_workflow(Path("config/workflows/res_id_workflow.yaml"))

    canvas = WorkflowRunner().build_canvas(definition)

    assert "workflow.best_effort_group" not in _collect_task_names(canvas)

    fanout_signature = _find_signature_by_task(canvas, "workflow.fanout_by_res_id")
    if fanout_signature is None and hasattr(canvas, "to_dict"):
        fanout_signature = _find_signature_by_task(canvas.to_dict(), "workflow.fanout_by_res_id")

    assert fanout_signature is not None
    fanout_kwargs = getattr(fanout_signature, "kwargs", None)
    if fanout_kwargs is None and isinstance(fanout_signature, dict):
        fanout_kwargs = fanout_signature.get("kwargs", {})
    if fanout_kwargs is None:
        fanout_kwargs = {}
    assert fanout_kwargs["fanout_task"] == "ingestion.process_res_id"
    options = fanout_kwargs.get("options") or {}
    assert "callback_task" not in options
