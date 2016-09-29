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
#   Enrico Faulhaber <enrico.faulhaber@frm2.tum.de>
# *****************************************************************************

"""playing implementation of a (simple) simulated cryostat"""

from math import atan
import time
import random
import threading

from secop.devices.core import Driveable, CONFIG, PARAM
from secop.protocol import status
from secop.validators import floatrange, positive, enum
from secop.lib import clamp


class Cryostat(Driveable):
    """simulated cryostat with:

    - heat capacity of the sample
    - cooling power
    - thermal transfer between regulation and samplen
    """
    PARAMS = dict(
        jitter=CONFIG("amount of random noise on readout values",
                      validator=floatrange(0, 1),
                      export=False,
                      ),
        T_start=CONFIG("starting temperature for simulation",
                       validator=positive, export=False,
                       ),
        looptime=CONFIG("timestep for simulation",
                        validator=positive, default=1, unit="s",
                        export=False,
                        ),
        ramp=PARAM("ramping speed in K/min",
                   validator=floatrange(0, 1e3), default=1,
                   ),
        setpoint=PARAM("ramping speed in K/min",
                       validator=float, default=1, readonly=True,
                       ),
        maxpower=PARAM("Maximum heater power in W",
                       validator=float, default=0, readonly=True, unit="W",
                       ),
        heater=PARAM("current heater setting in %",
                     validator=float, default=0, readonly=True, unit="%",
                     ),
        heaterpower=PARAM("current heater power in W",
                          validator=float, default=0, readonly=True, unit="W",
                          ),
        target=PARAM("target temperature in K",
                     validator=float, default=0, unit="K",
                     ),
        p=PARAM("regulation coefficient 'p' in %/K",
                validator=positive, default=40, unit="%/K",
                ),
        i=PARAM("regulation coefficient 'i'",
                validator=floatrange(0, 100), default=10,
                ),
        d=PARAM("regulation coefficient 'd'",
                validator=floatrange(0, 100), default=2,
                ),
        mode=PARAM("mode of regulation",
                   validator=enum('ramp', 'pid', 'openloop'), default='pid',
                   ),

        tolerance=PARAM("temperature range for stability checking",
                        validator=floatrange(0, 100), default=0.1, unit='K',
                        ),
        window=PARAM("time window for stability checking",
                     validator=floatrange(1, 900), default=30, unit='s',
                     ),
        timeout=PARAM("max waiting time for stabilisation check",
                      validator=floatrange(1, 36000), default=900, unit='s',
                      ),
    )

    def init(self):
        self._stopflag = False
        self._thread = threading.Thread(target=self.thread)
        self._thread.daemon = True
        self._thread.start()

    def read_status(self):
        # instead of asking a 'Hardware' take the value from the simulation
        return self.status

    def read_value(self, maxage=0):
        # return regulation value (averaged regulation temp)
        return self.regulationtemp + \
            self.config_jitter * (0.5 - random.random())

    def read_target(self, maxage=0):
        return self.target

    def write_target(self, value):
        self.target = value
        # next request will see this status, until the loop updates it
        self.status = (status.BUSY, 'new target set')

    def read_maxpower(self, maxage=0):
        return self.maxpower

    def write_maxpower(self, newpower):
        # rescale heater setting in % to keep the power
        heat = max(0, min(100, self.heater * self.maxpower / float(newpower)))
        self.heater = heat
        self.maxpower = newpower

    def doStop(self):
        # stop the ramp by setting current setpoint as target
        # XXX: discussion: take setpoint or current value ???
        self.write_target(self.setpoint)

    #
    # calculation helpers
    #
    def __coolerPower(self, temp):
        """returns cooling power in W at given temperature"""
        # quadratic up to 42K, is linear from 40W@42K to 100W@600K
        # return clamp((temp-2)**2 / 32., 0., 40.) + temp * 0.1
        return clamp(15 * atan(temp * 0.01) ** 3, 0., 40.) + temp * 0.1 - 0.2

    def __coolerCP(self, temp):
        """heat capacity of cooler at given temp"""
        return 75 * atan(temp / 50)**2 + 1

    def __heatLink(self, coolertemp, sampletemp):
        """heatflow from sample to cooler. may be negative..."""
        flow = (sampletemp - coolertemp) * \
               ((coolertemp + sampletemp) ** 2) / 400.
        cp = clamp(self.__coolerCP(coolertemp) * self.__sampleCP(sampletemp),
                   1, 10)
        return clamp(flow, -cp, cp)

    def __sampleCP(self, temp):
        return 3 * atan(temp / 30) + \
            12 * temp / ((temp - 12.)**2 + 10) + 0.5

    def __sampleLeak(self, temp):
        return 0.02 / temp

    def thread(self):
        self.sampletemp = self.config_T_start
        self.regulationtemp = self.config_T_start
        self.status = status.OK
        while not self._stopflag:
            try:
                self.__sim()
            except Exception as e:
                self.log.exception(e)
                self.status = status.ERROR, str(e)

    def __sim(self):
        # complex thread handling:
        # a) simulation of cryo (heat flow, thermal masses,....)
        # b) optional PID temperature controller with windup control
        # c) generating status+updated value+ramp
        # this thread is not supposed to exit!

        # local state keeping:
        regulation = self.regulationtemp
        sample = self.sampletemp
        # keep history values for stability check
        window = []
        timestamp = time.time()
        heater = 0
        lastflow = 0
        last_heaters = (0, 0)
        delta = 0
        I = D = 0
        lastD = 0
        damper = 1
        lastmode = self.mode
        while not self._stopflag:
            t = time.time()
            h = t - timestamp
            if h < self.looptime / damper:
                time.sleep(clamp(self.looptime / damper - h, 0.1, 60))
                continue
            # a)
            sample = self.sampletemp
            regulation = self.regulationtemp
            heater = self.heater

            heatflow = self.__heatLink(regulation, sample)
            self.log.debug('sample = %.5f, regulation = %.5f, heatflow = %.5g'
                           % (sample, regulation, heatflow))
            newsample = max(0,
                            sample + (self.__sampleLeak(sample) - heatflow) /
                            self.__sampleCP(sample) * h)
            # avoid instabilities due to too small CP
            newsample = clamp(newsample, sample, regulation)
            regdelta = (heater * 0.01 * self.maxpower + heatflow -
                        self.__coolerPower(regulation))
            newregulation = max(0, regulation +
                                regdelta / self.__coolerCP(regulation) * h)
            # b) see
            # http://brettbeauregard.com/blog/2011/04/
            # improving-the-beginners-pid-introduction/
            if self.mode != 'openloop':
                # fix artefacts due to too big timesteps
                # actually i would prefer reducing looptime, but i have no
                # good idea on when to increase it back again
                if heatflow * lastflow != -100:
                    if (newregulation - newsample) * (regulation - sample) < 0:
                        # newregulation = (newregulation + regulation) / 2
                        # newsample = (newsample + sample) / 2
                        damper += 1
                lastflow = heatflow

                error = self.setpoint - newregulation
                # use a simple filter to smooth delta a little
                delta = (delta + regulation - newregulation) / 2.

                kp = self.p / 10.             # LakeShore P = 10*k_p
                ki = kp * abs(self.i) / 500.  # LakeShore I = 500/T_i
                kd = kp * abs(self.d) / 2.    # LakeShore D = 2*T_d
                P = kp * error
                I += ki * error * h
                D = kd * delta / h

                # avoid reset windup
                I = clamp(I, 0., 100.)  # I is in %

                # avoid jumping heaterpower if switching back to pid mode
                if lastmode != self.mode:
                    # adjust some values upon switching back on
                    I = self.heater - P - D

                v = P + I + D
                # in damping mode, use a weighted sum of old + new heaterpower
                if damper > 1:
                    v = ((damper ** 2 - 1) * self.heater + v) / damper ** 2

                # damp oscillations due to D switching signs
                if D * lastD < -0.2:
                    v = (v + heater) / 2.
                # clamp new heater power to 0..100%
                heater = clamp(v, 0., 100.)
                lastD = D

                self.log.debug('PID: P = %.2f, I = %.2f, D = %.2f, '
                               'heater = %.2f' % (P, I, D, heater))

                # check for turn-around points to detect oscillations ->
                # increase damper
                x, y = last_heaters
                if (x + 0.1 < y and y > heater + 0.1) or \
                   (x > y + 0.1 and y + 0.1 < heater):
                    damper += 1
                last_heaters = (y, heater)

            else:
                # self.heaterpower is set manually, not by pid
                heater = self.heater
                last_heaters = (0, 0)

            heater = round(heater, 3)
            sample = newsample
            regulation = newregulation
            lastmode = self.mode
            # c)
            if self.setpoint != self.target:
                if self.ramp == 0:
                    maxdelta = 10000
                else:
                    maxdelta = self.ramp / 60. * h
                try:
                    self.setpoint = round(self.setpoint +
                                          clamp(self.target - self.setpoint,
                                                -maxdelta, maxdelta), 3)
                    self.log.debug('setpoint changes to %r (target %r)' %
                                   (self.setpoint, self.target))
                except (TypeError, ValueError):
                    # self.target might be None
                    pass

            # temperature is stable when all recorded values in the window
            # differ from setpoint by less than tolerance
            currenttime = time.time()
            window.append((currenttime, sample))
            while window[0][0] < currenttime - self.window:
                # remove old/stale entries
                window.pop(0)
            # obtain min/max
            deviation = 0
            for _, T in window:
                if abs(T - self.target) > deviation:
                    deviation = abs(T - self.target)
            if (len(window) < 3) or deviation > self.tolerance:
                self.status = status.BUSY, 'unstable'
            elif self.setpoint == self.target:
                self.status = status.OK, 'at target'
                damper -= (damper - 1) / 10.  # max value for damper is 11
            else:
                self.status = status.BUSY, 'ramping setpoint'
            damper -= (damper - 1) / 20.
            self.regulationtemp = round(regulation, 3)
            self.sampletemp = round(sample, 3)
            self.heaterpower = round(heater * self.maxpower * 0.01, 3)
            self.heater = heater
            timestamp = t

    def shutdown(self):
        # should be called from server when the server is stopped
        self._stopflag = True
        if self._thread and self._thread.isAlive():
            self._thread.join()
