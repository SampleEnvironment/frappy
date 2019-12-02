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
"""command handler

utility class for cases, where multiple parameters are treated with a common command.
The support for LakeShore and similar protocols is already included.
"""
import re

from secop.metaclass import Done



class CmdParser:
    """helper for parsing replies

    using a subset of old style python formatting
    the same format can be used or formatting command arguments
    """

    # make a map of cast functions
    CAST_MAP = {letter: cast
            for letters, cast in (
                ('d', int),
                ('s', str), # 'c' is treated separately
                ('o', lambda x:int(x, 8)),
                ('xX', lambda x:int(x, 16)),
                ('eEfFgG', float),
            ) for letter in letters
        }
    # pattern for chacaters to be escaped
    ESC_PAT = re.compile('([\\%s])' % '\\'.join('|^$-.+*?()[]{}<>'))
    # format pattern
    FMT_PAT = re.compile('(%%|%[^diouxXfFgGeEcrsa]*(?:.|$))')

    def __init__(self, argformat):
        # replace named patterns

        self.fmt = argformat
        spl = self.FMT_PAT.split(argformat)
        spl_iter = iter(spl)

        def escaped(text):
            return self.ESC_PAT.sub(lambda x: '\\' + x.group(1), text)

        casts = []
        # the first item in spl is just plain text
        pat = [escaped(next(spl_iter))]
        todofmt = None # format set aside to be treated in next loop

        # loop over found formats and separators
        for fmt, sep in zip(spl_iter,spl_iter):
            if fmt == '%%':
                if todofmt is None:
                    pat.append('%' + escaped(sep)) # plain text
                    continue
                fmt = todofmt
                todofmt = None
                sep = '%' + sep
            elif todofmt:
                raise ValueError("a separator must follow '%s'" % todofmt)
            cast = self.CAST_MAP.get(fmt[-1], None)
            if cast is None: # special or unknown case
                if fmt != '%c':
                    raise ValueError("unsupported format: '%s'" % fmt)
                # we do not need a separator after %c
                pat.append('(.)')
                casts.append(str)
                pat.append(escaped(sep))
                continue
            if sep == '': # missing separator. postpone handling for '%%' case or end of pattern
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
            argformat % ((0,) * len(casts)) # validate argformat
        except ValueError as e:
            raise ValueError("%s in %r" % (e, argformat))

    def format(self, *values):
        return self.fmt % values

    def parse(self, reply):
        match = self.pat.match(reply)
        if not match:
            raise ValueError('reply "%s" does not match pattern "%s"' % (reply, self.fmt))
        return [c(v) for c, v in zip(self.casts, match.groups())]


class ChangeWrapper:
    """store parameter changes before they are applied"""

    def __init__(self, module, pname, value):
        self._module = module
        setattr(self, pname, value)

    def __getattr__(self, key):
        """get values from module for unknown keys"""
        return getattr(self._module, key)

    def apply(self, module):
        """set only changed values"""
        for k, v in self.__dict__.items():
            if k != '_module' and v != getattr(module, k):
                setattr(module, k, v)

    def __repr__(self):
        return ', '.join('%s=%r' % (k, v) for k, v in self.__dict__.items() if k != '_module')



class CmdHandlerBase:
    """generic command handler"""

    # def __init__(self, group, ...):
    #     init must at least initialize self.group, which is is relevant for calling the
    # proper analyze_<group> and change_<group> methods

    def parse_reply(self, reply):
        """return values from a raw reply"""
        raise NotImplementedError

    def make_query(self, module):
        """make a query"""
        raise NotImplementedError

    def make_change(self, module, *values):
        """make a change command from values"""
        raise NotImplementedError

    def send_command(self, module, changecmd=''):
        """send a command (query or change+query) and parse the reply into a list

        If changecmd is given, it is prepended before the query.
        """
        querycmd = self.make_query(module)
        reply = module.sendRecv((changecmd + querycmd))
        return self.parse_reply(reply)

    def send_change(self, module, *values):
        """compose and send a command from values

        and send a query afterwards. This method might be overriden, if the change command
        can be combined with a query command, or if the change command already includes
        a reply.
        """
        changecmd = self.make_change(module, *values)
        module.sendRecv(changecmd) # ignore result
        return self.send_command(module)

    def get_read_func(self, pname):
        """returns the read function passed to the metaclass"""
        return self.read

    def read(self, module):
        """the read function passed to the metaclass

        overwrite with None if not used
        """
        # do a read of the current hw values
        reply = self.send_command(module)
        # convert them to parameters
        getattr(module, 'analyze_' + self.group)(*reply)
        return Done # parameters should be updated already

    def get_write_func(self, pname):
        """returns the write function passed to the metaclass

        return None if not used.
        """

        def wfunc(module, value, cmd=self, pname=pname):
            # do a read of the current hw values
            values = cmd.send_command(module)
            # convert them to parameters
            analyze = getattr(module, 'analyze_' + cmd.group)
            analyze(*values)
            # create wrapper object 'new' with changed parameter 'pname'
            new = ChangeWrapper(module, pname, value)
            # call change_* for calculation new hw values
            values = getattr(module, 'change_' + cmd.group)(new, *values)
            # send the change command and a query command
            analyze(*cmd.send_change(module, *values))
            # update only changed values
            new.apply(module)
            return Done # parameter 'pname' should be changed already

        return wfunc



class CmdHandler(CmdHandlerBase):
    """more evolved command handler

    this command handler works for a syntax, where the change command syntax can be
    build from the query command syntax, with the to be changed items at the second
    part of the command, using the same format as for the reply.
    Examples: devices from LakeShore, PPMS

    implementing classes have to define/override the following:
    """
    CMDARGS = []  # list of properties or parameters to be used for building
                  # some of the the query and change commands
    CMDSEPARATOR = ';'     # if given, it is valid to join a command a a query with
                           # the given separator


    def __init__(self, group, querycmd, replyfmt):
        """initialize the command handler

        group:     the handler group (used for analyze_<group> and change_<group>)
        querycmd:  the command for a query, may contain named formats for cmdargs
        replyfmt:  the format for reading the reply with some scanf like behaviour
        """
        self.group = group
        self.querycmd = querycmd
        self.replyfmt = CmdParser(replyfmt)

    def parse_reply(self, reply):
        """return values from a raw reply"""
        return self.replyfmt.parse(reply)

    def make_query(self, module):
        """make a query"""
        return self.querycmd % {k: getattr(module, k, None) for k in self.CMDARGS}

    def make_change(self, module, *values):
        """make a change command from a query command"""
        changecmd = self.querycmd.replace('?', ' ')
        if not self.querycmd.endswith('?'):
            changecmd += ','
        changecmd %= {k: getattr(module, k, None) for k in self.CMDARGS}
        return changecmd + self.replyfmt.format(*values)

    def send_change(self, module, *values):
        """join change and query commands"""
        if self.CMDSEPARATOR is None:
            return super().send_change(module, *values)
        return self.send_command(module, self.make_change(module, *values) + self.CMDSEPARATOR)
