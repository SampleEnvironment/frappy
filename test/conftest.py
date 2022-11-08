# content of conftest.py

import pytest


@pytest.fixture(scope="module")
def constants():
    # setup
    class Constants:
        ONE = 1
        TWO = 2
    c = Constants()
    yield c
    # teardown
    del c


# pylint: disable=redefined-builtin
@pytest.fixture(scope="session")
def globals():
    return {}
