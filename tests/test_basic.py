"""Basic tests to verify CI pipeline works."""

import src
from src import api, core, services, utils


def test_import_src():
    """Test that src package can be imported."""
    assert src.__version__ == "0.1.0"


def test_import_api():
    """Test that api module can be imported."""
    assert api is not None


def test_import_core():
    """Test that core module can be imported."""
    assert core is not None


def test_import_services():
    """Test that services module can be imported."""
    assert services is not None


def test_import_utils():
    """Test that utils module can be imported."""
    assert utils is not None


class TestProfileBotSetup:
    """Test class for ProfileBot setup verification."""

    def test_project_structure(self):
        """Verify basic project structure exists."""
        assert all(
            [
                api is not None,
                core is not None,
                services is not None,
                utils is not None,
            ]
        )

    def test_version_format(self):
        """Test version string format."""
        version_parts = src.__version__.split(".")
        assert len(version_parts) == 3
        assert all(part.isdigit() for part in version_parts)
