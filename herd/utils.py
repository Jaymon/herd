# -*- coding: utf-8 -*-
from __future__ import unicode_literals, division, print_function, absolute_import
import sys
import re

from captain.parse import UnknownParser

from .compat import *


def get_runtime():
    """returns the current python runtime

    :returns: string, the python runtime (eg, python2.7)
    """
    info = sys.version_info
    return "python{}.{}".format(info.major, info.minor)
    #return os.path.basename(sys.executable)


class NormalizeDict(dict):
    def __init__(self, *args, **kwargs):
        self.update(*args, **kwargs)

    def __setitem__(self, k, v):
        k = self.normalize_key(k)
        v = self.normalize_value(v)
        return super(NormalizeDict, self).__setitem__(k, v)

    def __delitem__(self, k):
        k = self.normalize_key(k)
        return super(NormalizeDict, self).__delitem__(k)

    def __getitem__(self, k):
        k = self.normalize_key(k)
        return super(NormalizeDict, self).__getitem__(k)

    def __contains__(self, k):
        k = self.normalize_key(k)
        return super(NormalizeDict, self).__contains__(k)

    def setdefault(self, key, default=None):
        k = self.normalize_key(k)
        v = self.normalize_value(default)
        return super(NormalizeDict, self).setdefault(k, v)

    def update(self, *args, **kwargs):
        # create temp dictionary so I don't have to mess with the arguments
        d = dict(*args, **kwargs)
        for k, v in d.items():
            self[k] = v

    def pop(self, key, default=None):
        k = self.normalize_key(k)
        v = self.normalize_value(default)
        return super(NormalizeDict, self).pop(k, v)

    def get(self, key, default=None):
        k = self.normalize_key(k)
        v = self.normalize_value(default)
        return super(NormalizeDict, self).get(k, v)

    def normalize_key(self, k):
        return k

    def normalize_value(self, v):
        return v


class Environ(NormalizeDict):
    def normalize_key(self, k):
        return String(k).upper()

    def normalize_value(self, v):
        return String(v)


class EnvironParser(UnknownParser):
    def __init__(self, args):
        super(Environ, self).__init__(args)

        for k in list(self.keys()):
            if not re.match(r"^[A-Z0-9_-]+$", k):
                del self[k]

