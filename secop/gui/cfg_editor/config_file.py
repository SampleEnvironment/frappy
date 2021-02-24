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
#   Sandra Seger <sandra.seger@frm2.tum.de>
#
# *****************************************************************************

import configparser
from collections import OrderedDict
from configparser import NoOptionError

from secop.gui.cfg_editor.tree_widget_item import TreeWidgetItem
from secop.gui.cfg_editor.utils import get_all_children_with_names, \
    get_all_items, get_interface_class_from_name, \
    get_module_class_from_name, get_params, get_props

NODE = 'node'
INTERFACE = 'interface'
MODULE = 'module'
PARAMETER = 'parameter'
PROPERTY = 'property'
COMMENT = 'comment'

SECTIONS = {NODE: 'description',
            INTERFACE: 'type',
            MODULE: 'class'}


def write_config(file_name, tree_widget):
    itms = get_all_items(tree_widget)
    itm_lines = OrderedDict()
    value_str = '%s = %s'
    blank_lines = 0
    for itm in itms:
        if itm.kind is None:
            continue
        par = itm.parent()
        value = str(itm.get_value())
        if itm.kind in SECTIONS:
            if itm.kind in [MODULE, INTERFACE]:
                itm_lines[blank_lines] = ''
                blank_lines += 1
            value = value.replace('\n\n', '\n.\n')
            value = value.replace('\n', '\n    ')
            itm_lines[id(itm)] = '[%s %s]\n' % (itm.kind, itm.name) +\
                                 value_str % (SECTIONS[itm.kind], value)
        # TODO params and props
        elif itm.kind == PARAMETER and value:
            itm_lines[id(itm)] = value_str % (itm.name, value)
        elif itm.kind == PROPERTY:
            prop_name = '.%s' % itm.name
            if par.kind == PARAMETER:
                prop_name = par.name + prop_name
            itm_lines[id(itm)] = value_str % (prop_name, value)
        elif itm.kind == COMMENT:
            temp_itm_lines = OrderedDict()
            for key, dict_value in itm_lines.items():
                if key == id(par):
                    value = value.replace('\n', '\n# ')
                    temp_itm_lines[id(itm)] = '# %s' % value
                temp_itm_lines[key] = dict_value
            itm_lines.clear()
            itm_lines.update(temp_itm_lines)
    with open(file_name, 'w') as configfile:
        configfile.write('\n'.join(itm_lines.values()))


def read_config(file_path):
    # TODO datatype of params and properties
    node = TreeWidgetItem(NODE)
    ifs = TreeWidgetItem(name='interfaces')
    mods = TreeWidgetItem(name='modules')
    node.addChild(ifs)
    node.addChild(mods)
    config = configparser.ConfigParser()
    config.read_file(open(file_path))

    for section in config.sections():
        kind = section.split(' ', 1)[0]
        name = section.split(' ', 1)[1]
        try:
            section_value = get_value(config, section, SECTIONS[kind])
            section_value = section_value.replace('\n.\n', '\n\n') \
                if kind == NODE else section_value
        except NoOptionError:
            # TODO invalid configuration
            continue
        if kind == NODE:
            node.set_name(name)
            act_item = node
            act_item.set_value(section_value)
            act_item.parameters = get_params(kind)
            act_item.properties = get_props(kind)
        else:
            act_item = TreeWidgetItem(kind, name)
            act_item.set_value(section_value)
            if kind == MODULE:
                mods.addChild(act_item)
                act_class = get_module_class_from_name(section_value)
                act_item.set_class_object(act_class)
            else:
                act_class = get_interface_class_from_name(section_value)
                act_item.set_class_object(act_class)
                ifs.addChild(act_item)
            act_item.parameters = get_params(act_class)
            act_item.properties = get_props(act_class)

        # TODO rewrite so Parameters and Properties get class_object and
        #  properties, needed information in act_item.parameters/properties
        for option in config.options(section):
            if option != SECTIONS[kind]:
                if option[0] == '.':
                    prop = TreeWidgetItem(PROPERTY, option[1:],
                                          get_value(config, section, option))
                    act_item.addChild(prop)
                else:
                    separated = option.split('.')
                    act_children = get_all_children_with_names(act_item)
                    # TODO find param / props in params, props and add datatype
                    if separated[0] in act_children:
                        param = act_children[separated[0]]
                    else:
                        param = TreeWidgetItem(PARAMETER, separated[0])
                        act_item.addChild(param)
                    if len(separated) == 1:
                        param.set_value(get_value(config, section, option))
                    else:
                        param.addChild(TreeWidgetItem(PROPERTY,
                                       separated[1], get_value(config, section,
                                                               option)))
    node = get_comments(node, ifs, mods, file_path)
    return node, ifs, mods


def get_value(config, section, option):
    value = config.get(section, option)
    if value.find('#') != -1:
        value = value[:value.find('#')]
    return value


def get_comments(node, ifs, mods, file_path):
    configfile = open(file_path, 'r')
    all_lines = configfile.readlines()
    current_comment = None
    all_ifs = get_all_children_with_names(ifs)
    all_mods = get_all_children_with_names(mods)
    for index, line in enumerate(all_lines):
        line = line[:-1]
        if line.startswith('#'):
            line = line[1:].strip()
            if index and all_lines[index-1][0] == '#':
                current_comment.set_value('%s\n%s' % (current_comment.
                                                      get_value(), line))
            else:
                current_comment = TreeWidgetItem(COMMENT, '#', line)
                next_line = get_next_line(index, all_lines)
                if not next_line:
                    node.insertChild(0, current_comment)
                    continue
                insert_comment(index, next_line, all_lines, current_comment,
                               node, all_ifs, all_mods)
        elif line.find('#') != -1:
            comment_index = line.find('#')
            current_comment = TreeWidgetItem(COMMENT, '#',
                                             line[comment_index+1:].strip())
            line = line[:comment_index]
            insert_comment(index, line, all_lines, current_comment, node,
                           all_ifs, all_mods)
    return node


def insert_comment(index, line, all_lines, current_comment, node, all_ifs, all_mods):
    if not insert_section_comment(line, current_comment, node, all_ifs,
                                  all_mods):
        insert_param_prop_comment(index, line, all_lines, current_comment, node,
                                  all_ifs, all_mods)


def insert_section_comment(line, current_comment, node, all_ifs, all_mods):
    try:
        if line.startswith('[%s' % NODE):
            node.insertChild(0, current_comment)
        elif line.startswith('[%s' % INTERFACE):
            all_ifs[get_name_of_section(line)]. \
                insertChild(0, current_comment)
        elif line.startswith('[%s' % MODULE):
            all_mods[get_name_of_section(line)]. \
                insertChild(0, current_comment)
        else:
            return False
        return True
    except KeyError:
        # TODO invalid file
        pass


def insert_param_prop_comment(index, line, all_lines, current_comment,
                              node, all_ifs, all_mods):
    try:
        parent = get_previous_line(index, all_lines)
        if not parent:
            # TODO invalid file
            pass
        if parent.startswith('[%s' % NODE):
            parent_item = node
        elif parent.startswith('[%s' % INTERFACE):
            parent_item = all_ifs[get_name_of_section(parent)]
        else:
            parent_item = all_mods[get_name_of_section(parent)]
        parent_children = get_all_children_with_names(
            parent_item)
        line = line.replace(' ', '')
        line = line.split('=')[0]
        dot_i = line.find('.')
        if dot_i == -1:
            # parameter
            parent_children[line].insertChild(
                0, current_comment)
        elif dot_i == 0:
            # .property
            parent_children[line[1:]].insertChild(
                0, current_comment)
        else:
            # parameter.property
            sub_childs = get_all_children_with_names(
                parent_children[line[:dot_i]])
            sub_childs[line[dot_i + 1:]].insertChild(
                0, current_comment)
    except KeyError:
        # TODO invalid file
        pass


def get_next_line(index, all_lines):
    next_index = index + 1
    try:
        while all_lines[next_index][0] == '#' or \
                all_lines[next_index][:-1].strip() == '':
            next_index += 1
    except IndexError:
        return ''
    return all_lines[next_index][:-1].strip()


def get_previous_line(index, all_lines):
    prev_index = index - 1
    try:
        while all_lines[prev_index].strip()[0] != '[':
            prev_index -= 1
    except IndexError:
        return ''
    return all_lines[prev_index]


def get_name_of_section(line):
    line = line[line.find('['):line.rfind(']')]
    return ' '.join(line.split(' ', 1)[1:])
