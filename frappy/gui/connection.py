#  -*- coding: utf-8 -*-
# *****************************************************************************
# Copyright (c) 2015-2016 by the authors, see LICENSE
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
#   Alexander Lenz <alexander.lenz@frm2.tum.de>
#
# *****************************************************************************

from frappy.gui.qt import QObject, pyqtSignal

import frappy.client


class QSECNode(QObject):
    newData = pyqtSignal(str, str, object)  # module, parameter, data
    stateChange = pyqtSignal(str, bool, str)  # node name, online, connection state
    unhandledMsg = pyqtSignal(str)  # message
    descriptionChanged = pyqtSignal(str, object) # contactpoint, self
    logEntry = pyqtSignal(str)

    def __init__(self, uri, parent_logger, parent=None):
        super().__init__(parent)
        self.log = parent_logger.getChild(uri)
        self.conn = conn = frappy.client.SecopClient(uri, self.log)
        conn.validate_data = True
        self.contactPoint = conn.uri
        conn.connect()
        self.equipmentId = conn.properties['equipment_id']
        self.log.info('Switching to logger %s', self.equipmentId)
        self.log.name = '.'.join((parent_logger.name, self.equipmentId))
        self.nodename = f'{self.equipmentId} ({conn.uri})'
        self.modules = conn.modules
        self.properties = self.conn.properties
        self.protocolVersion = conn.secop_version
        self.log.debug('SECoP Version: %s', conn.secop_version)
        conn.register_callback(None, self.updateItem, self.nodeStateChange,
                               self.unhandledMessage, self.descriptiveDataChange)

    # provide methods from old baseclient for making other gui code work
    def reconnect(self):
        if self.conn.online:
            self.conn.disconnect(shutdown=False)
        self.conn.connect()

    def getParameters(self, module):
        return self.modules[module]['parameters']

    def getCommands(self, module):
        return self.modules[module]['commands']

    def getModuleProperties(self, module):
        return self.modules[module]['properties']

    def getProperties(self, module, parameter):
        props = self.modules[module]['parameters'][parameter]
        if 'unit' in props['datainfo']:
            props['unit'] = props['datainfo']['unit']
        return self.modules[module]['parameters'][parameter]

    def setParameter(self, module, parameter, value):
        self.conn.setParameter(module, parameter, value)

    def getParameter(self, module, parameter):
        return self.conn.getParameter(module, parameter, True)

    def execCommand(self, module, command, argument):
        return self.conn.execCommand(module, command, argument)

    def queryCache(self, module):
        return {k: self.conn.cache[(module, k)]
                for k in self.modules[module]['parameters']}

    def syncCommunicate(self, action, ident='', data=None):
        reply = self.conn.request(action, ident, data)
        # pylint: disable=not-an-iterable
        return frappy.client.encode_msg_frame(*reply).decode('utf-8')

    def decode_message(self, msg):
        # decode_msg needs bytes as input
        return frappy.client.decode_msg(msg.encode('utf-8'))

    def _getDescribingParameterData(self, module, parameter):
        # print(module, parameter, self.modules[module]['parameters'])
        return self.modules[module]['parameters'][parameter]

    def updateItem(self, module, parameter, item):
        self.newData.emit(module, parameter, item)

    def nodeStateChange(self, online, state):
        self.stateChange.emit(self.nodename, online, state)

    def unhandledMessage(self, action, specifier, data):
        self.unhandledMsg.emit(f'{action} {specifier} {data!r}')

    def descriptiveDataChange(self, _module, conn):
        self.modules = conn.modules
        self.properties = conn.properties
        self.descriptionChanged.emit(self.contactPoint, self)

    def terminate_connection(self):
        self.conn.disconnect()
