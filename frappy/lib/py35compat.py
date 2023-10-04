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
"""workaround for python versions older than 3.6

``Object`` must be inherited for classes needing support for
__init_subclass__ and __set_name__
"""


if hasattr(object, '__init_subclass__'):
    class Object:
        pass
else:
    class PEP487Metaclass(type):
        # support for __set_name__ and __init_subclass__ for older python versions
        # slightly modified from PEP487 doc
        def __new__(cls, *args, **kwargs):  # pylint: disable=bad-mcs-classmethod-argument
            if len(args) != 3:
                return super().__new__(cls, *args)
            name, bases, ns = args
            init = ns.get('__init_subclass__')
            if callable(init):
                ns['__init_subclass__'] = classmethod(init)
            newtype = super().__new__(cls, name, bases, ns)
            for k, v in newtype.__dict__.items():
                func = getattr(v, '__set_name__', None)
                if func is not None:
                    func(newtype, k)
            if bases:
                super(newtype, newtype).__init_subclass__(**kwargs)  # pylint: disable=bad-super-call
            return newtype

        def __init__(cls, name, bases, ns, **kwargs):
            super().__init__(name, bases, ns)

    class Object(metaclass=PEP487Metaclass):
        @classmethod
        def __init_subclass__(cls, *args, **kwargs):
            pass
