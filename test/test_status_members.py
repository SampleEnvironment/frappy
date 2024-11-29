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

from frappy.core import Readable, Drivable, StatusType
from frappy_ess.epics import EpicsReadable, EpicsDrivable

readable_codes = {m.name: m.value for m in Readable.Status.members}
drivable_codes = {m.name: m.value for m in Drivable.Status.members}


def test_entangle_status():
    try:
        # pylint: disable=import-outside-toplevel
        # pylint: disable=unused-import
        import PyTango
    except ImportError:
        return

    # pylint: disable=import-outside-toplevel
    from frappy_mlz.entangle import AnalogInput, AnalogOutput, TemperatureController

    assert AnalogInput.status.datatype.members[0].export_datatype() == {
        "type": "enum",
        "members": {"UNKNOWN": StatusType.UNKNOWN,
                    "DISABLED": StatusType.DISABLED,
                    **readable_codes},
    }
    assert AnalogOutput.status.datatype.members[0].export_datatype() == {
        "type": "enum",
        "members": {"UNKNOWN": StatusType.UNKNOWN,
                    "DISABLED": StatusType.DISABLED,
                    "UNSTABLE": StatusType.UNSTABLE,
                    **drivable_codes},
    }
    assert TemperatureController.status.datatype.members[0].export_datatype() == {
        "type": "enum",
        "members": {"UNKNOWN": StatusType.UNKNOWN,
                    "DISABLED": StatusType.DISABLED,
                    "UNSTABLE": StatusType.UNSTABLE,
                    **drivable_codes},
    }


def test_epics_status():

    assert EpicsReadable.status.datatype.members[0].export_datatype() == {
        "type": "enum",
        "members": {"UNKNOWN": StatusType.UNKNOWN,
                    **readable_codes},
    }

    assert EpicsDrivable.status.datatype.members[0].export_datatype() == {
        "type": "enum",
        "members": {"UNKNOWN": StatusType.UNKNOWN,
                    **drivable_codes},
    }
