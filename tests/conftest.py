import pytest


@pytest.fixture
def anyio_backend() -> str:
    """Run async tests marked with @pytest.mark.anyio on asyncio only."""
    return "asyncio"
