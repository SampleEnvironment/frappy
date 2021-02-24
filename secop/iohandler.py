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
"""IO handler

Utility class for cases, where multiple parameters are treated with a common command,
or in cases, where IO can be parametrized.
The support for LakeShore and similar protocols is already included.

For read, instead of the methods read_<parameter> we write one method analyze_<group>
for all parameters with the same handler. Before analyze_<group> is called, the
reply is parsed and converted to values, which are then given as arguments.

def analyze_<group>(self, value1, value2, ...):
    # here we have to calculate parameters from the values (value1, value2 ...)
    # and return a dict with parameter names as keys and new values.

It is an error to have a read_<parameter> method implemented on a parameter with a
handler.

For write, instead of the methods write_<parameter>" we write one method change_<group>
for all parameters with the same handler.

def change_<group>(self, change):
    # Change contains the to be changed parameters as attributes, and also the unchanged
    # parameters taking part to the handler group. If the method needs the current values
    # from the hardware, it can read them with change.getValues(). This call does also
    # update the values of the attributes of change, which are not subject to change.
    # In addtion, the method may call change.toBeChanged(<parameter name>) to determine,
    # whether a specific parameter is subject to change.
    # The return value must be either a sequence of values to be written to the hardware,
    # which will be formatted by the handler, or None. The latter is used only in some
    # special cases, when nothing has to be written.

A write_<parameter> method may be implemented in addition. In that case, the handlers write
method has to be called explicitly int the write_<parameter> method, if needed.
"""
import re

from secop.errors import ProgrammingError
from secop.modules import Done


class CmdParser:
    """helper for parsing replies

    using a subset of old style python formatting.
    The same format can be used for formatting command arguments
    """

    # make a map of cast functions
    CAST_MAP = {letter: cast
                for letters, cast in (
                    ('d', int),
                    ('s', str),  # 'c' is treated separately
                    ('o', lambda x: int(x, 8)),
                    ('xX', lambda x: int(x, 16)),
                    ('eEfFgG', float),
                ) for letter in letters}
    # pattern for characters to be escaped
    ESC_PAT = re.compile(r'([\|\^\$\-\.\+\*\?\(\)\[\]\{\}\<\>])')
    # format pattern
    FMT_PAT = re.compile('(%%|%[^diouxXfFgGeEcrsa]*(?:.|$))')

    def __init__(self, argformat):
        self.fmt = argformat
        spl = self.FMT_PAT.split(argformat)
        spl_iter = iter(spl)

        def escaped(text):
            return self.ESC_PAT.sub(lambda x: '\\' + x.group(1), text)

        casts = []
        # the first item in spl is just plain text
        pat = [escaped(next(spl_iter))]
        todofmt = None  # format set aside to be treated in next loop

        # loop over found formats and separators
        for fmt, sep in zip(spl_iter, spl_iter):
            if fmt == '%%':
                if todofmt is None:
                    pat.append('%' + escaped(sep))  # plain text
                    continue
                fmt = todofmt
                todofmt = None
                sep = '%' + sep
            elif todofmt:
                raise ValueError("a separator must follow '%s'" % todofmt)
            cast = self.CAST_MAP.get(fmt[-1], None)
            if cast is None:  # special or unknown case
                if fmt != '%c':
                    raise ValueError("unsupported format: '%s'" % fmt)
                # we do not need a separator after %c
                pat.append('(.)')
                casts.append(str)
                pat.append(escaped(sep))
                continue
            if sep == '':  # missing separator. postpone handling for '%%' case or end of pattern
                todofmt = fmt
                continue
            casts.append(cast)
            # accepting everything up to a separator
            pat.append('([^%s]*)' % escaped(sep[0]) + escaped(sep))
        if todofmt:
            casts.append(cast)
            pat.append('(.*)')
        self.casts = casts
        self.pat = re.compile(''.join(pat))
        try:
            argformat % ((0,) * len(casts))  # validate argformat
        except ValueError as e:
            raise ValueError("%s in %r" % (e, argformat))

    def format(self, *values):
        return self.fmt % values

    def parse(self, reply):
        match = self.pat.match(reply)
        if not match:
            raise ValueError('reply "%s" does not match pattern "%s"' % (reply, self.fmt))
        return [c(v) for c, v in zip(self.casts, match.groups())]


class Change:
    """contains new values for the call to change_<group>

    A Change instance is used as an argument for the change_<group> method.
    Getting the value of change.<parameter> returns either the new, changed value or the
    current one from the module, if there is no new value.
    """
    def __init__(self, handler, module, valuedict):
        self._handler = handler
        self._module = module
        self._valuedict = valuedict
        self._to_be_changed = set(self._valuedict)
        self._reply = None

    def __getattr__(self, key):
        """return attribute from module key is not in self._valuedict"""
        if key in self._valuedict:
            return self._valuedict[key]
        return getattr(self._module, key)

    def doesInclude(self, *args):
        """check whether one of the specified parameters is to be changed"""
        return bool(set(args) & self._to_be_changed)

    def readValues(self):
        """read values from the hardware

        and update our parameter attributes accordingly (i.e. do not touch the new values)
        """
        if self._reply is None:
            self._reply = self._handler.send_command(self._module)
            result = self._handler.analyze(self._module, *self._reply)
            result.update(self._valuedict)
            self._valuedict.update(result)
        return self._reply


class IOHandlerBase:
    """abstract IO handler

    IO handlers for parametrized access should inherit from this
    """

    def get_read_func(self, modclass, pname):
        """get the read function for parameter pname"""
        raise NotImplementedError

    def get_write_func(self, pname):
        """get the write function for parameter pname"""
        raise NotImplementedError


class IOHandler(IOHandlerBase):
    """IO handler for cases, where multiple parameters are treated with a common command

    This IO handler works for a syntax, where the reply of a query command has
    the same format as the arguments for the change command.
    Examples: devices from LakeShore, PPMS

    :param group:     the handler group (used for analyze_<group> and change_<group>)
    :param querycmd:  the command for a query, may contain named formats for cmdargs
    :param replyfmt:  the format for reading the reply with some scanf like behaviour
    :param changecmd: the first part of the change command (without values), may be
                         omitted if no write happens
    """
    CMDARGS = []  #: list of properties or parameters to be used for building some of the the query and change commands
    CMDSEPARATOR = None  #: if not None, it is possible to join a command and a query with the given separator

    def __init__(self, group, querycmd, replyfmt, changecmd=None):
        """initialize the IO handler

        group:     the handler group (used for analyze_<group> and change_<group>)
        querycmd:  the command for a query, may contain named formats for cmdargs
        replyfmt:  the format for reading the reply with some scanf like behaviour
        changecmd: the first part of the change command (without values), may be
                   omitted if no write happens
        """
        self.group = group
        self.parameters = set()
        self._module_class = None
        self.querycmd = querycmd
        self.replyfmt = CmdParser(replyfmt)
        self.changecmd = changecmd

    def parse_reply(self, reply):
        """return values from a raw reply"""
        return self.replyfmt.parse(reply)

    def make_query(self, module):
        """make a query"""
        return self.querycmd % {k: getattr(module, k, None) for k in self.CMDARGS}

    def make_change(self, module, *values):
        """make a change command"""
        changecmd = self.changecmd % {k: getattr(module, k, None) for k in self.CMDARGS}
        return changecmd + self.replyfmt.format(*values)

    def send_command(self, module, changecmd=''):
        """send a command (query or change+query) and parse the reply into a list

        If changecmd is given, it is prepended before the query. changecmd must
        contain the command separator at the end.
        """
        querycmd = self.make_query(module)
        reply = module.sendRecv(changecmd + querycmd)
        return self.parse_reply(reply)

    def send_change(self, module, *values):
        """compose and send a command from values

        and send a query afterwards, or combine with a query command.
        Override this method, if the change command already includes a reply.
        """
        changecmd = self.make_change(module, *values)
        if self.CMDSEPARATOR is None:
            module.sendRecv(changecmd)  # ignore result
            return self.send_command(module)
        return self.send_command(module, changecmd + self.CMDSEPARATOR)

    def get_read_func(self, modclass, pname):
        """returns the read function passed to the metaclass

        and registers the parameter in this handler
        """
        self._module_class = self._module_class or modclass
        if self._module_class != modclass:
            raise ProgrammingError("the handler '%s' for '%s.%s' is already used in module '%s'"
                                   % (self.group, modclass.__name__, pname, self._module_class.__name__))
        # self.change might be needed even when get_write_func was not called
        self.change = getattr(self._module_class, 'change_' + self.group, None)
        self.parameters.add(pname)
        self.analyze = getattr(modclass, 'analyze_' + self.group)
        return self.read

    def read(self, module):
        # read values from module
        assert module.__class__ == self._module_class
        try:
            # do a read of the current hw values
            reply = self.send_command(module)
            # convert them to parameters
            result = self.analyze(module, *reply)
            for pname, value in result.items():
                setattr(module, pname, value)
            for pname in self.parameters:
                if module.parameters[pname].readerror:
                    # clear errors on parameters, which were not updated.
                    # this will also inform all activated clients
                    setattr(module, pname, getattr(module, pname))
        except Exception as e:
            # set all parameters of this handler to error
            for pname in self.parameters:
                module.announceUpdate(pname, None, e)
            raise
        return Done

    def get_write_func(self, pname):
        """returns the write function passed to the metaclass

        :param pname: the parameter name

        May be overriden to return None, if not used
        """

        def wfunc(module, value, hdl=self, pname=pname):
            hdl.write(module, pname, value)
            return Done

        return wfunc

    def write(self, module, pname, value):
        # write value to parameter pname of the module
        assert module.__class__ == self._module_class
        force_read = False
        valuedict = {pname: value}
        if module.writeDict:  # collect other parameters to be written
            for p in self.parameters:
                if p in module.writeDict:
                    valuedict[p] = module.writeDict.pop(p)
                elif p not in valuedict:
                    force_read = True
        change = Change(self, module, valuedict)
        if force_read:
            change.readValues()
        values = self.change(module, change)
        if values is None:  # this indicates that nothing has to be written
            return
        # send the change command and a query command
        reply = self.send_change(module, *values)
        result = self.analyze(module, *reply)
        for k, v in result.items():
            setattr(module, k, v)
