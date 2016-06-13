#!/usr/bin/env python
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

import os
from os import path
import markdown
import codecs

BASE_PATH = path.abspath(path.join(path.dirname(__file__), '..'))
DOC_SRC = path.join(BASE_PATH, 'doc')
DOC_DST = path.join(BASE_PATH, 'html')

conv = markdown.Markdown()

for dirpath, dirnames, filenames in os.walk(DOC_SRC):
    # re-create the dir-structure of DOC_SRC into DOC_DST
    dst_path = path.join(DOC_DST, path.relpath(dirpath, DOC_SRC))
    try:
        os.mkdir(dst_path)
    except OSError:
        pass

    
    for fn in filenames:
        full_name = path.join(dirpath, fn)
        sub_name = path.relpath(full_name, DOC_SRC)
        final_name = path.join(DOC_DST, sub_name)
 
        if not fn.endswith('md'):
            # just copy everything else
            with open(full_name, 'rb') as fi:
                with open(final_name, 'wb') as fo:
                    # WARNING: possible Memory hog!
                    fo.write(fi.read())
            continue
        # treat .md files special
        final_sub_name = path.splitext(sub_name)[0] + '.html'
        final_name = path.join(DOC_DST, final_sub_name)
        print "Converting", sub_name, "to", final_sub_name
        # transform one file
        conv.reset()
        conv.convertFile(input=full_name,
                         output=final_name,
                         encoding="utf-8")
