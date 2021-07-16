#  -*- coding: utf-8 -*-
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
"""Mixin for keeping parameters persistent

For hardware not keeping parameters persistent, we might want to store them in Frappy.

The following example will make 'param1' and 'param2' persistent, i.e. whenever
one of the parameters is changed, either by a change command or when reading back
from the hardware, it is saved to a file, and reloaded after
a power down / power up cycle. In order to make this work properly, there is a
mechanism needed to detect power down (i.e. a reading a hardware parameter
taking a special value on power up).

An additional use might be the example of a motor with an encoder which looses
the counts of how many turns already happened on power down.
This can be solved by comparing the loaded encoder value self.encoder with a
fresh value from the hardware and then adjusting the zero point accordingly.


class MyClass(PersistentMixin, ...):
    param1 = PersistentParam(...)
    param2 = PersistentParam(...)
    encoder = PersistentParam(...)

    ...

    def read_encoder(self):
        encoder = <get encoder from hardware>
        if <power down/power up cycle detected>:
            self.loadParameters()
            <fix encoder turns by comparing loaded self.encoder with encoder from hw>
        else:
            self.saveParameters()
"""

import os
import json

from secop.lib import getGeneralConfig
from secop.params import Parameter, Property, BoolType, Command
from secop.modules import HasAccessibles


class PersistentParam(Parameter):
    persistent = Property('persistence flag', BoolType(), default=True)


class PersistentMixin(HasAccessibles):
    def __init__(self, *args, **kwds):
        super().__init__(*args, **kwds)
        persistentdir = os.path.join(getGeneralConfig()['logdir'], 'persistent')
        os.makedirs(persistentdir, exist_ok=True)
        self.persistentFile = os.path.join(persistentdir, '%s.%s.json' % (self.DISPATCHER.equipment_id, self.name))
        self.initData = {}
        for pname in self.parameters:
            pobj = self.parameters[pname]
            if not pobj.readonly and getattr(pobj, 'persistent', False):
                self.initData[pname] = pobj.value
        self.writeDict.update(self.loadParameters(write=False))

    def loadParameters(self, write=True):
        """load persistent parameters

        :return: persistent parameters which have to be written

        is called upon startup and may be called from a module
        when a hardware powerdown is detected
        """
        try:
            with open(self.persistentFile, 'r') as f:
                self.persistentData = json.load(f)
        except FileNotFoundError:
            self.persistentData = {}
        writeDict = {}
        for pname in self.parameters:
            pobj = self.parameters[pname]
            if getattr(pobj, 'persistent', False) and pname in self.persistentData:
                try:
                    value = pobj.datatype.import_value(self.persistentData[pname])
                    pobj.value = value
                    if not pobj.readonly:
                        writeDict[pname] = value
                except Exception as e:
                    self.log.warning('can not restore %r to %r (%r)' % (pname, value, e))
        if write:
            self.writeDict.update(writeDict)
            self.writeInitParams()
        return writeDict

    def saveParameters(self):
        """save persistent parameters

        - to be called regularely explicitly by the module
        - the caller has to make sure that this is not called after
          a power down of the connected hardware before loadParameters
        """
        if self.writeDict:
            # do not save before all values are written to the hw, as potentially
            # factory default values were read in the mean time
            return
        data = {k: v.export_value() for k, v in self.parameters.items()
                if getattr(v, 'persistent', False)}
        if data != self.persistentData:
            self.persistentData = data
            persistentdir = os.path.basename(self.persistentFile)
            tmpfile = self.persistentFile + '.tmp'
            if not os.path.isdir(persistentdir):
                os.makedirs(persistentdir, exist_ok=True)
            try:
                with open(tmpfile, 'w') as f:
                    json.dump(self.persistentData, f, indent=2)
                    f.write('\n')
                os.rename(tmpfile, self.persistentFile)
            finally:
                try:
                    os.remove(tmpfile)
                except FileNotFoundError:
                    pass

    @Command()
    def factory_reset(self):
        self.writeDict.update(self.initData)
        self.writeInitParams()
