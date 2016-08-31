# SECoP demo syntax simulation
#
# Author: Markus Zolliker <markus.zolliker@psi.ch>
#
# Input from a file for test purposes:
#
#   python -m demo_server f < test.txt
#
# Input from commandline:
#
#   python -m demo_server
#
# Input from TCP/IP connections:
#
#   python -m demo_server <port>


import json
from collections import OrderedDict
from fnmatch import fnmatch
from datetime import datetime

import sys
if len(sys.argv) <= 1:
    port = 0
    import cmd_lineserver as lineserver
elif sys.argv[1] == "f":
    port = 1
    import cmd_lineserver as lineserver
else:
    port = int(sys.argv[1])
    import tcp_lineserver as lineserver


class SecopError(Exception):

    def __init__(self, message, text):
        Exception.__init__(self, message, text)


class UnknownDeviceError(SecopError):

    def __init__(self, message, args):
        SecopError.__init__(self, "NoSuchDevice", args[0])


class UnknownParamError(SecopError):

    def __init__(self, message, args):
        SecopError.__init__(self, "NoSuchParam", "%s:%s" % args)


class UnknownPropError(SecopError):

    def __init__(self, message, args):
        SecopError.__init__(self, "NoSuchProperty", "%s:%s:%s" % args)


class SyntaxError(SecopError):

    def __init__(self, message):
        SecopError.__init__(self, "SyntaxError", message)


class OtherError(SecopError):

    def __init__(self, message):
        SecopError.__init__(self, "OtherError", message)


def encode(input):
    inp = str(input)
    enc = repr(inp)
    if inp.find(';') >= 0 or inp != enc[1:-1]:
        return enc
    return inp


def gettype(obj):
    typ = str(type(obj).__name__)
    if typ == "unicode":
        typ = "string"
    return typ


def wildcard(dictionary, pattern):
    list = []
    if pattern == "":
        pattern = "."
    for p in pattern.split(","):
        if p[-1] == "*":
            if p[:-1].find("*") >= 0:
                raise SyntaxError("illegal wildcard pattern %s" % p)
            for key in dictionary:
                if key.startswith(p[:-1]):
                    list.append(key)
        elif p in dictionary:
            list.append(p)
        else:
            raise KeyError(pattern)
    return list


class SecopClientProps(object):

    def __init__(self):
        self.reply_items = {".": "t", "writable": 1}
        self.compact_output = {".": 0, "writable": 1}


class SecopLineHandler(lineserver.LineHandler):

    def __init__(self, *args, **kwargs):
        lineserver.LineHandler.__init__(self, *args, **kwargs)
        self.props = SecopClientProps()

    def handle_line(self, msg):
        try:
            if msg[-1:] == "\r":  # strip CR at end (for CRLF)
                msg = msg[:-1]
            if msg[:1] == "+":
                self.subscribe(msg[1:].split(":"))
            elif msg[:1] == "-":
                self.unsubscribe(msg[1:].split(":"))
            elif msg[:1] == "!":
                self.list(msg[1:])
            else:
                j = msg.find("=")
                if j >= 0:
                    self.write(msg[0:j], msg[j + 1:])
                else:
                    self.read(msg)
        except SecopError as e:
            self.send_line("~%s~ %s" % (e.args[0], e.args[1]))
        self.send_line("")

    def get_device(self, d):
        if d == "":
            d = "."
        if d == ".":
            return self.props.__dict__
        try:
            return secNodeDict[d]
        except KeyError:
            raise UnknownDeviceError("", (d))

    def get_param(self, d, p):
        if p == "":
            p = "."
        try:
            return self.get_device(d)[p]
        except KeyError:
            raise UnknownParamError("", (d, p))

    def get_prop(self, d, p, y):
        if y == "":
            y = "."
        try:
            paramDict = self.get_param(d, p)
            return (paramDict, paramDict[y])
        except KeyError:
            raise UnknownPropertyError("", (d, p, y))

    def clear_output_path(self):
        # used for compressing only
        self.outpath = [".", ".", "."]
        try:
            self.compact = self.props.compact_output["."] != 0
        except KeyError:
            self.compact = False

    def output_path(self, d, p=".", y="."):
        # compose path from arguments. compress if compact is True
        if d == self.outpath[0]:
            msg = ":"
        else:
            msg = d + ":"
            if self.compact:
                self.outpath[0] = d
                self.outpath[1] = "."
                self.outpath[2] = "."
        if p == self.outpath[1]:
            msg += ":"
        else:
            msg += p + ":"
            if self.compact:
                self.outpath[1] = p
                self.outpath[2] = "."
        if y == "" or y == self.outpath[2]:
            while msg[-1:] == ":":
                msg = msg[:-1]
        else:
            msg += y
            if self.compact:
                self.outpath[2] = y
        return msg

    def write(self, pathArg, value):
        self.clear_output_path()
        path = pathArg.split(":")
        while len(path) < 3:
            path.append("")
        d, p, y = path
        parDict = self.get_param(d, p)
        if (y != "." and y != "") or not parDict.get("writable", 0):
            self.send_line("? %s is not writable" % self.output_path(d, p, y))
        typ = type(parDict["."])
        try:
            val = (typ)(value)
        except ValueError:
            raise SyntaxError("can not convert '%s' to %s" %
                              (value, gettype(value)))
        parDict["."] = val
        parDict["t"] = datetime.utcnow()
        self.send_line(self.output_path(d, p, ".") +
                       "=" + encode(parDict["."]))

    def read(self, pathArg):
        self.clear_output_path()
        path = pathArg.split(":")
        if len(path) > 3:
            raise SyntaxError("path may only contain 3 elements")
        while len(path) < 3:
            path.append("")

        # first collect a list of matched properties
        list = []
        try:
            devList = wildcard(secNodeDict, path[0])
        except KeyError as e:
            raise UnknownDeviceError("", (e.message))
        for d in devList:
            devDict = secNodeDict[d]
            try:
                parList = wildcard(devDict, path[1])
            except KeyError as e:
                raise UnknownParamError("", (d, e.message))
            for p in parList:
                parDict = devDict[p]
                try:
                    propList = wildcard(parDict, path[2])
                except KeyError as e:
                    raise UnknownPropError("", (d, p, e.message))
                for y in propList:
                    list.append((d, p, y))

        # then, if no error happened, write out the messages
        try:
            replyitems = self.props.reply_items["."]
            replyitems = replyitems.split(",")
        except KeyError:
            replyitems = []
        for item in list:
            d, p, y = item
            paramDict = secNodeDict[d][p]
            if path[2] == "":
                msg = self.output_path(d, p, "") + "=" + encode(paramDict["."])
                for y in replyitems:
                    if y == ".":
                        continue  # do not show the value twice
                    try:
                        msg += ";" + y + "=" + encode(paramDict[y])
                    except KeyError:
                        pass
            else:
                msg = self.output_path(d, p, y) + "=" + encode(paramDict[y])
            self.send_line(msg)

    def list(self, pathArg):
        self.clear_output_path()
        path = pathArg.split(":")
        # first collect a list of matched items
        list = []
        try:
            devList = wildcard(secNodeDict, path[0])
        except KeyError as e:
            raise UnknownDeviceError("", (e.message))
        for d in devList:
            devDict = secNodeDict[d]
            if len(path) == 1:
                list.append((d, ".", "."))
            else:
                try:
                    parList = wildcard(devDict, path[1])
                except KeyError as e:
                    raise UnknownParamError("", (d, e.message))
                for p in parList:
                    parDict = devDict[p]
                    if len(path) == 2:
                        list.append((d, p, "."))
                    else:
                        try:
                            propList = wildcard(parDict, path[2])
                        except KeyError as e:
                            raise UnknownPropError("", (d, p, e.message))
                        for y in propList:
                            list.append((d, p, y))

        # then, if no error happened, write out the items
        for item in list:
            d, p, y = item
            self.send_line(self.output_path(d, p, y))

    def subscribe(self, pathArg):
        raise OtherError("subscribe unimplemented")

    def unsubscribe(self, pathArg):
        raise OtherError("unsubscribe unimplemented")

if port <= 1:
    server = lineserver.LineServer(port, SecopLineHandler)
else:
    server = lineserver.LineServer("localhost", port, SecopLineHandler)


secNodeDict = json.load(open("secnode.json", "r"),
                        object_pairs_hook=OrderedDict)
#json.dump(secNodeDict, open("secnode_out.json", "w"), indent=2, separators=(",",":"))
for d in secNodeDict:
    devDict = secNodeDict[d]
    for p in devDict:
        parDict = devDict[p]
        try:
            parDict["type"] = gettype(parDict["."])
        except KeyError:
            print d, p, " no '.' (value) property"
            continue
        parDict["t"] = datetime.utcnow()

server.loop()
