"""Basic tests to verify CI pipeline works."""




def test_import_src():
    """Test that src package can be imported."""
    import src

    assert src.__version__ == "0.1.0"


def test_import_api():
    """Test that api module can be imported."""
    from src import api

    assert api is not None


def test_import_core():
    """Test that core module can be imported."""
    from src import core

    assert core is not None


def test_import_services():
    """Test that services module can be imported."""
    from src import services

    assert services is not None


def test_import_utils():
    """Test that utils module can be imported."""
    from src import utils

    assert utils is not None


class TestProfileBotSetup:
    """Test class for ProfileBot setup verification."""

    def test_project_structure(self):
        """Verify basic project structure exists."""
        import src.api
        import src.core
        import src.services
        import src.utils

        assert all(
            [
                src.api is not None,
                src.core is not None,
                src.services is not None,
                src.utils is not None,
            ]
        )

    def test_version_format(self):
        """Test version string format."""
        import src

        version_parts = src.__version__.split(".")
        assert len(version_parts) == 3
        assert all(part.isdigit() for part in version_parts)
