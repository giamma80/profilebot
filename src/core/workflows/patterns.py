"""Workflow canvas patterns for resilient orchestration."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from celery import Celery, signature
from celery.canvas import Signature


@dataclass(frozen=True)
class BestEffortChord:
    """Build a best-effort chord signature for workflow orchestration."""

    app: Celery | None = None
    min_success_ratio: float = 0.8
    poll_interval: int = 5

    def build(self, header: Signature | list[Signature], body: Signature) -> Signature:
        """Create the best-effort chord signature."""
        header_tasks = _extract_header_tasks(header)
        task_metadata = [_extract_task_metadata(sig) for sig in header_tasks]
        return signature(
            "workflow.best_effort_group",
            kwargs={
                "payload": {
                    "header": header_tasks,
                    "body": body,
                    "min_success_ratio": self.min_success_ratio,
                    "poll_interval": self.poll_interval,
                    "task_metadata": task_metadata,
                }
            },
            app=self.app,
        )


def _extract_header_tasks(header: Signature | list[Signature]) -> list[Signature]:
    tasks = getattr(header, "tasks", None)
    if isinstance(tasks, list):
        return tasks
    if isinstance(header, list):
        return header
    return [header]


def _extract_task_metadata(sig: Signature) -> dict[str, Any]:
    task_name = getattr(sig, "task", None)
    kwargs = getattr(sig, "kwargs", None) or {}
    res_id = kwargs.get("res_id") if isinstance(kwargs, dict) else None
    return {"task_name": task_name, "res_id": res_id}


__all__ = ["BestEffortChord"]
