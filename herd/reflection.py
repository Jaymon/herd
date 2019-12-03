# -*- coding: utf-8 -*-
from __future__ import unicode_literals, division, print_function, absolute_import
import codecs
import ast
import sys
import os
import glob
from distutils import sysconfig
import json
import re
import pkgutil
import logging
import itertools

from .compat import *
from .path import Filepath, Dirpath, Path
from .utils import get_runtime


logger = logging.getLogger(__name__)


class Imports(set):
    """A set of all the toplevel imports of the passed in filepath"""
    def __init__(self, filepath, encoding="UTF-8"):
        super(Imports, self).__init__()

        open_kwargs = dict(mode='r', errors='replace', encoding=encoding)
        with codecs.open(filepath, **open_kwargs) as fp:
            body = fp.read().strip()

        try:
            self._find(body)
        except SyntaxError as e:
            logger.debug("Failed to parse {}".format(filepath))

    def _find(self, body):
        lines = [l for l in body.splitlines(False)]


        # This is based on code from pout.reflect.Call._find_calls and
        # endpoints.reflection.ReflectClass.get_info
        def visit_Import(node):
            for name in node.names:
                self.add(name.name.split(".")[0])

        def visit_ImportFrom(node):
            # if node.module is missing it's a "from . import ..." statement
            # if level > 0 it's a "from .submodule import ..." statement
            if node.module is not None and node.level == 0:
                self.add(node.module.split(".")[0])

        #def generic_visit(node):
        #    pout.v(node)

        node_iter = ast.NodeVisitor()
        node_iter.visit_Import = visit_Import
        node_iter.visit_ImportFrom = visit_ImportFrom
        #node_iter.generic_visit = generic_visit

        node_iter.visit(ast.parse(ByteString(body)))


class Dependencies(set):
    def __init__(self, path):
        #self.filepath = Filepath(filepath)
        self.resolve(path)

    def resolve(self, path):
        packages = Packages()
        seen = set()
        filepath = Filepath(path)
        if filepath.exists():
            logger.debug("Checking imports for {}".format(filepath))
            im = Imports(filepath)
            for modulename in im:
                self.update(self._resolve(modulename, packages, seen))

        else:
            # do we have a module path?
            try:
                p = packages[path]
            except ValueError:
                raise ValueError("Could not resolve path {}".format(path))

            else:
                logger.debug("Checking requires for {}".format(p))
                for modulename in p.requires():
                    self.update(self._resolve(modulename, packages, seen))

    def _resolve(self, modulepath, packages, seen):
        modulename = modulepath.split(".")[0]
        ret = set()
        if modulename not in seen:
            seen.add(modulename)

            try:
                p = packages[modulename]

            except KeyError as e:
                logger.debug("Missing dependency {}".format(modulename))

            else:
                if not p.is_standard():
                    ret.add(p)
                    logger.debug("Checking requires for {} at {}".format(p, p.path))
                    for m in p.requires():
                        #pout.v(name, require_modulepath, seen)
                        ret.update(self._resolve(m, packages, seen))

        return ret


class Infopath(String):
    @property
    def top_level(self):
        ret = []
        if self.path.isdir():
            filepath = Filepath(self, "top_level.txt")
            ret = [line.strip() for line in filepath]
        return ret

    @property
    def import_name(self):
        """tries to find the best import name for the module"""
        name = self.info_to_module(self.path.fileroot)
        basedir = self.path.dirname

        p = Package.find_path(name, basedir)
        if not p:
            top_level = self.top_level
            if top_level:
                name = self.top_level[0]

            else:
                for prefix in ["python_", "py"]:
                    if name.startswith(prefix):
                        try_name = name[len(prefix):]
                        p = Package.find_path(try_name, basedir)
                        if p:
                            name = p.fileroot
                            break

        return name

    @property
    def metadata(self):
        ret = {}
        jsonpath = Filepath(self, "metadata.json")
        if jsonpath.exists():
            ret = json.loads(jsonpath.contents())
        return ret

    @property
    def data(self):
        ret = ""
        if self.path.isfile():
            path = self.path
        else:
            path = Filepath(self, "METADATA")

        if path.exists():
            ret = path.contents()
        return ret

    @classmethod
    def info_to_module(cls, name):
        """removes things like the semver version

        :param name: string, the complete package name with things like semver
        :returns: the actual package name as pypi sees it
        """
        m = re.match("^([a-zA-Z0-9_]+)", name.strip())
        return m.group(1).replace("-", "_")

    def __new__(cls, infopath):
        infopath = Path.create(infopath)
        instance = super(Infopath, cls).__new__(cls, infopath)
        instance.path = infopath
        return instance

    def requires(self):
        """returns the info defined dependencies for this package

        this doesn't normalize the module name or anything

        :returns: set, the required packages per configuration
        """
        ret = set()

        md = self.metadata
        if md:
            for d in md.get("run_requires", []):
                for name in d.get("requires", []):
                    ret.add(self.info_to_module(name))

        else:
            txt = self.data
            if txt:
                for line in txt.splitlines(False):
                    if line.startswith("Requires-Dist"):
                        # TODO -- this line can have "extras == '...' info that
                        # means this package is optional and might not be
                        # installed
                        name = self.info_to_module(line.split(":")[1].strip())
                        if name:
                            ret.add(name)

        return ret


class Package(String):

    @property
    def name(self):
        return String(self)

    @property
    def filepath(self):
        """always reteurns a filepath for the module, this could either be self.name.py
        or __init__.py"""
        p = self.path
        if p is not None and p.isdir():
            p = Filepath(p, "__init__.py")
        return p

    @property
    def infopath(self):
        if not self.basedir: return ""

        for infopath in self.basedir.glob("*.*-info"):
            m = Infopath(infopath)
            if self in m.top_level:
                return m

    @classmethod
    def find_path(cls, name, basedir):
        ret = ""
        name = String(name)
        name = name.replace(".", "/")
        p = Filepath(basedir, name, ext=".py")
        if p.exists():
            ret = p
        else:
            p = Dirpath(basedir, name)
            if p.exists():
                ret = p

            else:
                p = Filepath(basedir, name, ext=".so")
                if p.exists():
                    ret = p

        if not ret:
            # let's just try and find by ignoring case
            basedir = Dirpath(basedir)
            regex = re.compile(r"^{}(?:\.py)?$".format(name), re.I)
            for root_dir, dirs, files in basedir:
                for basename in itertools.chain(files, dirs):
                    if regex.match(basename):
                        logger.debug("Found {} through case-insensitive search of {}".format(name, basedir))
                        ret = Path.create(root_dir, basename)
                        break

                break

        return ret

    def __new__(cls, name, basedir):
        path = None
        if basedir is not None:
            path = cls.find_path(name, basedir)
            if not path:
                raise ValueError("No module {} in {}".format(name, basedir))

            basedir = Dirpath(basedir)

        instance = super(Package, cls).__new__(cls, name)
        instance.basedir = basedir
        instance.path = path
        return instance

    def is_site(self):
        p = self.infopath
        return True if p else False

    def is_standard(self):
        sp = StandardPackages()
        try:
            sp[self]
            return True
        except KeyError:
            return False

    def is_local(self):
        return not self.is_site() and not self.is_standard()

    def is_package(self):
        """returns True if this package is a directory"""
        return self.path.isdir() if self.path else False

    def is_module(self):
        """returns True if this package is a module file"""
        return self.path.isfile() if self.path else False

    def has_shared_library(self):
        """Returns True if this package contains a shared library (.so) file"""
        if self.path:
            if self.path.isfile():
                return self.path.ext == "so"

            else:
                for root_dir, dirs, files in self.path:
                    for filename in files:
                        fp = Filepath(filename)
                        if fp.ext == "so":
                            return True

        return False

    def submodules(self):
        if self.is_package():
            for root_dir, dirs, files in self.path:
                relative_dir = root_dir.replace(self.basedir, "").strip("/")
                modpath = relative_dir.replace("/", ".")
                if Filepath(root_dir, "__init__.py").exists():
                    if modpath != self:
                        yield type(self)(modpath, self.basedir)

                    for basename in files:
                        if basename.endswith(".py") and basename != "__init__.py":
                            fp = Filepath(basename)
                            name = ".".join([modpath, fp.fileroot])
                            yield type(self)(name, self.basedir)

    def modules(self):
        """like .submodules() put will also yield self"""
        yield self
        for sm in self.submodules():
            yield sm

    def requires(self):
        ret = getattr(self, "_requires_set", None)
        if ret is None:
            ret = self._requires_import() or set()
            ret.update(self._requires_info() or set())

            # remove itself as a dependency if present (I'm looking at you pycrypto)
            ret.discard(self)
            self._requires_set = ret

        return ret

    def _requires_import(self):
        """find all the import statements in all the modules of this package"""
        ret = set()

        for m in self.modules():
            if m.filepath:
                im = Imports(m.filepath)
                ret.update(im)

            else:
                logger.debug("Cannot find imports for {}".format(m))

        return ret

    def _requires_info(self):
        ret = set()
        infopath = self.infopath
        if infopath:
            ret = infopath.requires()
        return ret


class Packages(dict):
    #instance = None

    package_class = Package

    def __init__(self, paths=None):
        self.paths = paths
        super(Packages, self).__init__()

    def search_paths(self):
        if self.paths:
            for p in self.paths:
                yield Dirpath(p)

        else:
            for p in sys.path:
                dp = Dirpath(p)
                if dp.exists():
                    yield dp

    def __missing__(self, name):
        ret = None
        for basedir in self.search_paths():
            try:
                ret = self.package_class(name, basedir)
                logger.debug("Found {} in {}".format(name, basedir))
                break

            except ValueError:
                pass

        if not ret:
            # search again, this time looking for the info folder
            pattern = "{}*.*-info".format(name.replace("-", "?"))
            for basedir in self.search_paths():
                for infopath in basedir.glob(pattern):
                    m = Infopath(infopath)
                    ret = self.package_class(m.import_name, basedir)
                    logger.debug("Found {} = {} using infopath {}".format(name, ret, infopath))

                    if super(Packages, self).__contains__(ret): 
                        logger.debug("Mapping {} to {}".format(ret, name))
                        ret = self[ret]
                    else:
                        logger.debug("Mapping {} to {}".format(name, ret))
                        super(Packages, self).__setitem__(String(ret), ret)

                    break

        if not ret:
            sp = StandardPackages()
            ret = sp[name]
            logger.debug("Found {} in standard library".format(name))

        if ret:
            super(Packages, self).__setitem__(name, ret)

        else:
            raise KeyError(name)

        return ret

    def get(self, name, default=None):
        # this should call missing if name not in self already
        ret = default
        if name in self:
            ret = self[name]

        else:
            try:
                ret = self.__missing__(name)
            except KeyError:
                pass

        return ret

    def __contains__(self, name):
        # this should call missing if k not in self already
        ret = True
        if not super(Packages, self).__contains__(name): 
            try:
                ret = True if self.__missing__(name) else False
            except KeyError:
                ret = False
        return ret

    def pop(self, *args, **kwargs):
        raise NotImplementedError()

    setdefault = pop
    update = pop
    clear = pop
    __delitem__ = pop
    __setitem__ = pop


class StandardPackages(Packages):
    def __init__(self):
        super(StandardPackages, self).__init__()

    def __missing__(self, name):
        ret = None

        # https://stackoverflow.com/a/4927129/5006
        if name in set(sys.builtin_module_names):
            ret = self.package_class(name, None)

        if not ret:
            basedir = Dirpath(sysconfig.get_python_lib(standard_lib=True))

            try:
                ret = self.package_class(name, basedir)

            except ValueError:
                ret = None

        if not ret:
            for basedir in self.search_paths():
                filepath = Filepath(basedir, name, ext="so")
                if filepath.exists():
                    ret = self.package_class(name, basedir)

        if not ret:
            raise KeyError(name)

        return ret

