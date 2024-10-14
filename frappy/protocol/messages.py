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

# allowed actions:

IDENTREQUEST = '*IDN?'  # literal
# literal! first part is fixed!
IDENTPREFIX = 'ISSE&SINE2020,SECoP,'
IDENTREPLY = IDENTPREFIX + 'V2019-08-20,v1.0 RC2'

DESCRIPTIONREQUEST = 'describe'  # literal
DESCRIPTIONREPLY = 'describing'  # +<id> +json

ENABLEEVENTSREQUEST = 'activate'  # literal + optional spec
ENABLEEVENTSREPLY = 'active'  # literal + optional spec, is end-of-initial-data-transfer

DISABLEEVENTSREQUEST = 'deactivate'  # literal + optional spec
DISABLEEVENTSREPLY = 'inactive'  # literal + optional spec

COMMANDREQUEST = 'do'  # +module:command +json args (if needed)
# +module:command +json args (if needed) # send after the command finished !
COMMANDREPLY = 'done'

# +module[:parameter] +json_value
WRITEREQUEST = 'change'
# +module[:parameter] +json_value # send with the read back value
WRITEREPLY = 'changed'

# +module[:parameter] -> NO direct reply, calls POLL internally!
READREQUEST = 'read'
READREPLY = 'reply'  # See Issue 54

EVENTREPLY = 'update'  # +module[:parameter] +json_value (value, qualifiers_as_dict)

HEARTBEATREQUEST = 'ping'  # +nonce_without_space
HEARTBEATREPLY = 'pong'  # +nonce_without_space

ERRORPREFIX = 'error_'  # + specifier + json_extended_info(error_report)

HELPREQUEST = 'help'  # literal
HELPREPLY = 'helping'  # +line number +json_text

LOGGING_REQUEST = 'logging'
LOGGING_REPLY = 'logging'
# + [module] + json string (loglevel)

LOG_EVENT = 'log'
# + [module:level] + json_string (message)

# helper mapping to find the REPLY for a REQUEST
# do not put IDENTREQUEST/IDENTREPLY here, as this needs anyway extra treatment
REQUEST2REPLY = {
    DESCRIPTIONREQUEST:   DESCRIPTIONREPLY,
    ENABLEEVENTSREQUEST:  ENABLEEVENTSREPLY,
    DISABLEEVENTSREQUEST: DISABLEEVENTSREPLY,
    COMMANDREQUEST:       COMMANDREPLY,
    WRITEREQUEST:         WRITEREPLY,
    READREQUEST:          READREPLY,
    HEARTBEATREQUEST:     HEARTBEATREPLY,
    HELPREQUEST:          HELPREPLY,
    LOGGING_REQUEST:      LOGGING_REPLY,
}


HelpMessage = f"""Try one of the following:
            '{IDENTREQUEST}' to query protocol version
            '{DESCRIPTIONREQUEST}' to read the description
            '{READREQUEST} <module>[:<parameter>]' to request reading a value
            '{WRITEREQUEST} <module>[:<parameter>] value' to request changing a value
            '{COMMANDREQUEST} <module>[:<command>]' to execute a command
            '{HEARTBEATREQUEST} <nonce>' to request a heartbeat response
            '{ENABLEEVENTSREQUEST}' to activate async updates
            '{DISABLEEVENTSREQUEST}' to deactivate updates
            '{LOGGING_REQUEST} [<module>] <loglevel>' to activate logging events
            """
