# -*- coding: utf-8 -*-
from __future__ import unicode_literals, division, print_function, absolute_import
import sys


def get_runtime():
    info = sys.version_info
    return "python{}.{}".format(info.major, info.minor)
    #return os.path.basename(sys.executable)

