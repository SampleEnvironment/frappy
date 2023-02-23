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

import inspect
import sys
from os import listdir, path

from frappy.gui.qt import QDialogButtonBox, QFileDialog, QIcon, QSize, uic
from frappy.modules import Module
from frappy.params import Parameter
from frappy.properties import Property
from frappy.protocol.interface.tcp import TCPServer
from frappy.server import generalConfig

uipath = path.dirname(__file__)


def loadUi(widget, uiname, subdir='ui'):
    uic.loadUi(path.join(uipath, subdir, uiname), widget)


def setIcon(widget, icon_name, subdir='ui', icondir='icons'):
    widget.setIcon(QIcon(path.join(uipath, subdir, icondir, icon_name)))
    widget.setIconSize(QSize(60, 60))


def set_name_edit_style(invalid, name_edit, button_box=None):
    if invalid:
        name_edit.setStyleSheet("color: red")
        name_edit.setToolTip('Invalid name: name already taken')
        if button_box:
            button_box.button(QDialogButtonBox.Ok).setEnabled(False)
    else:
        name_edit.setStyleSheet("color: black")
        name_edit.setToolTip('')
        if button_box:
            button_box.button(QDialogButtonBox.Ok).setEnabled(True)


def setTreeIcon(widget, icon_name, subdir='ui', icondir='icons'):
    widget.setIcon(0, QIcon(path.join(uipath, subdir, icondir, icon_name)))


def setActionIcon(widget, icon_name, subdir='ui', icondir='icons'):
    widget.setIcon(QIcon(path.join(uipath, subdir, icondir, icon_name)))


def get_subtree_nodes(tree_widget_item):
    nodes = []
    nodes.append(tree_widget_item)
    for i in range(tree_widget_item.childCount()):
        nodes.extend(get_subtree_nodes(tree_widget_item.child(i)))
    return nodes


def get_all_children_with_names(tree_widget_item):
    children = {}
    for i in range(0, tree_widget_item.childCount()):
        children[tree_widget_item.child(i).name] = tree_widget_item.child(i)
    return children


def get_all_items(tree_widget):
    all_items = []
    for i in range(tree_widget.topLevelItemCount()):
        top_item = tree_widget.topLevelItem(i)
        all_items.extend(get_subtree_nodes(top_item))
    return all_items


def get_file_paths(widget, open_file=True):
    dialog = QFileDialog(widget)
    if open_file:
        title = 'Open file'
        dialog.setAcceptMode(QFileDialog.AcceptOpen)
        dialog.setFileMode(QFileDialog.ExistingFiles)
    else:
        title = 'Save file'
        dialog.setAcceptMode(QFileDialog.AcceptSave)
        dialog.setFileMode(QFileDialog.AnyFile)
    dialog.setWindowTitle(title)
    dialog.setNameFilter('*.cfg')
    dialog.setDefaultSuffix('.cfg')
    dialog.exec_()
    return dialog.selectedFiles()


def get_modules():
    modules = {}
    generalConfig.init()
    base_path = generalConfig.basedir
    # pylint: disable=too-many-nested-blocks
    for dirname in listdir(base_path):
        if dirname.startswith('frappy_'):
            modules[dirname] = {}
            for filename in listdir(path.join(base_path, dirname)):
                if not path.isfile(path.join(base_path, dirname, filename)) or \
                        filename == '__init__.py' or filename[-3:] != '.py':
                    continue
                module = '%s.%s' % (dirname, filename[:-3])
                module_in_file = False
                try:
                    __import__(module)
                    for name, obj in inspect.getmembers(sys.modules[module]):
                        if inspect.isclass(obj) and \
                                obj.__module__.startswith('frappy_') and \
                                issubclass(obj, Module):
                            # full_name = '%s.%s' % (obj.__module__, name)
                            if not module_in_file:
                                modules[dirname][filename[:-3]] = []
                                module_in_file = True
                            modules[dirname][filename[:-3]].append(name)
                except ImportError:
                    pass
    return modules


def get_module_class_from_name(name):
    try:
        last_dot = name.rfind('.')
        class_name = name[last_dot+1:]
        module = name[:last_dot]
        __import__(module)
        for cls_name, obj in inspect.getmembers(sys.modules[module]):
            if inspect.isclass(obj) and obj.__module__.startswith('frappy_') \
                    and issubclass(obj, Module) and cls_name == class_name:
                return obj
    except ImportError:
        pass
    return -1


def get_interface_class_from_name(name):
    # TODO: return the class of name and not TCPServer hard coded
    return TCPServer


def get_interfaces():
    # TODO class must be found out like for modules
    interfaces = []
    generalConfig.init()
    interface_path = path.join(generalConfig.basedir, 'frappy',
                               'protocol', 'interface')
    for filename in listdir(interface_path):
        if path.isfile(path.join(interface_path, filename)) and \
                        filename != '__init__.py' and filename[-3:] == '.py':
            interfaces.append(filename[:-3])
    return interfaces


def get_params(info):
    """returns all parameter of a module with all properties of all parameter
     as dictionary: {parameter name: [Parameter object, {property name, Property object}], ...}"""
    params = {}
    try:
        conf = info.configurables
        for access in info.accessibles:
            if type(info.accessibles[access]) == Parameter:
                params[access] = [info.accessibles[access], conf[access]]
    except AttributeError:
        return {}
    return params


def get_props(info):
    """returns all properties of a module class, interface class or parameter
     as dictionary: {property name: Property object, ...}"""
    props = {}
    try:
        conf = info.configurables
        for name, value in conf.items():
            if type(value) == Property:
                props[name] = value
    except AttributeError:
        return {}
    return props
