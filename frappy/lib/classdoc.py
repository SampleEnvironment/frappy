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

from textwrap import indent

from frappy.modules import Command, Parameter, Property
from frappy.modulebase import HasProperties, Module


def indent_description(p):
    """indent lines except first one"""
    space = ' ' * 6
    return indent(p.description, space).replace(space, '', 1)


def fmt_param(name, param):
    desc = indent_description(param)
    if '(' in desc[0:2]:
        dtinfo = ''
    else:
        dtinfo = [short_doc(param.datatype), 'rd' if param.readonly else 'wr',
                  None if param.export else 'hidden']
        dtinfo = f"*({', '.join(filter(None, dtinfo))})* "
    return f'- **{name}** - {dtinfo}{desc}\n'


def fmt_command(name, command):
    desc = indent_description(command)
    if '(' in desc[0:2]:
        dtinfo = ''  # note: we expect that desc contains argument list
    else:
        dtinfo = f'*{short_doc(command.datatype)}*' + f" -{'' if command.export else ' *(hidden)*'} "
    return f'- **{name}**\\ {dtinfo}{desc}\n'


def fmt_property(name, prop):
    desc = indent_description(prop)
    if '(' in desc[0:2]:
        dtinfo = ''
    else:
        dtinfo = [short_doc(prop.datatype), None if prop.export else 'hidden']
        dtinfo = ', '.join(filter(None, dtinfo))
        if dtinfo:
            dtinfo = f'*({dtinfo})* '
    return f'- **{name}** - {dtinfo}{desc}\n'


SIMPLETYPES = {
    'FloatRange': 'float',
    'ScaledInteger': 'float',
    'IntRange': 'int',
    'BlobType': 'bytes',
    'StringType': 'str',
    'TextType': 'str',
    'BoolType': 'bool',
    'StructOf': 'dict',
}


def short_doc(datatype, internal=False):
    # pylint: disable=possibly-unused-variable

    def doc_EnumType(dt):
        return f'one of {str(tuple(dt._enum.keys()))}'

    def doc_ArrayOf(dt):
        return f'array of {short_doc(dt.members, True)}'

    def doc_TupleOf(dt):
        return f"tuple of ({', '.join(short_doc(m, True) for m in dt.members)})"

    def doc_CommandType(dt):
        argument = short_doc(dt.argument, True) if dt.argument else ''
        result = f' -> {short_doc(dt.result, True)}' if dt.result else ''
        return f'({argument}){result}'  # return argument list only

    def doc_NoneOr(dt):
        other = short_doc(dt.other, True)
        return f'{other} or None' if other else None

    def doc_OrType(dt):
        types = [short_doc(t, True) for t in dt.types]
        if None in types:  # type is anyway broad: no doc
            return None
        return ' or '.join(types)

    def doc_Stub(dt):
        return dt.name.replace('Type', '').replace('Range', '').lower()

    def doc_BLOBType(dt):
        return 'byte array'

    clsname = type(datatype).__name__
    result = SIMPLETYPES.get(clsname)
    if result:
        return result
    fun = locals().get('doc_' + clsname)
    if fun:
        return fun(datatype)
    return clsname if internal else None  # broad types like ValueType: no doc


def append_to_doc(cls, lines, itemcls, name, attrname, fmtfunc):
    """add information about some items to the doc

    :param cls: the class with the doc string to be extended
    :param lines: content of the docstring, as lines
    :param itemcls: the class of the attribute to be collected, a tuple of classes is also allowed.
    :param attrname: the name of the attribute dict to look for
    :param name: the name of the items to be collected (used for the title and for the tags)
    :param fmtfunc: a function returning a formatted item to be displayed, including line feed at end
       or an empty string to suppress output for this item
    :type fmtfunc: function(key, value)

    rules, assuming name='properties':

       - if the docstring contains ``{properties}``, new properties are inserted here
       - if the docstring contains ``{all properties}``, all properties are inserted here
       - if the docstring contains ``{no properties}``, no properties are inserted

    only the first appearance of a tag above is considered
    """
    doc = '\n'.join(lines)
    title = f'SECoP {name.title()}'
    allitems = getattr(cls, attrname, {})
    fmtdict = {n: fmtfunc(n, p) for n, p in allitems.items() if isinstance(p, itemcls)}
    head, _, tail = doc.partition('{all %s}' % name)
    clsset = set()
    if tail:  # take all
        fmted = fmtdict.values()
    else:
        head, _, tail = doc.partition('{%s}' % name)
        if not tail:
            head, _, tail = doc.partition('{no %s}' % name)
            if tail:  # add no information
                return
            # no tag found: append to the end

        fmted = []
        for key, formatted_item in fmtdict.items():
            if not formatted_item:
                continue
            # find where item is defined or modified
            refcls = None
            for base in cls.__mro__:
                p = getattr(base, attrname, {}).get(key)
                if isinstance(p, itemcls):
                    if fmtfunc(key, p) == formatted_item:
                        refcls = base
                    else:
                        break
            if refcls == cls:
                # definition in cls is new or modified
                fmted.append(formatted_item)
            else:
                # definition of last modification in refcls
                clsset.add(refcls)
    if fmted:
        if clsset:
            fmted.append('- see also %s\n' % (', '.join(':class:`%s.%s`' % (c.__module__, c.__name__)
                                                        for c in cls.__mro__ if c in clsset)))

        doc = f"{head}\n\n:{title}: {'  '.join(fmted)}\n\n{tail}"
        lines[:] = doc.split('\n')


def class_doc_handler(app, what, name, cls, options, lines):
    if what == 'class':
        if issubclass(cls, HasProperties):
            append_to_doc(cls, lines, Property, 'properties', 'propertyDict', fmt_property)
        if issubclass(cls, Module):
            append_to_doc(cls, lines, Parameter, 'parameters', 'accessibles', fmt_param)
            append_to_doc(cls, lines, Command, 'commands', 'accessibles', fmt_command)
