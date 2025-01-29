# *****************************************************************************
#
# This program is free software; you can redistribute it and/or modify it under
# the terms of the GNU General Public License as published by the Free Software
# Foundation; either version 2 of the License, or (at your option) any later
# version.
#
# This program is distributed in the hope that it will be useful, but WITHOUT
# ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS
# FOR A PARTICULAR PURPOSE.  See the GNU General Public License for more
# details.
#
# You should have received a copy of the GNU General Public License along with
# this program; if not, write to the Free Software Foundation, Inc.,
# 59 Temple Place, Suite 330, Boston, MA  02111-1307  USA
#
# Module authors:
#   Markus Zolliker <markus.zolliker@psi.ch>
#
# *****************************************************************************
"""tests for probable implementation errors."""

import sys
import importlib
from glob import glob
import pytest
from frappy.core import Module, Drivable
from frappy.errors import ProgrammingError


all_drivables = set()
for pyfile in glob('frappy_*/*.py') + glob('frappy/*.py'):
    module = pyfile[:-3].replace('/', '.')
    try:
        importlib.import_module(module)
    except Exception as e:
        print(module, e)
        continue
    for obj_ in sys.modules[module].__dict__.values():
        if isinstance(obj_, type) and issubclass(obj_, Drivable):
            all_drivables.add(obj_)


@pytest.mark.parametrize('modcls', all_drivables)
def test_stop_doc(modcls):
    # make sure that implemented stop methods have a doc string
    if (modcls.stop.description == Drivable.stop.description
            and modcls.stop.func != Drivable.stop.func):
        assert modcls.stop.func.__doc__  # stop method needs a doc string


def test_bad_method_test():
    with pytest.raises(ProgrammingError):
        class Mod1(Module):  # pylint: disable=unused-variable
            def read_param(self):
                pass

    with pytest.raises(ProgrammingError):
        class Mod2(Module):  # pylint: disable=unused-variable
            def write_param(self):
                pass

    with pytest.raises(ProgrammingError):
        class Mod3(Module):  # pylint: disable=unused-variable
            def do_cmd(self):
                pass

    # no complain in this case
    # checking this would make code to check much more complicated.
    # in the rare cases used it might even be intentional
    class Mixin:
        def read_param(self):
            pass

    class ModTest(Mixin, Module):  # pylint: disable=unused-variable
        pass
