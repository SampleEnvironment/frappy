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
"""test base client."""

import pytest

import sys
sys.path.insert(0, sys.path[0] + '/..')

from collections import OrderedDict
from secop.client.baseclient import Client

# define Test-only connection object


class TestConnect(object):
    callbacks = []

    def writeline(self, line):
        pass

    def readline(self):
        return ''


@pytest.fixture(scope="module")
def clientobj(request):
    print ("  SETUP ClientObj")
    testconnect = TestConnect()
    yield Client(dict(testing=testconnect), autoconnect=False)
    for cb, arg in testconnect.callbacks:
        cb(arg)
    print ("  TEARDOWN ClientObj")


def test_describing_data_decode(clientobj):
    assert OrderedDict(
        [('a', 1)]) == clientobj._decode_list_to_ordereddict(['a', 1])
    assert {'modules': {}, 'properties': {}
            } == clientobj._decode_substruct(['modules'], {})
    describing_data = {'equipment_id': 'eid',
                       'modules': ['LN2', {'commands': [],
                                           'interfaces': ['Readable', 'Module'],
                                           'parameters': ['value', {'datatype': ['double'],
                                                                    'description': 'current value',
                                                                    'readonly': True,
                                                                    }
                                                          ]
                                           }
                                   ]
                       }
    decoded_data = {'modules': {'LN2': {'commands': {},
                                        'parameters': {'value': {'datatype': ['double'],
                                                                 'description': 'current value',
                                                                 'readonly': True,
                                                                 }
                                                       },
                                        'properties': {'interfaces': ['Readable', 'Module']}
                                        }
                                },
                    'properties': {'equipment_id': 'eid',
                                   }
                    }

    a = clientobj._decode_substruct(['modules'], describing_data)
    for modname, module in a['modules'].items():
        a['modules'][modname] = clientobj._decode_substruct(
            ['parameters', 'commands'], module)
    assert a == decoded_data
