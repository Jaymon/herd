# -*- coding: utf-8 -*-
from __future__ import unicode_literals, division, print_function, absolute_import
import sys


def get_runtime():
    """returns the current python runtime

    :returns: string, the python runtime (eg, python2.7)
    """
    info = sys.version_info
    return "python{}.{}".format(info.major, info.minor)
    #return os.path.basename(sys.executable)

