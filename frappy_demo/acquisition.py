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
#   Alexander Zaft <a.zaft@fz-juelich.de>
#   Markus Zolliker <markus.zolliker@psi.ch>
#
# *****************************************************************************
import time
import random
import threading
from frappy.lib import clamp, mkthread
from frappy.core import IntRange, Parameter, ArrayOf, TupleOf, FloatRange, \
    IDLE, ERROR, BUSY
from frappy.modules import AcquisitionController, AcquisitionChannel, Acquisition
from frappy.params import Command


class AcquisitionSimulation:
    def __init__(self, keys):
        self.values = {k: 0 for k in keys}
        self.err = None
        self._stopflag = threading.Event()
        self.run_acquisition = threading.Event()
        self.lock = threading.Lock()
        self.need_reset = False
        self._thread = None
        self.start()

    def start(self):
        if self.need_reset:
            self.reset()
        if self._thread is None:
            self._thread = mkthread(self.threadfun)

    def threadfun(self):
        self.sim_interval = 1
        self.err = None
        try:
            self.__sim()
        except Exception as e:
            self.err = str(e)
            # the thread stops here, but will be restarted with the go command
            self._thread = None

    def __sim(self):
        timestamp = time.time()
        delay = 0
        while not self._stopflag.wait(delay):
            self.run_acquisition.wait()
            t = time.time()
            diff = t - timestamp
            if diff < self.sim_interval:
                delay = clamp(0.1, self.sim_interval, 10)
                continue
            delay = 0
            with self.lock:
                self.values = {k: v + max(0., random.normalvariate(4., 1.))
                               for k, v in self.values.items()}
                timestamp = t

    def reset(self):
        with self.lock:
            for key in self.values:
                self.values[key] = 0
            self.need_reset = False

    def shutdown(self):
        # unblock thread:
        self._stopflag.set()
        self.run_acquisition.set()
        if self._thread and self._thread.is_alive():
            self._thread.join()


class Controller(AcquisitionController):
    _status = None  # for sticky status values

    def init_ac(self):
        self.ac = AcquisitionSimulation(m.name for m in self.channels.values())
        self.ac.reset()
        for key, channel in self.channels.items():
            self.log.debug('register %s: %s', key, channel.name)
            channel.register_acq(self.ac)

    def initModule(self):
        super().initModule()
        self.init_ac()

    def read_status(self):
        with self.ac.lock:
            if self.ac.err:
                status = self.Status.ERROR, self.ac.err
            elif self.ac.run_acquisition.is_set():
                status = self.Status.BUSY, 'running acquisition'
            else:
                status = self._status or (self.Status.IDLE, '')
        for chan in self.channels.values():
            chan.read_status()
        return status

    def go(self):
        self.ac.start()  # restart sim thread if it failed
        self.ac.run_acquisition.set()
        self._status = None
        self.read_status()

    def hold(self):
        self.ac.run_acquisition.clear()
        self._status = IDLE, 'paused'
        self.read_status()

    def stop(self):
        self.ac.run_acquisition.clear()
        self.ac.need_reset = True
        self._status = IDLE, 'stopped'

    @Command()
    def clear(self):
        """clear all channels"""
        self.ac.reset()

    def shutdownModule(self):
        self.ac.shutdown()


class Channel(AcquisitionChannel):
    _status = None  # for sticky status values
    # activate optional parameters:
    goal = Parameter()
    goal_enable = Parameter()

    def register_acq(self, ac):
        self.ac = ac

    def read_value(self):
        with self.ac.lock:
            try:
                ret = self.ac.values[self.name]
            except KeyError:
                return -1
            if self.goal_enable and self.goal < ret:
                if self.ac.run_acquisition.is_set():
                    self.ac.run_acquisition.clear()
                    self.ac.need_reset = True
                    self._status = IDLE, 'hit goal'
            else:
                self._status = None
            return ret

    def read_status(self):
        if self.ac.err:
            return ERROR, self.ac.err
        if self.ac.run_acquisition.is_set():
            return BUSY, 'running acquisition'
        return self._status or (IDLE, '')

    @Command()
    def clear(self):
        """clear this channel"""
        with self.ac.lock:
            try:
                self.ac.values[self.name] = 0.
            except KeyError:
                pass
        self.read_value()


class SimpleAcquisition(Acquisition, Controller, Channel):
    def init_ac(self):
        self.channels = {}
        self.ac = AcquisitionSimulation([self.name])
        self.ac.reset()


class NoGoalAcquisition(Acquisition):
    _value = 0
    _deadline = 0

    def read_value(self):
        return self._value

    def read_status(self):
        if self.status[0] == BUSY:
            overtime = time.time() - self._deadline
            if overtime < 0:
                return BUSY, ''
            self.setFastPoll(False)
            self._value = overtime
            self.read_value()
        return IDLE, ''

    def go(self):
        self._value = 0
        self.status = BUSY, 'started'
        self.setFastPoll(True, 0.1)
        self._deadline = time.time() + 1
        self.read_status()


# TODO
class MatrixChannel(AcquisitionChannel):
    roi = Parameter('region of interest',
                    ArrayOf(TupleOf(IntRange(), IntRange()), 0, 1),
                    default=[], readonly=False)

    def initModule(self):
        self.data = [0.] * 128

    def read_value(self):
        # mean of data or roi
        if self.roi:
            b, e = self.roi[0]
        else:
            b, e = 0, len(self.data) - 1
        return self.data[b:e] / (e - b)

    def write_roi(self, roi):
        pass

    @Command(result=ArrayOf(FloatRange()))
    def get_data(self):
        return self.data

    # axes
    # binning
    def clear(self):
        raise NotImplementedError()
