from pathlib import Path

from frappy.gui.cfg_editor.utils import get_modules, get_interfaces
from frappy.lib import generalConfig

basedir = Path(__file__).parent.parent.absolute()


def test_imports():
    generalConfig.testinit(basedir=basedir)

    get_modules()
    get_interfaces()
