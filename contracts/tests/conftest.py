import pytest

def pytest_configure(config):
    config.addinivalue_line(
        "markers", "db: optional tests requiring a running Docker daemon to launch a postgres:16 container"
    )
