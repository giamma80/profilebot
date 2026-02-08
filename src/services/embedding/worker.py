"""Celery worker entrypoint for ProfileBot embedding jobs."""

from __future__ import annotations

import logging

from src.services.embedding.celery_app import celery_app

logger = logging.getLogger(__name__)


def main() -> int:
    """Start the Celery worker process."""
    argv = [
        "worker",
        "-l",
        "info",
        "-A",
        "src.services.embedding.celery_app",
    ]
    logger.info("Starting Celery worker with args: %s", argv)
    celery_app.worker_main(argv)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
