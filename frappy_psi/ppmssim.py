#!/usr/bin/env python
#  -*- coding: utf-8 -*-
# *****************************************************************************
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
# *****************************************************************************
import json
import math
import time


def num(string):
    return json.loads(string)


class NamedList:
    def __init__(self, keys, *args, **kwargs):
        self.__keys__ = keys.split()
        self.setvalues(args)
        for key, val in kwargs.items():
            setattr(self, key, val)

    def setvalues(self, values):
        for key, arg in zip(self.__keys__, values):
            setattr(self, key, arg)

    def aslist(self):
        return [getattr(self, key) for key in self.__keys__]

    def __getitem__(self, index):
        return getattr(self, self.__keys__[index])

    def __setitem__(self, index, value):
        return setattr(self, self.__keys__[index], value)

    def __repr__(self):
        return ",".join(f"{val:.7g}" for val in self.aslist())


class PpmsSim:
    CHANNELS = {
        0: 'st', 1: 't', 2: 'mf', 3: 'pos', 4: 'r1', 5: 'i1', 6: 'r2', 7: 'i2',
        23: 'ts',
    }

    def __init__(self):
        self.status = NamedList('t mf ch pos', 1, 1, 1, 1)
        self.st = 0x1111
        self.t = 15
        self.temp = NamedList('target ramp amode', 200., 1, 0, fast=self.t, delay=10)
        self.mf = 100
        self.field = NamedList('target ramp amode pmode', 0, 50, 0, 0)
        self.pos = 0
        self.move = NamedList('target mode code', 0, 0, 0)
        self.chamber = NamedList('target', 0)
        self.level = NamedList('value code', 100.0, 1)
        self.bridge1 = NamedList('no exc pow dc mode vol', 1, 333, 1000, 0, 2, 1)
        self.bridge2 = NamedList('no exc pow dc mode vol', 2, 333, 1000, 0, 2, 1)
        self.bridge3 = NamedList('no exc pow dc mode vol', 3, 333, 1000, 0, 2, 1)
        self.bridge4 = NamedList('no exc pow dc mode vol', 4, 333, 1000, 0, 2, 1)
        self.drvout1 = NamedList('no cur pow', 1, 333, 1000)
        self.drvout2 = NamedList('no cur pow', 2, 333, 1000)
        self.r1 = 0
        self.i1 = 0
        self.r2 = 0
        self.i2 = 0
        self.ts = self.t + 0.1
        self.time = int(time.time())
        self.start = self.time
        self.mf_start = 0
        self.ch_start = 0
        self.t_start = 0
        self.changed = set()

    def progress(self):
        now = time.time()
        if self.time >= now:
            return
        while self.time < now:
            self.time += 1
            if self.temp.amode: # no overshoot
                dif = self.temp.target - self.temp.fast
            else:
                dif = self.temp.target - self.t
            self.temp.fast += math.copysign(min(self.temp.ramp / 60.0, abs(dif)), dif)
            self.t += (self.temp.fast - self.t) / self.temp.delay

            # handle magnetic field
            if 'FIELD' in self.changed:
                self.changed.remove('FIELD')
                if self.field.target < 0:
                    self.status.mf = 15 # general error
                elif self.status.mf == 1: # persistent
                    self.mf_start = now # indicates leads are ramping
                elif self.status.mf == 3: # switch_cooling
                    self.mf_start = now
                    self.status.mf = 2 # switch_warming
                else:
                    self.status.mf = 6 + int(self.field.target < self.mf) # charging or discharging
            if self.status.mf == 1 and self.mf_start: # leads ramping
                if now > self.mf_start + abs(self.field.target) / 10000 + 5:
                    self.mf_start = now
                    self.status.mf = 2 # switch_warming
            elif self.status.mf == 2: # switch_warming
                if now > self.mf_start + 15:
                    self.status.mf = 6 + int(self.field.target < self.mf) # charging or discharging
            elif self.status.mf == 5: # driven_final
                if now > self.mf_start + 5:
                    self.mf_start = now
                    self.status.mf = 3 # switch cooling
            elif self.status.mf == 3: # switch_cooling
                if now > self.mf_start + 15:
                    self.status.mf = 1 # persistent_mode
                    self.mf_start = 0 # == no leads ramping happens
            elif self.status.mf in (6, 7): # charging, discharging
                dif = self.field.target - self.mf
                if abs(dif) < 0.01:
                    if self.field.pmode:
                        self.status.mf = 4 # driven_stable
                    else:
                        self.status.mf = 5 # driven_final
                        self.mf_last = now
                else:
                    self.mf += math.copysign(min(self.field.ramp, abs(dif)), dif)
            # print(self.mf, self.status.mf, self.field)

            dif = self.move.target - self.pos
            speed = (15 - self.move.code) * 0.8
            self.pos += math.copysign(min(speed, abs(dif)), dif)

            if 'CHAMBER' in self.changed:
                self.changed.remove('CHAMBER')
                if self.chamber.target == 0: # seal immediately
                    self.status.ch = 3 # sealed unknown
                    self.ch_start = 0
                elif self.chamber.target == 3: # pump cont.
                    self.status.ch = 8
                    self.ch_start = 0
                elif self.chamber.target == 4: # vent cont.
                    self.status.ch = 9
                    self.ch_start = 0
                elif self.chamber.target == 1: # purge and seal
                    self.status.ch = 4
                    self.ch_start = now
                elif self.chamber.target == 2: # vent and seal
                    self.status.ch = 5
                    self.ch_start = now
                elif self.chamber.target == 5: # hi vac.
                    self.status.ch = 6 # pumping down
                    self.ch_start = now
            elif self.ch_start and now > self.ch_start + 15:
                self.ch_start = 0
                if self.chamber.target == 5:
                    self.status.ch = 7 # at high vac.
                else:
                    self.status.ch = self.chamber.target

            if 'TEMP' in self.changed:
                self.changed.remove('TEMP')
                self.status.t = 2 # changing
                self.t_start = now
            elif abs(self.t - self.temp.target) < 0.1:
                if now > self.t_start + 10:
                    self.status.t = 1 # stable
                else:
                    self.status.t = 5 # within tolerance
            else:
                self.t_start = now
                if abs(self.t - self.temp.target) < 1:
                    self.status.t = 6 # outside tolerance

        if abs(self.pos - self.move.target) < 0.01:
            self.status.pos = 1
        else:
            self.status.pos = 5

        self.st = sum((self.status[i] << (i * 4) for i in range(4)))
        self.r1 = self.t * 0.1
        self.i1 = self.t % 10.0
        self.r2 = 1000 / self.t
        self.i2 = math.log(self.t)
        self.ts = self.t + 0.1
        self.level.value = 100 - (self.time - self.start) * 0.01 % 100

    def getdat(self, mask):
        mask = int(mask) & 0x8000ff  # all channels up to i2 plus ts
        output = [f'{mask}', f'{time.time() - self.start:.2f}']
        for i, chan in self.CHANNELS.items():
            if (1 << i) & mask:
                output.append(f"{getattr(self, chan):.7g}")
        return ",".join(output)


class QDevice:
    def __init__(self, classid):
        self.sim = PpmsSim()

    def send(self, command):
        self.sim.progress()
        if '?' in command:
            if command.startswith('GETDAT?'):
                mask = int(command[7:])
                result = self.sim.getdat(mask)
            else:
                name, args = command.split('?')
                name += args.strip()
                result = getattr(self.sim, name.lower()).aslist()
                result =  ",".join(f"{arg:.7g}" for arg in result)
                # print(command, '/', result)
        else:
            # print(command)
            name, args = command.split()
            args = json.loads(f"[{args}]")
            if name.startswith('BRIDGE') or name.startswith('DRVOUT'):
                name = name + str(int(args[0]))
            getattr(self.sim, name.lower()).setvalues(args)
            self.sim.changed.add(name)
            result = "OK"
        return result


def shutdown():
    pass
