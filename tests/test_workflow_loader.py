from __future__ import annotations

from pathlib import Path

import pytest

from src.core.workflows.loader import load_workflow


def test_load_workflow__yaml__returns_definition(tmp_path: Path) -> None:
    workflow_path = tmp_path / "workflow.yaml"
    workflow_path.write_text(
        """version: 1
workflow_id: res_id_ingestion
schedule: "0 */4 * * *"

nodes:
  - id: fetch_res_ids
    task: src.services.scraper.tasks.scraper_inside_refresh_task
""",
        encoding="utf-8",
    )

    definition = load_workflow(workflow_path)

    assert definition.workflow_id == "res_id_ingestion"
    assert definition.schedule == "0 */4 * * *"
    assert [node.id for node in definition.nodes] == ["fetch_res_ids"]


def test_load_workflow__unsupported_extension__raises_value_error(
    tmp_path: Path,
) -> None:
    workflow_path = tmp_path / "workflow.txt"
    workflow_path.write_text("{}", encoding="utf-8")

    with pytest.raises(ValueError, match="Unsupported workflow file type"):
        load_workflow(workflow_path)


def test_load_workflow__missing_file__raises_file_not_found_error(
    tmp_path: Path,
) -> None:
    workflow_path = tmp_path / "missing.yaml"

    with pytest.raises(FileNotFoundError, match="Workflow file not found"):
        load_workflow(workflow_path)
