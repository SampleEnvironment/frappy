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
#   Georg Brandl <g.brandl@fz-juelich.de>
#   Alexander Zaft <a.zaft@fz-juelich.de>
#
# *****************************************************************************

"""Adapter to the existing SEOP 3He spin filter system daemon."""

from os import path

# eventually he3control
from he3d import he3cell  # pylint: disable=import-error

from frappy.core import Attached
from frappy.datatypes import ArrayOf, FloatRange, IntRange, StatusType, \
    StringType, StructOf, TupleOf
from frappy.errors import CommandRunningError
from frappy.modules import Command, Drivable, Module, Parameter, Property, \
    Readable
from frappy.rwhandler import CommonReadHandler

integral = IntRange()
floating = FloatRange()
string = StringType()

# Configuration is kept in YAML files to stay compatible to the
# traditional 3He daemon, for now.


class Cell(Module):
    """ Dummy module for creating He3Cell object in order for other modules to talk to the hardware.
        Only deals with the config, and rotating the paramlog.
    """
    config_directory = Property(
        'Directory for the YAML config files', datatype=string)

    def initModule(self):
        super().initModule()
        self.cell = he3cell.He3_cell(
            path.join(self.config_directory, 'cell.yml'))

    # Commands
    @Command(result=string)
    def raw_config_file(self):
        """return unparsed contents of yaml file"""
        with open(self.cell._He3_cell__cfg_filename, 'r', encoding='utf-8') as f:
            return str(f.read())

    @Command(string, result=string)
    def cfg_get(self, identifier):
        """Get a configuration value."""
        return str(self.cell.cfg_get(identifier))

    @Command((string, string), result=string)
    def cfg_set(self, identifier, value):
        """Set a configuration value."""
        try:
            value = int(value)
        except ValueError:
            try:
                value = float(value)
            except ValueError:
                pass
        # The type is lost during transmission.
        # Check type so the value to be set has the same type and
        # is not eg. a string where an int would be needed in the config key.
        oldty = type(self.cell.cfg_get(identifier))
        if oldty is not type(value):
            raise ValueError('Type of value to be set does not match the '
                             'value in the configuration!')
        return str(self.cell.cfg_set(identifier, value))

    @Command()
    def nmr_paramlog_rotate(self):
        """resets fitting and switches to a new logfile"""
        self.cell.nmr_paramlog_rotate()


class Afp(Readable):
    """Polarisation state of the SEOP waveplates"""

    value = Parameter('Current polarisation state of the SEOP waveplates', IntRange(0, 1))

    cell = Attached(Cell)

    def read_value(self):
        return self.cell.cell.afp_state_get()

    # Commands
    @Command(description='Flip polarization of SEOP waveplates')
    def afp_flip(self):
        self.cell.cell.afp_flip_do()
        self.read_value()


class Nmr(Readable):
    Status = Drivable.Status
    status = Parameter(datatype=StatusType(Drivable.Status))
    value = Parameter('Timestamp of last NMR', string)
    cell = Attached(Cell)

    def initModule(self):
        super().initModule()
        self.interval = 0

    def read_value(self):
        return str(self.cell.cell.nmr_timestamp_get())

    def read_status(self):
        cellstate = self.cell.cell.nmr_state_get()

        if self.cell.cell.nmr_background_check():
            status = self.Status.BUSY, 'running every %d seconds' % self.interval
        else:
            status = self.Status.IDLE, 'not running'

        # TODO: what do we do here with None and -1?
        # -> None basically indicates that the fit for the parameters did not converge
        if cellstate is None:
            return self.Status.IDLE, f'returned None, {status[1]}'
        if cellstate in (0, 1):
            return status[0], f'nmr cellstate {cellstate}, {status[1]}'
        if cellstate == -1:
            return self.Status.WARN, f'got error from cell, {status[1]}'
        return self.Status.ERROR, 'Unrecognized cellstate!'

    # Commands
    @Command()
    def nmr_do(self):
        """Triggers the NMR to run"""
        self.cell.cell.nmr_do()
        self.read_status()

    @Command()
    def bgstart(self):
        """Start background NMR"""
        if self.isBusy():
            raise CommandRunningError('backgroundNMR is already running')
        interval = self.cell.cell.cfg_get('tasks/nmr/background/interval')
        self.interval = interval
        self.cell.cell.nmr_background_start(interval)
        self.read_status()

    @Command()
    def bgstop(self):
        """Stop background NMR"""
        self.cell.cell.nmr_background_stop()
        self.read_status()

    # Commands to get large datasets we do not want directly in the NICOS cache
    @Command(result=TupleOf(ArrayOf(floating, maxlen=100000),
                ArrayOf(floating, maxlen=100000)))
    def get_processed_nmr(self):
        """Get data for processed signal."""
        val= self.cell.cell.nmr_processed_get()
        return (val['xval'], val['yval'])

    @Command(result=TupleOf(ArrayOf(floating, maxlen=100000),
                ArrayOf(floating, maxlen=100000)))
    def get_raw_nmr(self):
        """Get raw signal data."""
        val = self.cell.cell.nmr_raw_get()
        return (val['xval'], val['yval'])

    @Command(result=TupleOf(ArrayOf(floating, maxlen=100000),
                ArrayOf(floating, maxlen=100000)))
    def get_raw_spectrum(self):
        """Get the raw spectrum."""
        val = self.cell.cell.nmr_raw_spectrum_get()
        y = val['yval'][:len(val['xval'])]
        return (val['xval'], y)

    @Command(result=TupleOf(ArrayOf(floating, maxlen=100000),
                ArrayOf(floating, maxlen=100000)))
    def get_processed_spectrum(self):
        """Get the processed spectrum."""
        val = self.cell.cell.nmr_processed_spectrum_get()
        x = val['xval'][:len(val['yval'])]
        return (x, val['yval'])

    @Command(result=TupleOf(ArrayOf(string, maxlen=100),
                ArrayOf(floating, maxlen=100)))
    def get_amplitude(self):
        """Last 20 amplitude datapoints."""
        rv = self.cell.cell.nmr_paramlog_get('amplitude', 20)
        x = [ str(timestamp) for timestamp in rv['xval']]
        return (x,rv['yval'])

    @Command(result=TupleOf(ArrayOf(string, maxlen=100),
                ArrayOf(floating, maxlen=100)))
    def get_phase(self):
        """Last 20 phase datapoints."""
        val = self.cell.cell.nmr_paramlog_get('phase', 20)
        return ([str(timestamp) for timestamp in val['xval']], val['yval'])


class FitParam(Readable):
    value = Parameter('fitted value', unit='$', default=0.0)
    sigma = Parameter('variance of the fitted value', FloatRange(), default=0.0)
    param = Property('the parameter that should be accesssed',
                     StringType(), export=False)

    cell = Attached(Cell)

    @CommonReadHandler(['value', 'sigma'])
    def read_amplitude(self):
        ret = self.cell.cell.nmr_param_get(self.param)
        self.value = ret['value']
        self.sigma = ret['sigma']

    # Commands
    @Command(integral, result=StructOf(xval=ArrayOf(string),
                                       yval=ArrayOf(string)))
    def nmr_paramlog_get(self, n):
        """returns the log of the last 'n' values for this parameter"""
        return self.cell.cell.nmr_paramlog_get(self.param, n)
