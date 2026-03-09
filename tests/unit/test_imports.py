import orchestrator
from orchestrator.api.app import app


def test_package_version_present() -> None:
    assert orchestrator.__version__


def test_fastapi_app_created() -> None:
    assert app.title == "Orchestrator Kernel"
