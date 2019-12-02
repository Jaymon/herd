# -*- coding: utf-8 -*-
from __future__ import unicode_literals, division, print_function, absolute_import
import os
import codecs
import tempfile
from distutils import dir_util
import shutil
from zipfile import ZipFile
import glob

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

    @classmethod
    def create(cls, *args, **kwargs):
        path = Filepath(*args, **kwargs)
        if not os.path.isfile(path):
            path = Dirpath(*args, **kwargs)
            if not os.path.isdir(path):
                raise ValueError("Path {} is neither a file or folder".format(path))
        return path

    def __new__(cls, *args, **kwargs):
        path = os.path.join(*args)
        instance = super(Path, cls).__new__(cls, path)
        return instance

    def exists(self):
        return os.path.exists(self)

    def isfile(self):
        return os.path.isfile(self)

    def isdir(self):
        return os.path.isdir(self)


class Dirpath(Path):
    def exists(self):
        return os.path.isdir(self)

    def __iter__(self):
        for root_dir, dirs, files in os.walk(self, topdown=True):
            yield root_dir, dirs, files

    def copy_to(self, dest_path):
        """copy self to dest_path"""
        source_path = self
        # https://stackoverflow.com/a/15034373/5006
        dir_util.copy_tree(source_path, dest_path, update=1)

    def zip_to(self, dest_path):
        if dest_path.endswith(".zip"):
            dest_path = os.path.splitext(dest_path)[0]
        # https://docs.python.org/3/library/shutil.html#shutil.make_archive
        # https://stackoverflow.com/a/25650295/5006
        return shutil.make_archive(dest_path, 'zip', self)

    def delete(self):
        """Remove this whole directory and all subdirectories and files in it"""
        shutil.rmtree(self)

    def glob(self, pattern):
        return glob.glob(os.path.join(self, pattern))

    def files(self):
        for root_dir, dirs, files in self:
            return files


class Tempdir(Dirpath):
    def __new__(cls, *args, **kwargs):
        prefix = ""
        if args:
            prefix = os.path.join(*args)
        if prefix:
            prefix += "-"
        basedir = kwargs["dir"] if "dir" in kwargs else tempfile.gettempdir()
        path = tempfile.mkdtemp(prefix=prefix, dir=basedir)
        return super(Path, cls).__new__(cls, path)


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

    def copy_to(self, dest_path):
        r = shutil.copy(self, dest_path)

    def zip_to(self, dest_path):
        with ZipFile(dest_path, 'w') as z:
            z.write(self)
        return dest_path

    def delete(self):
        """remove the file"""
        os.unlink(self)

