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
"""Define SECoP Messages"""
from __future__ import print_function

# allowed actions:

IDENTREQUEST = u'*IDN?'  # literal
# literal! first part is fixed!
IDENTREPLY = u'SINE2020&ISSE,SECoP,V2018-11-07,v1.0\\beta'

DESCRIPTIONREQUEST = u'describe'  # literal
DESCRIPTIONREPLY = u'describing'  # +<id> +json

ENABLEEVENTSREQUEST = u'activate'  # literal + optional spec
ENABLEEVENTSREPLY = u'active'  # literal + optional spec, is end-of-initial-data-transfer

DISABLEEVENTSREQUEST = u'deactivate'  # literal + optional spec
DISABLEEVENTSREPLY = u'inactive'  # literal + optional spec

COMMANDREQUEST = u'do'  # +module:command +json args (if needed)
# +module:command +json args (if needed) # send after the command finished !
COMMANDREPLY = u'done'

# +module[:parameter] +json_value
WRITEREQUEST = u'change'
# +module[:parameter] +json_value # send with the read back value
WRITEREPLY = u'changed'

# +module[:parameter] +json_value
BUFFERREQUEST = u'buffer'
# +module[:parameter] +json_value # send with the read back value
BUFFERREPLY = u'buffered'

# +module[:parameter] -> NO direct reply, calls POLL internally!
POLLREQUEST = u'read'
EVENTREPLY = u'update'  # +module[:parameter] +json_value (value, qualifiers_as_dict)

HEARTBEATREQUEST = u'ping'  # +nonce_without_space
HEARTBEATREPLY = u'pong'  # +nonce_without_space

ERRORREPLY = u'error'  # +errorclass +json_extended_info

HELPREQUEST = u'help'  # literal
HELPREPLY = u'helping'  # +line number +json_text

# helper mapping to find the REPLY for a REQUEST
REQUEST2REPLY = {
    IDENTREQUEST:         IDENTREPLY,
    DESCRIPTIONREQUEST:   DESCRIPTIONREPLY,
    ENABLEEVENTSREQUEST:  ENABLEEVENTSREPLY,
    DISABLEEVENTSREQUEST: DISABLEEVENTSREPLY,
    COMMANDREQUEST:       COMMANDREPLY,
    WRITEREQUEST:         WRITEREPLY,
    BUFFERREQUEST:        BUFFERREPLY,
    POLLREQUEST:          EVENTREPLY,
    HEARTBEATREQUEST:     HEARTBEATREPLY,
    HELPREQUEST:          HELPREPLY,
}



HelpMessage = u"""Try one of the following:
            '%s' to query protocol version
            '%s' to read the description
            '%s <module>[:<parameter>]' to request reading a value
            '%s <module>[:<parameter>] value' to request changing a value
            '%s <module>[:<command>]' to execute a command
            '%s <nonce>' to request a heartbeat response
            '%s' to activate async updates
            '%s' to deactivate updates
            """ % (IDENTREQUEST, DESCRIPTIONREQUEST, POLLREQUEST,
                   WRITEREQUEST, COMMANDREQUEST, HEARTBEATREQUEST,
                   ENABLEEVENTSREQUEST, DISABLEEVENTSREQUEST)
