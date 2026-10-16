import pytest

from contra.config import load_config


@pytest.fixture(scope="session")
def cfg():
    return load_config()
