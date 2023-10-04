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
"""Define Mixin Features for real Modules implemented in the server"""


from frappy.datatypes import FloatRange
from frappy.core import Feature, PersistentParam


class HasOffset(Feature):
    """has a client side offset parameter

    this is just a storage!
    """
    offset = PersistentParam('offset (physical value + offset = HW value)',
                             FloatRange(unit='$'), readonly=False, default=0)
