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
#   Markus Zolliker <markus.zolliker@psi.ch>
#   Alexander Zaft <a.zaft@fz-juelich.de>
#
# *****************************************************************************
"""Define helpers"""

import importlib
import linecache
import re
import socket
import sys
import threading
import traceback
from configparser import ConfigParser
from os import environ, path


SECoP_DEFAULT_PORT = 10767


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

        default values for 'piddir', 'logdir' and 'confdir' are guessed from the
        location of this source file and from sys.executable.

        if configfile is not given, the general config file is determined by
        the env. variable FRAPPY_CONFIG_FILE or <confdir>/generalConfig.cfg is used

        if a configfile is given, the values from the FRAPPY section are
        overriding above defaults

        finally, the env. variables FRAPPY_PIDDIR, FRAPPY_LOGDIR and FRAPPY_CONFDIR
        are overriding these values when given
        """
        cfg = {}
        mandatory = 'piddir', 'logdir', 'confdir'
        repodir = path.abspath(path.join(path.dirname(__file__), '..', '..'))
        # create default paths
        if (path.splitext(sys.executable)[1] == ".exe"
           and not path.basename(sys.executable).startswith('python')):
            # special MS windows environment
            self.update_defaults(piddir='./', logdir='./log', confdir='./')
        elif path.exists(path.join(repodir, 'cfg')):
            # running from git repo
            self.set_default('confdir', path.join(repodir, 'cfg'))
            # take logdir and piddir from <repodir>/cfg/generalConfig.cfg
        else:
            # running on installed system (typically with systemd)
            self.update_defaults(piddir='/var/run/frappy', logdir='/var/log', confdir='/etc/frappy')
        if configfile is None:
            configfile = environ.get('FRAPPY_CONFIG_FILE')
            if configfile:
                configfile = path.expanduser(configfile)
                if not path.exists(configfile):
                    raise FileNotFoundError(configfile)
            else:
                configfile = path.join(self['confdir'], 'generalConfig.cfg')
                if not path.exists(configfile):
                    configfile = None
        if configfile:
            parser = ConfigParser()
            parser.optionxform = str
            parser.read([configfile])
            # only the FRAPPY section is relevant, other sections might be used by others
            for key, value in parser['FRAPPY'].items():
                if value.startswith('./'):
                    cfg[key] = path.abspath(path.join(repodir, value))
                else:
                    # expand ~ to username, also in path lists separated with ':'
                    cfg[key] = ':'.join(path.expanduser(v) for v in value.split(':'))
            if cfg.get('confdir') is None:
                cfg['confdir'] = path.dirname(configfile)
        for key in mandatory:
            if (env := environ.get(f'FRAPPY_{key.upper()}')) is not None:
                cfg[key] = env
        missing_keys = [
            key for key in mandatory
            if cfg.get(key) is None and self.defaults.get(key) is None
        ]
        if missing_keys:
            if configfile:
                raise KeyError(f"missing value for {' and '.join(missing_keys)} in {configfile}")
            raise KeyError('missing %s'
                           % ' and '.join('FRAPPY_%s' % k.upper() for k in missing_keys))
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
                # e.g. 'lazy_number_validation' in frappy.datatypes
                return self.defaults[key]
            raise TypeError('generalConfig.init() has to be called first') from None

    def get(self, key, default=None):
        """access for keys not known to exist"""
        try:
            return self[key]
        except KeyError:
            return default

    def getint(self, key, default=None):
        """access and convert to int"""
        try:
            return int(self[key])
        except KeyError:
            return default

    def __getattr__(self, key):
        """goodie: use generalConfig.<key> instead of generalConfig.get('<key>')"""
        return self.get(key)

    @property
    def initialized(self):
        return bool(self._config)

    def update_defaults(self, **updates):
        """Set a default value, when there is not already one for each dict entry."""
        for key, value in updates.items():
            self.set_default(key, value)

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
    if modname.startswith('frappy'):
        module = importlib.import_module(modname)
    else:
        # rarely needed by now....
        module = importlib.import_module('frappy.' + modname)
    try:
        return getattr(module, classname)
    except AttributeError:
        raise AttributeError('no such class') from None


def mkthread(func, *args, **kwds):
    t = threading.Thread(
        name=f'{func.__module__}:{func.__name__}',
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
        item = f'  File "{filename}", line {tb.tb_lineno}, in {frame.f_code.co_name}\n'
        linecache.checkcache(filename)
        line = linecache.getline(filename, tb.tb_lineno, frame.f_globals)
        if line:
            item = item + f'    {line.strip()}\n'
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
        item = f'  File "{filename}", line {lineno}, in {name}\n'
        linecache.checkcache(filename)
        line = linecache.getline(filename, lineno, f.f_globals)
        if line:
            item = item + f'    {line.strip()}\n'
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


HOSTNAMEPART = re.compile(r'^(?!-)[a-z0-9-]{1,63}(?<!-)$', re.IGNORECASE)


def validate_hostname(host):
    """checks if the rules for valid hostnames are adhered to"""
    if len(host) > 255:
        return False
    for part in host.split('.'):
        if not HOSTNAMEPART.match(part):
            return False
    return True


def validate_ipv4(addr):
    """check if v4 address is valid."""
    try:
        socket.inet_aton(addr)
    except OSError:
        return False
    return True


def validate_ipv6(addr):
    """check if v6 address is valid."""
    try:
        socket.inet_pton(socket.AF_INET6, addr)
    except OSError:
        return False
    return True


def parse_ipv6_host_and_port(addr, defaultport=SECoP_DEFAULT_PORT):
    """ Parses IPv6 addresses with optional port. See parse_host_port for valid formats"""
    if ']' in addr:
        host, port = addr.rsplit(':', 1)
        return host[1:-1], int(port)
    if '.' in addr:
        host, port = addr.rsplit('.', 1)
        return host, int(port)
    return addr, defaultport


def parse_host_port(host, defaultport=SECoP_DEFAULT_PORT):
    """Parses hostnames and IP (4/6) addressses.

    The accepted formats are:
    - a standard hostname
    - base IPv6 or 4 addresses
    - 'hostname:port'
    - IPv4 addresses in the form of 'IPv4:port'
    - IPv6 addresses in the forms '[IPv6]:port' or 'IPv6.port'
    """
    colons = host.count(':')
    if colons == 0:  # hostname/ipv4 without port
        port = defaultport
    elif colons == 1:  # hostname or ipv4 with port
        host, port = host.split(':')
        port = int(port)
    else:  # ipv6
        host, port = parse_ipv6_host_and_port(host, defaultport)
    if (validate_ipv4(host) or validate_hostname(host) or validate_ipv6(host)) \
            and 0 < port < 65536:
        return host, port
    raise ValueError(f'invalid host {host!r} or port {port}')


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


def merge_status(*args):
    """merge status

    for combining stati of different mixins
    - the status with biggest code wins
    - texts matching maximal code are joined with ', '
    - if texts already contain ', ', it is considered as composed by
      individual texts and duplication is avoided. when commas are used
      for other purposes, the behaviour might be surprising
    """
    maxcode = max(a[0] for a in args)
    merged = [a[1] for a in args if a[0] == maxcode and a[1]]
    # use dict instead of set for preserving order
    merged = {m: True for mm in merged for m in mm.split(', ')}
    return maxcode, ', '.join(merged)


class _Raiser:
    def __init__(self, modname):
        self.modname = modname

    def __getattr__(self, name):
        # Just retry the import, it will give the most useful exception.
        __import__(self.modname)

    def __bool__(self):
        return False


def delayed_import(modname):
    """Import a module, and return an object that raises a delayed exception
    on access if it failed.
    """
    try:
        module = __import__(modname, None, None, ['*'])
    except Exception:
        return _Raiser(modname)
    return module
