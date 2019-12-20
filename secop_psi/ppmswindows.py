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
import threading

try:
    import pythoncom
    import win32com.client
except ImportError:
    print("This Module only works with a pythoncom module on a MS Windows OS")
    raise


class Error(Exception):
    pass


class QDevice:
    def __init__(self, classid):
        self.threadlocal = threading.local()
        self.classid = classid

    def send(self, command):
        try:
            mvu = self.threadlocal.mvu
        except AttributeError:
            pythoncom.CoInitialize()
            mvu = win32com.client.Dispatch(self.classid)
            self.threadlocal.mvu = mvu
        args = [
            win32com.client.VARIANT(pythoncom.VT_BYREF | pythoncom.VT_BSTR, command),
            win32com.client.VARIANT(pythoncom.VT_BYREF | pythoncom.VT_BSTR, ""),  # reply
            win32com.client.VARIANT(pythoncom.VT_BYREF | pythoncom.VT_BSTR, ""),  # error
            win32com.client.VARIANT(pythoncom.VT_BYREF | pythoncom.VT_I4, 0),  # ?
            win32com.client.VARIANT(pythoncom.VT_BYREF | pythoncom.VT_I4, 0)]  # ?
        err = mvu.SendPpmsCommand(*args)
        # win32com does invert the order of results!
        if err == 0:
            # print '<', args[3].value
            return args[3].value
        if err == 1:
            # print '<done'
            return "OK"
        raise Error(args[2].value.replace('\n', ' '))


if __name__ == "__main__":  # test only
    print(QDevice('QD.MULTIVU.PPMS.1').send('LEVEL?'))
