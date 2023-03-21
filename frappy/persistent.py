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

For hardware not keeping parameters persistent, we might want to store them in a file.

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

from frappy.lib import generalConfig
from frappy.datatypes import EnumType
from frappy.params import Parameter, Property, Command
from frappy.modules import Module


class PersistentParam(Parameter):
    persistent = Property('persistence flag (auto means: save automatically on any change)',
                          EnumType(off=0, on=1, auto=2), default=1)
    given = False


class PersistentMixin(Module):
    persistentData = None  # dict containing persistent data after startup

    def __init__(self, name, logger, cfgdict, srv):
        super().__init__(name, logger, cfgdict, srv)
        persistentdir = os.path.join(generalConfig.logdir, 'persistent')
        os.makedirs(persistentdir, exist_ok=True)
        self.persistentFile = os.path.join(persistentdir, '%s.%s.json' % (self.DISPATCHER.equipment_id, self.name))
        self.initData = {}  # "factory" settings
        loaded = self.loadPersistentData()
        for pname in self.parameters:
            pobj = self.parameters[pname]
            flag = getattr(pobj, 'persistent', False)
            if flag:
                if flag == 'auto':
                    def cb(value, m=self):
                        m.saveParameters()
                    self.valueCallbacks[pname].append(cb)
                self.initData[pname] = pobj.value
                if not pobj.given:
                    if pname in loaded:
                        pobj.value = loaded[pname]
                    if hasattr(self, 'write_' + pname):
                        # a persistent parameter should be written to HW, even when not yet in persistentData
                        self.writeDict[pname] = pobj.value
        self.__save_params()

    def loadPersistentData(self):
        try:
            with open(self.persistentFile, 'r', encoding='utf-8') as f:
                self.persistentData = json.load(f)
        except (FileNotFoundError, ValueError):
            self.persistentData = {}
        result = {}
        for pname, value in self.persistentData.items():
            try:
                pobj = self.parameters[pname]
                if getattr(pobj, 'persistent', False):
                    result[pname] = self.parameters[pname].datatype.import_value(value)
            except Exception as e:
                # ignore invalid persistent data (in case parameters have changed)
                self.log.warning('can not restore %r to %r (%r)' % (pname, value, e))
        return result

    def loadParameters(self):
        """load persistent parameters

        and write them to the HW, in case a write_<param> method is available
        may be called from a module when a hardware power down is detected
        """
        loaded = self.loadPersistentData()
        for pname, value in loaded.items():
            pobj = self.parameters[pname]
            pobj.value = value
            pobj.readerror = None
            if hasattr(self, 'write_' + pname):
                self.writeDict[pname] = value
        self.writeInitParams()
        return loaded

    def saveParameters(self):
        """save persistent parameters

        - to be called regularly explicitly by the module
        - the caller has to make sure that this is not called after
          a power down of the connected hardware before loadParameters
        """
        if self.writeDict:
            # do not save before all values are written to the hw, as potentially
            # factory default values were read in the mean time
            return
        self.__save_params()

    def __save_params(self):
        data = {k: v.export_value() for k, v in self.parameters.items()
                if getattr(v, 'persistent', False)}
        if data != self.persistentData:
            self.persistentData = data
            persistentdir = os.path.dirname(self.persistentFile)
            tmpfile = self.persistentFile + '.tmp'
            if not os.path.isdir(persistentdir):
                os.makedirs(persistentdir, exist_ok=True)
            try:
                with open(tmpfile, 'w', encoding='utf-8') as f:
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
        """reset to values from config / default values"""
        self.writeDict.update(self.initData)
        self.writeInitParams()
