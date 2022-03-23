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
#   Enrico Faulhaber <enrico.faulhaber@frm2.tum.de>
#
# *****************************************************************************
"""Define helpers"""

import importlib
import linecache
import socket
import sys
import threading
import traceback
from configparser import ConfigParser
from os import environ, path


class GeneralConfig:
    """generalConfig holds server configuration items

    generalConfig.init is to be called before starting the server.
    Accessing generalConfig.<key> raises an error, when generalConfig.init is
    not yet called, except when a default for <key> is set.
    For tests and for imports from client code, a module may access generalConfig
    without calling generalConfig.init before. For this, it should call
    generalConfig.set_default on import to define defaults for the needed keys.
    """

    def __init__(self):
        self._config = None
        self.defaults = {}  #: default values. may be set before or after :meth:`init`

    def init(self, configfile=None):
        """init default server configuration

        :param configfile: if present, keys and values from the [FRAPPY] section are read

        if configfile is not given, it tries to guess the location of the configfile
        or determine 'piddir', 'logdir', 'confdir' and 'basedir' from the environment.
        """
        cfg = {}
        mandatory = 'piddir', 'logdir', 'confdir'
        repodir = path.abspath(path.join(path.dirname(__file__), '..', '..'))
        # create default paths
        if path.splitext(sys.executable)[1] == ".exe" and not path.basename(sys.executable).startswith('python'):
            # special MS windows environment
            cfg.update(piddir='./', logdir='./log', confdir='./')
        elif path.exists(path.join(repodir, '.git')):
            # running from git repo
            cfg['confdir'] = path.join(repodir, 'cfg')
            # take logdir and piddir from <repodir>/cfg/generalConfig.cfg
        else:
            # running on installed system (typically with systemd)
            cfg.update(piddir='/var/run/frappy', logdir='/var/log', confdir='/etc/frappy')
        if configfile is None:
            configfile = environ.get('FRAPPY_CONFIG_FILE',
                                     path.join(cfg['confdir'], 'generalConfig.cfg'))
        if configfile and path.exists(configfile):
            parser = ConfigParser()
            parser.optionxform = str
            parser.read([configfile])
            # mandatory in a general config file:
            cfg['logdir'] = cfg['piddir'] = None
            cfg['confdir'] = path.dirname(configfile)
            # only the FRAPPY section is relevant, other sections might be used by others
            for key, value in parser['FRAPPY'].items():
                if value.startswith('./'):
                    cfg[key] = path.abspath(path.join(repodir, value))
                else:
                    # expand ~ to username, also in path lists separated with ':'
                    cfg[key] = ':'.join(path.expanduser(v) for v in value.split(':'))
        else:
            for key in mandatory:
                cfg[key] = environ.get('FRAPPY_%s' % key.upper(), cfg[key])
        missing_keys = [key for key in mandatory if cfg[key] is None]
        if missing_keys:
            if path.exists(configfile):
                raise KeyError('missing value for %s in %s' % (' and '.join(missing_keys), configfile))
            raise FileNotFoundError(configfile)
        # this is not customizable
        cfg['basedir'] = repodir
        self._config = cfg

    def __getitem__(self, key):
        """access for keys known to exist

        :param key: the key (raises an error when key is not available)
        :return: the value
        """
        try:
            return self._config[key]
        except KeyError:
            return self.defaults[key]
        except TypeError:
            if key in self.defaults:
                # accept retrieving defaults before init
                # e.g. 'lazy_number_validation' in secop.datatypes
                return self.defaults[key]
            raise TypeError('generalConfig.init() has to be called first') from None

    def get(self, key, default=None):
        """access for keys not known to exist"""
        try:
            return self.__getitem__(key)
        except KeyError:
            return default

    def getint(self, key, default=None):
        """access and convert to int"""
        try:
            return int(self.__getitem__(key))
        except KeyError:
            return default

    def __getattr__(self, key):
        """goodie: use generalConfig.<key> instead of generalConfig.get('<key>')"""
        return self.get(key)

    @property
    def initialized(self):
        return bool(self._config)

    def set_default(self, key, value):
        """set a default value, in case not set already"""
        if key not in self.defaults:
            self.defaults[key] = value

    def testinit(self, **kwds):
        """for test purposes"""
        self._config = kwds


generalConfig = GeneralConfig()


class lazy_property:
    """A property that calculates its value only once."""

    def __init__(self, func):
        self._func = func
        self.__name__ = func.__name__
        self.__doc__ = func.__doc__

    def __get__(self, obj, obj_class):
        if obj is None:
            return self
        obj.__dict__[self.__name__] = self._func(obj)
        return obj.__dict__[self.__name__]


class attrdict(dict):
    """a normal dict, providing access also via attributes"""

    def __getattr__(self, key):
        return self[key]

    def __setattr__(self, key, value):
        self[key] = value


def clamp(_min, value, _max):
    """return the median of 3 values,

    i.e. value if min <= value <= max, else min or max depending on which side
    value lies outside the [min..max] interval. This works even when min > max!
    """
    # return median, i.e. clamp the the value between min and max
    return sorted([_min, value, _max])[1]


def get_class(spec):
    """loads a class given by string in dotted notation (as python would do)"""
    modname, classname = spec.rsplit('.', 1)
    if modname.startswith('secop'):
        module = importlib.import_module(modname)
    else:
        # rarely needed by now....
        module = importlib.import_module('secop.' + modname)
    try:
        return getattr(module, classname)
    except AttributeError:
        raise AttributeError('no such class') from None


def mkthread(func, *args, **kwds):
    t = threading.Thread(
        name='%s:%s' % (func.__module__, func.__name__),
        target=func,
        args=args,
        kwargs=kwds)
    t.daemon = True
    t.start()
    return t


def formatExtendedFrame(frame):
    ret = []
    for key, value in frame.f_locals.items():
        try:
            valstr = repr(value)[:256]
        except Exception:
            valstr = '<cannot be displayed>'
        ret.append('        %-20s = %s\n' % (key, valstr))
    ret.append('\n')
    return ret


def formatExtendedTraceback(exc_info=None):
    if exc_info is None:
        etype, value, tb = sys.exc_info()
    else:
        etype, value, tb = exc_info
    ret = ['Traceback (most recent call last):\n']
    while tb is not None:
        frame = tb.tb_frame
        filename = frame.f_code.co_filename
        item = '  File "%s", line %d, in %s\n' % (filename, tb.tb_lineno,
                                                  frame.f_code.co_name)
        linecache.checkcache(filename)
        line = linecache.getline(filename, tb.tb_lineno, frame.f_globals)
        if line:
            item = item + '    %s\n' % line.strip()
        ret.append(item)
        if filename not in ('<script>', '<string>'):
            ret += formatExtendedFrame(tb.tb_frame)
        tb = tb.tb_next
    ret += traceback.format_exception_only(etype, value)
    return ''.join(ret).rstrip('\n')


def formatExtendedStack(level=1):
    f = sys._getframe(level)
    ret = ['Stack trace (most recent call last):\n\n']
    while f is not None:
        lineno = f.f_lineno
        co = f.f_code
        filename = co.co_filename
        name = co.co_name
        item = '  File "%s", line %d, in %s\n' % (filename, lineno, name)
        linecache.checkcache(filename)
        line = linecache.getline(filename, lineno, f.f_globals)
        if line:
            item = item + '    %s\n' % line.strip()
        ret.insert(1, item)
        if filename != '<script>':
            ret[2:2] = formatExtendedFrame(f)
        f = f.f_back
    return ''.join(ret).rstrip('\n')


def formatException(cut=0, exc_info=None, verbose=False):
    """Format an exception with traceback, but leave out the first `cut`
    number of frames.
    """
    if verbose:
        return formatExtendedTraceback(exc_info)
    if exc_info is None:
        typ, val, tb = sys.exc_info()
    else:
        typ, val, tb = exc_info
    res = ['Traceback (most recent call last):\n']
    tbres = traceback.format_tb(tb, sys.maxsize)
    res += tbres[cut:]
    res += traceback.format_exception_only(typ, val)
    return ''.join(res)


def parseHostPort(host, defaultport):
    """Parse host[:port] string and tuples

    Specify 'host[:port]' or a (host, port) tuple for the mandatory argument.
    If the port specification is missing, the value of the defaultport is used.
    """

    if isinstance(host, (tuple, list)):
        host, port = host
    elif ':' in host:
        host, port = host.rsplit(':', 1)
        port = int(port)
    else:
        port = defaultport
    assert 0 < port < 65536
    assert ':' not in host
    return host, port


def tcpSocket(host, defaultport, timeout=None):
    """Helper for opening a TCP client socket to a remote server.

    Specify 'host[:port]' or a (host, port) tuple for the mandatory argument.
    If the port specification is missing, the value of the defaultport is used.
    If timeout is set to a number, the timout of the connection is set to this
    number, else the socket stays in blocking mode.
    """
    host, port = parseHostPort(host, defaultport)

    # open socket and set options
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    if timeout:
        s.settimeout(timeout)
    # connect
    s.connect((host, int(port)))
    return s


# keep a reference to socket to avoid (interpreter) shut-down problems
def closeSocket(sock, socket=socket):  # pylint: disable=redefined-outer-name
    """Do our best to close a socket."""
    if sock is None:
        return
    try:
        sock.shutdown(socket.SHUT_RDWR)
    except socket.error:
        pass
    try:
        sock.close()
    except socket.error:
        pass


def getfqdn(name=''):
    """Get fully qualified hostname."""
    return socket.getfqdn(name)


def formatStatusBits(sword, labels, start=0):
    """Return a list of labels according to bit state in `sword` starting
    with bit `start` and the first label in `labels`.
    """
    result = []
    for i, lbl in enumerate(labels, start):
        if sword & (1 << i) and lbl:
            result.append(lbl)
    return result


class UniqueObject:
    def __init__(self, name):
        self.name = name

    def __repr__(self):
        return self.name
