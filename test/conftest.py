# content of conftest.py
from __future__ import division, print_function

import pytest


@pytest.fixture(scope="module")
def constants():
    # setup
    class Constants(object):
        ONE = 1
        TWO = 2
    c = Constants()
    yield c
    # teardown
    del c


@pytest.fixture(scope="session")
# pylint: disable=redefined-builtin
def globals():
    return dict()
