
from frappy.gui.cfg_editor.utils import get_modules

def test_assert():
    assert 1


def test_constants(constants):
    assert constants.ONE == 1
    assert constants.TWO == 2


def test_imports():
    get_modules()
