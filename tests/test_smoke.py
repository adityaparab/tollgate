"""Placeholder tests that prove the toolchain works. Replace them as real modules land."""

import anyio
import anyio.lowlevel
import pytest

import tollgate


def test_package_imports() -> None:
    assert tollgate.__name__ == "tollgate"


@pytest.mark.anyio
async def test_async_tests_run() -> None:
    await anyio.lowlevel.checkpoint()
