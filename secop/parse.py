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
"""parser. used for config files and the gui

can't use ast.literal_eval as it can't handle enums :(

parsing rules:
(...) -> tuple
[...] -> tuple
{text:...} -> dict
{text=...} -> dict
..., ... -> tuple
digits -> float or int (try int, if it fails: take float)
text -> string
'text' -> string
"text" -> string

further convertions are done by the validator of the datatype....
"""

from collections import OrderedDict


class Parser:
    # all parsing methods return (parsed value, remaining string)
    # or (None, remaining_text) if parsing error

    def parse_number(self, text):
        text = text.strip()
        l = 1
        number = None
        while l <= len(text):
            try:
                number = float(text[:l])
                length = l
                l += 1
            except ValueError:
                if text[l - 1] in 'eE+-':
                    l += 1
                    continue
                if number is None:
                    return None, text
                try:
                    return int(text[:length]), text[length:]
                except ValueError:
                    return number, text[length:]
        return number, ''

    def parse_string(self, orgtext):
        # handle quoted and unquoted strings correctly
        text = orgtext.strip()
        if text[0] in ('"', "'"):
            # quoted string
            quote = text[0]
            idx = 0

            while True:
                idx = text.find(quote, idx + 1)
                if idx == -1:
                    return None, orgtext
                # check escapes!
                if text[idx - 1] == '\\':
                    continue
                return text[1:idx], text[idx + 1:]

        # unquoted strings are terminated by comma or whitespace
        idx = 0
        while idx < len(text):
            if text[idx] in '\x09 ,.;:()[]{}<>-+*/\\!"§$%&=?#~+*\'´`^°|-':
                break
            idx += 1
        return text[:idx] or None, text[idx:]

    def parse_tuple(self, orgtext):
        text = orgtext.strip()
        bra = text[0]
        if bra not in '([<':
            return None, orgtext
        # convert to closing bracket
        bra = ')]>'['([<'.index(bra)]
        reslist = []
        # search for cosing bracket, collecting results
        text = text[1:]
        while text:
            if bra not in text:
                return None, text
            res, rem = self.parse_sub(text)
            if res is None:
                return None, text
            reslist.append(res)
            if rem[0] == bra:
                return tuple(reslist), rem[1:]
            # eat separator
            if rem[0] in ',;':
                text = rem[1:]
            else:
                return None, rem
        return None, orgtext

    def parse_dict(self, orgtext):
        text = orgtext.strip()
        if text[0] != '{':
            return None, orgtext
        # keep ordering
        result = OrderedDict()
        # search for cosing bracket, collecting results
        # watch for key=value or key:value pairs, separated by ,
        text = text[1:]
        while '}' in text:
            # first part is always a string
            key, rem = self.parse_string(text)
            if not key:
                return None, orgtext
            if rem[0] not in ':=':
                return None, rem
            # eat separator
            text = rem[1:]
            value, rem = self.parse_sub(text)
            if not value:
                return None, orgtext
            result[key] = value
            if rem[0] == '}':
                return result, rem[1:]

            if rem[0] not in ',;':
                return None, rem
            # eat separator
            text = rem[1:]
        return None, text

    def parse_sub(self, orgtext):
        text = orgtext.strip()
        if not text:
            return None, orgtext
        if text[0] in '+-.0123456789':
            return self.parse_number(orgtext)
        if text[0] == '{':
            return self.parse_dict(orgtext)
        if text[0] in '([<':
            return self.parse_tuple(orgtext)
        return self.parse_string(orgtext)

    def parse(self, orgtext):
        res, rem = self.parse_sub(orgtext)
        if rem and rem[0] in ',;':
            return self.parse_sub('[%s]' % orgtext)
        return res, rem
