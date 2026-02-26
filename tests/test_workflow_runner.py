from __future__ import annotations

import pytest

from src.core.workflows.runner import WorkflowRunner
from src.core.workflows.schemas import FanoutConfig, WorkflowDefinition, WorkflowNode


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
