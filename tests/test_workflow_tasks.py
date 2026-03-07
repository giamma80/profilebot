from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from src.core.workflows.schemas import WorkflowDefinition, WorkflowNode
from src.services.workflows import tasks as workflow_tasks


class DummyResult:
    def __init__(self, task_id: str) -> None:
        self.id = task_id


class DummyRunner:
    def __init__(self, *, app=None) -> None:
        self._app = app

    def run(self, definition: WorkflowDefinition) -> DummyResult:
        return DummyResult("root-task-id")


def test_run_scraper_workflow_task__triggers_canvas(monkeypatch) -> None:
    definition = WorkflowDefinition(
        workflow_id="workflow",
        nodes=[WorkflowNode(id="step_a", task="tasks.a")],
    )

    monkeypatch.setattr(
        workflow_tasks,
        "load_workflow",
        lambda _: definition,
        raising=True,
    )
    monkeypatch.setattr(
        workflow_tasks,
        "WorkflowRunner",
        DummyRunner,
        raising=True,
    )

    result = workflow_tasks.run_scraper_workflow_task(
        workflow_path=str(Path("config/workflows/res_id_workflow.yaml"))
    )

    assert result["status"] == "triggered"
    assert result["workflow_id"] == "workflow"
    assert result["root_task_id"] == "root-task-id"
    assert result["node_count"] == 1


class DummyGroupResult:
    def __init__(self, group_id: str, children: list[DummyResult]) -> None:
        self.id = group_id
        self.children = children


class DummySignature:
    def __init__(self, task_name: str, kwargs: dict[str, object]) -> None:
        self.task = task_name
        self.kwargs = kwargs


class DummyGroup:
    def __init__(self, signatures: list[DummySignature]) -> None:
        self._signatures = signatures

    def apply_async(self) -> DummyGroupResult:
        children = [DummyResult(f"child-{index}") for index, _ in enumerate(self._signatures)]
        return DummyGroupResult("group-123", children)


def _make_signature(task_name: str, kwargs: dict[str, object]) -> DummySignature:
    return DummySignature(task_name, kwargs)


def test_run_workflow_fanout_task__uses_cached_res_ids(monkeypatch) -> None:
    monkeypatch.setattr(
        workflow_tasks,
        "_load_fanout_res_ids",
        lambda _: [101, 202],
        raising=True,
    )
    monkeypatch.setattr(
        workflow_tasks,
        "signature",
        _make_signature,
        raising=True,
    )
    monkeypatch.setattr(
        workflow_tasks,
        "group",
        lambda signatures: DummyGroup(list(signatures)),
        raising=True,
    )

    result = workflow_tasks.run_workflow_fanout_task(
        fanout_source="redis:profilebot:scraper:inside:res_ids",
        fanout_task="tasks.child",
        fanout_parameter_name="res_id",
    )

    assert result["status"] == "triggered"
    assert result["res_ids_count"] == 2
    assert result["group_id"] == "group-123"
    assert result["child_task_ids"] == ["child-0", "child-1"]


def test_run_workflow_fanout_task__skips_when_empty(monkeypatch) -> None:
    monkeypatch.setattr(
        workflow_tasks,
        "_load_fanout_res_ids",
        lambda _: [],
        raising=True,
    )

    result = workflow_tasks.run_workflow_fanout_task(
        fanout_source="redis:profilebot:scraper:inside:res_ids",
        fanout_task="tasks.child",
        fanout_parameter_name="res_id",
    )

    assert result == {"status": "skipped", "res_ids_count": 0}


def test_run_workflow_fanout_task__invalid_source_raises_value_error() -> None:
    with pytest.raises(ValueError, match="Unsupported fanout source"):
        workflow_tasks.run_workflow_fanout_task(
            fanout_source="http:profilebot:scraper:inside:res_ids",
            fanout_task="tasks.child",
            fanout_parameter_name="res_id",
        )


def test_run_workflow_fanout_task__empty_source_key_raises_value_error() -> None:
    with pytest.raises(ValueError, match="Fanout source key is required"):
        workflow_tasks.run_workflow_fanout_task(
            fanout_source="redis:",
            fanout_task="tasks.child",
            fanout_parameter_name="res_id",
        )


class DummyBestEffortChild:
    def __init__(self, value: Any) -> None:
        self._value = value

    def get(self, *, propagate: bool = False) -> Any:
        return self._value


class DummyBestEffortGroupResult:
    def __init__(self, results: list[DummyBestEffortChild]) -> None:
        self.results = results


def test_collect_best_effort_results__all_success__returns_results() -> None:
    group_result = DummyBestEffortGroupResult(
        [DummyBestEffortChild({"ok": True}), DummyBestEffortChild({"ok": True})]
    )
    results, errors = workflow_tasks._collect_best_effort_results(
        group_result,
        [
            {"task_name": "tasks.a", "res_id": 10},
            {"task_name": "tasks.b", "res_id": 20},
        ],
    )

    assert len(results) == 2
    assert errors == []


def test_collect_best_effort_results__with_failure__returns_errors() -> None:
    group_result = DummyBestEffortGroupResult(
        [DummyBestEffortChild(RuntimeError("boom")), DummyBestEffortChild({"ok": True})]
    )
    results, errors = workflow_tasks._collect_best_effort_results(
        group_result,
        [
            {"task_name": "tasks.a", "res_id": 10},
            {"task_name": "tasks.b", "res_id": 20},
        ],
    )

    assert len(results) == 1
    assert errors == [{"task_name": "tasks.a", "res_id": 10, "error": "boom"}]


def test_compute_success_ratio__below_threshold__returns_expected_ratio() -> None:
    ratio = workflow_tasks._compute_success_ratio(1, 3)

    assert ratio == pytest.approx(1 / 3)


def test_compute_success_ratio__all_failed__returns_zero() -> None:
    ratio = workflow_tasks._compute_success_ratio(0, 2)

    assert ratio == 0.0


class DummyBestEffortReadyGroup(DummyBestEffortGroupResult):
    def ready(self) -> bool:
        return True


class DummyCallbackSignature:
    def __init__(self) -> None:
        self.called_with: dict[str, Any] | None = None

    def apply_async(
        self, args: list[Any] | None = None, kwargs: dict[str, Any] | None = None
    ) -> DummyResult:
        self.called_with = {"args": args, "kwargs": kwargs}
        return DummyResult("callback-1")


class DummyCounter:
    def __init__(self) -> None:
        self.count = 0

    def inc(self) -> None:
        self.count += 1


def test_best_effort_chord_task__partial_failure_above_threshold__triggers_callback(
    monkeypatch,
) -> None:
    group_result = DummyBestEffortReadyGroup(
        [DummyBestEffortChild(RuntimeError("boom")), DummyBestEffortChild({"ok": True})]
    )
    callback = DummyCallbackSignature()
    counter = DummyCounter()

    monkeypatch.setattr(
        workflow_tasks.GroupResult,
        "restore",
        lambda group_id, app=None: group_result,
        raising=True,
    )
    monkeypatch.setattr(workflow_tasks, "_coerce_signature", lambda _: callback, raising=True)
    monkeypatch.setattr(workflow_tasks, "CHORD_PARTIAL_FAILURES", counter, raising=True)

    result = workflow_tasks.best_effort_chord_task.run(
        header=[],
        body={"task": "tasks.body"},
        min_success_ratio=0.5,
        poll_interval=1,
        task_metadata=[
            {"task_name": "tasks.a", "res_id": 10},
            {"task_name": "tasks.b", "res_id": 20},
        ],
        group_id="group-123",
    )

    assert result["status"] == "triggered"
    assert callback.called_with is not None
    assert counter.count == 1


def test_best_effort_chord_task__below_threshold__raises(monkeypatch) -> None:
    group_result = DummyBestEffortReadyGroup(
        [DummyBestEffortChild(RuntimeError("boom")), DummyBestEffortChild({"ok": True})]
    )
    callback = DummyCallbackSignature()
    counter = DummyCounter()

    monkeypatch.setattr(
        workflow_tasks.GroupResult,
        "restore",
        lambda group_id, app=None: group_result,
        raising=True,
    )
    monkeypatch.setattr(workflow_tasks, "_coerce_signature", lambda _: callback, raising=True)
    monkeypatch.setattr(workflow_tasks, "CHORD_PARTIAL_FAILURES", counter, raising=True)

    with pytest.raises(ValueError, match="success ratio below threshold"):
        workflow_tasks.best_effort_chord_task.run(
            header=[],
            body={"task": "tasks.body"},
            min_success_ratio=0.9,
            poll_interval=1,
            task_metadata=[
                {"task_name": "tasks.a", "res_id": 10},
                {"task_name": "tasks.b", "res_id": 20},
            ],
            group_id="group-123",
        )


def test_best_effort_chord_task__all_failed__raises(monkeypatch) -> None:
    group_result = DummyBestEffortReadyGroup(
        [
            DummyBestEffortChild(RuntimeError("boom")),
            DummyBestEffortChild(RuntimeError("boom")),
        ]
    )
    callback = DummyCallbackSignature()
    counter = DummyCounter()

    monkeypatch.setattr(
        workflow_tasks.GroupResult,
        "restore",
        lambda group_id, app=None: group_result,
        raising=True,
    )
    monkeypatch.setattr(workflow_tasks, "_coerce_signature", lambda _: callback, raising=True)
    monkeypatch.setattr(workflow_tasks, "CHORD_PARTIAL_FAILURES", counter, raising=True)

    with pytest.raises(ValueError, match="success ratio below threshold"):
        workflow_tasks.best_effort_chord_task.run(
            header=[],
            body={"task": "tasks.body"},
            min_success_ratio=0.1,
            poll_interval=1,
            task_metadata=[
                {"task_name": "tasks.a", "res_id": 10},
                {"task_name": "tasks.b", "res_id": 20},
            ],
            group_id="group-123",
        )
