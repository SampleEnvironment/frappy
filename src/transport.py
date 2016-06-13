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
#
# *****************************************************************************

"""provides transport layer of SECoP"""

# currently implements pickling Python-objects over plain TCP
# WARNING: This is not (really) portable to other languages!

import time
import socket
import threading
import SocketServer
try:
    import cPickle as pickle
except ImportError:
    import pickle

from server import DeviceServer
from messages import ListOfFeaturesRequest

DEF_PORT = 10767
MAX_MESSAGE_SIZE = 1024

def decodeMessage(msg):
    """transport layer message -> msg object"""
    return pickle.loads(msg)

def encodeMessage(msgobj):
    """msg object -> transport layer message"""
    return pickle.dumps(msgobj)

def encodeMessageFrame(msg):
    """add transport layer encapsulation/framing of messages"""
    return '%s\n' % msg

def decodeMessageFrame(frame):
    """remove transport layer encapsulation/framing of messages"""
    if '\n' in frame:
       # WARNING: ignores everything after first '\n'
       return frame.split('\n', 1)[0]
    # invalid/incomplete frames return nothing here atm.
    return None


class SECoPClient(object):
    """connects to a SECoPServer and provides communication"""
    _socket = None
    def connect(self, server='localhost'):
        if self._socket:
            raise Exception('%r is already connected!' % self)
        if ':' not in server:
            server = '%s:%d' % (server, DEF_PORT)
        host, port = server.split(':')
        port = int(port)
        self._socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._socket.connect((host, port))
        self._negotiateServerSettings()

    def close(self):
        if not self._socket:
            raise Exception('%r is not connected!' % self)
        self._socket.close(socket.SH_RDONLY)
        self._socket.close(socket.SH_RDWR)
        self._socket = None

    def _sendRequest(self, request):
        if not self._socket:
            raise Exception('%r is not connected!' % self)
        self._socket.send(encodeMessageFrame(encodeMessage(request)))

    def _recvReply(self):
        if not self._socket:
            raise Exception('%r is not connected!' % self)
        rawdata = ''
        while True:
            data = self._socket.recv(MAX_MESSAGE_SIZE)
            if not(data):
                time.sleep(0.1)
                # XXX: needs timeout mechanism!
                continue
            rawdata = rawdata + data
            msg = decodeMessageFrame(rawdata)
            if msg:
                return decodeMessage(msg)
    
    def _negotiateServerSettings(self):
        self._sendRequest(ListOfFeaturesRequest())
        print self._recvReply()
        # XXX: fill with life!


class SECoPRequestHandler(SocketServer.BaseRequestHandler):
    def handle(self):
        """handle a new tcp-connection"""
        # self.client_address
        socket = self.request
        frame = ''
        # start serving
        while True:
            _frame = socket.recv(MAX_MESSAGE_SIZE)
            if not _frame:
                time.sleep(0.1)
                continue
            frame = frame + _frame
            msg = decodeMessageFrame(frame)
            if msg:
                requestObj = decodeMessage(msg)
                replyObj = self.handle_request(requestObj)
                self.send(encodeMessageFrame(encodeMessage(replyObj)))
                frame = ''

    def handle_request(self, requestObj):
        # XXX: handle connection/Server specific Requests
        # pass other (Device) requests to the DeviceServer
        return self.server.handle(requestObj)
        

class SECoPServer(SocketServer.ThreadingTCPServer, DeviceServer):
    daemon_threads = False

def startup_server():
    srv = SECoPServer(('localhost', DEF_PORT), SECoPRequestHandler, bind_and_activate=True)
    srv.serve_forever()
    srv.server_close()
