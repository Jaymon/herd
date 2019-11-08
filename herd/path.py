# -*- coding: utf-8 -*-
from __future__ import unicode_literals, division, print_function, absolute_import
import os
import codecs


from .compat import *


class Path(String):
    @property
    def dirname(self):
        return Dirpath(os.path.dirname(self))

    @property
    def basename(self):
        return os.path.basename(self)

    @property
    def fileroot(self):
        return self.basename

    def __new__(cls, *args, **kwargs):
        path = os.path.join(*args)
        instance = super(Path, cls).__new__(cls, path)
        return instance

    def exists(self):
        return os.path.exists(self)


class Dirpath(Path):
    def exists(self):
        return os.path.isdir(self)

    def __iter__(self):
        for root_dir, dirs, files in os.walk(self, topdown=True):
            yield root_dir, dirs, files


class Filepath(Path):
    @property
    def fileroot(self):
        return os.path.splitext(self.basename)[0]

    def __new__(cls, *args, **kwargs):
        if "ext" in kwargs:
            args = list(args)
            ext = kwargs.pop("ext")
            if not args[-1].endswith(ext):
                args[-1] = "{}.{}".format(args[-1], ext.lstrip("."))

        instance = super(Filepath, cls).__new__(cls, *args, **kwargs)
        instance.encoding = kwargs.pop("encoding", "UTF-8")
        return instance

    def __iter__(self):
        for line in self.contents().splitlines(False):
            yield line

    def contents(self):
        if self.encoding:
            open_kwargs = dict(mode='r', errors='replace', encoding=self.encoding)
            with codecs.open(self, **open_kwargs) as fp:
                return fp.read()

        else:
            with open(self, mode="rb") as fp:
                return fp.read()

    def exists(self):
        return os.path.isfile(self)
