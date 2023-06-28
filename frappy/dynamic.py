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
# Alexander Zaft <a.zaft@fz-juelich.de>
#
# *****************************************************************************

from .core import Module

class Pinata(Module):
    """Base class for scanning conections and adding modules accordingly.

    Like a piñata. You poke it, and modules fall out.

    To use it, subclass it for your connection type and override the function
    'scanModules'. For each module you want to register, you should yield the
    modules name and its config options.
    The connection will then be scanned during server startup.
    """
    export = False

    # POKE
    def scanModules(self):
        """yield (modname, options) for each module the Pinata should create.
        Options has to include keys for class and the config for the module.
        """
        raise NotImplementedError
