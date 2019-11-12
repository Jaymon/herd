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


from .compat import *
from .path import Filepath, Dirpath
from .utils import get_runtime


class Imports(set):
    def __init__(self, filepath, encoding="UTF-8"):
        super(Imports, self).__init__()

        open_kwargs = dict(mode='r', errors='replace', encoding=encoding)
        with codecs.open(filepath, **open_kwargs) as fp:
            body = fp.read().strip()

        self._find(body)

    def _find(self, body):
        # This is based on code from pout.reflect.Call._find_calls and
        # endpoints.reflection.ReflectClass.get_info

        def visit_Import(node):
            self.add(node.names[0].name.split(".")[0])

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

        node_iter.visit(ast.parse(body))


class Dependencies(set):
    def __init__(self, filepath):
        self.filepath = Filepath(filepath)

        standard_modules = StandardPackages()
        site_modules = SitePackages()
        local_modules = LocalPackages()

        im = Imports(self.filepath)
        for modulepath in im:
            self.update(self._resolve(
                modulepath,
                standard_modules,
                site_modules,
                local_modules
            ))

    def _resolve(self, modulepath, standard_modules, site_modules, local_modules):
        # we only want to resolve dependencies if this is not in the standard library
        module_name = modulepath.split(".")[0]

        ret = set()

        if module_name not in standard_modules:
            name = ""
            if module_name in site_modules:
                name = site_modules[module_name]
            else:
                if module_name in local_modules:
                    name = local_modules[module_name]

            if name:
                ret.add(name)
                for require_modulepath in name.requires():
                    ret.update(self._resolve(
                        require_modulepath,
                        standard_modules,
                        site_modules,
                        local_modules
                    ))

        #pout.b(module_name)
        #pout.v(name, ret)
        return ret


class Package(String):
    @property
    def filepath(self):
        """always reteurns a filepath for the module, this could either be self.name.py
        or __init__.py"""
        p = self.path
        if isinstance(p, Dirpath):
            p = Filepath(p, "__init__.py")
        return p

    @property
    def path(self):
        """Returns the path for the module, this can be a directory or file"""
        return self._find_path(self, self.basedir)

    @classmethod
    def _find_path(cls, name, basedir):
        ret = ""
        name = name.replace(".", "/")
        p = Filepath(basedir, name, ext=".py")
        if p.exists():
            ret = p
        else:
            p = Dirpath(basedir, name)
            if p.exists():
                ret = p
        return ret

    def __new__(cls, name, basedir):
        instance = super(Package, cls).__new__(cls, name)
        instance.basedir = Dirpath(basedir)
        return instance

    def names(self):
        return [self]

    def requires(self):
        return set()

    def is_package(self):
        """returns True if this package is a directory"""
        p = self._find_path(self, self.basedir)
        return isinstance(p, Dirpath)

    def is_module(self):
        """returns True if this package is a module file"""
        return not self.is_package()

    def submodules(self):
        if self.is_package():
            for root_dir, dirs, files in self.path:
                relative_dir = root_dir.replace(self.basedir, "").strip("/")
                modpath = relative_dir.replace("/", ".")
                if Filepath(root_dir, "__init__.py").exists():
                    if modpath != self:
                        yield Package(modpath, self.basedir)

                    for basename in files:
                        if basename.endswith(".py") and basename != "__init__.py":
                            fp = Filepath(basename)
                            name = ".".join([modpath, fp.fileroot])
                            yield Package(name, self.basedir)

    def modules(self):
        """like .submodules() put will also yield self"""
        yield self
        for sm in self.submodules():
            yield sm


class SitePackage(Package):
    @classmethod
    def _get_toplevel_names(cls, infopath):
        """module_name (eg, python-dateutil) needs to read *.dist-info/top_level.txt
        to get the actual name (eg, dateutil)

        :param infopath: string, the directory path the the .dist-info folder
        :returns: the toplevel package name that scripts would import
        """
        # https://setuptools.readthedocs.io/en/latest/formats.html#sources-txt-source-files-manifest
        filepath = Filepath(infopath, "top_level.txt")
        return [line.strip() for line in filepath]

    @classmethod
    def _get_pypi_names(cls, infopath):
        m = re.match("^([0-9a-zA-Z_]+)", Dirpath(infopath).basename)
        name = m.group(1)
        return [name, name.replace("_", "-")]

    @classmethod
    def _get_semver_name(self, name):
        """removes things like the semver version

        :param name: string, the complete package name with things like semver
        :returns: the actual package name as pypi sees it
        """
        m = re.match("^([0-9a-zA-Z_-]+)", name.strip())
        return m.group(1)

    def __new__(cls, infopath):
        infopath = Dirpath(infopath)
        basedir = infopath.dirname

        # find the actual real name of the package from all our options
        names = cls._get_toplevel_names(infopath)
        for name in names:
            p = cls._find_path(name, basedir)
            if p:
                break

        instance = super(SitePackage, cls).__new__(cls, name, basedir)
        instance.infopath = infopath
        return instance

    def names(self):
        return self._get_toplevel_names(self.infopath) + self._get_pypi_names(self.infopath)

    def requires(self):
        """returns the immediate defined dependencies for this package

        this doesn't normalize the module name or anything

        :returns: set, the required packages per configuration
        """
        ret = set()

        jsonpath = Filepath(self.infopath, "metadata.json")
        if jsonpath.exists():
            json_d = json.loads(jsonpath.contents())

            for d in json_d.get("run_requires", []):
                for name in d.get("requires", []):
                    ret.add(self._get_semver_name(name))

        else:
            txtpath = Filepath(self.infopath, "METADATA")
            if txtpath.exists():
                for line in txtpath:
                    if line.startswith("Requires-Dist"):
                        # TODO -- this line can have "extras == '...' info that
                        # means this package is optional and might not be
                        # installed
                        name = self._get_semver_name(line.split(":")[1].strip())
                        if name:
                            ret.add(name)

        return ret


class LocalPackage(Package):
    def requires(self):
        ret = set()

        for m in self.modules():
            im = Imports(m.filepath)
            ret.update(im)

        return ret


class Packages(dict):
    #instance = None

    package_class = Package

#     @classmethod
#     def get_instance(cls, *args, **kwargs):
#         """get the singleton"""
#         if not cls.instance:
#             cls.instance = cls(*args, **kwargs)
#         return cls.instance

    def __init__(self, *args, **kwargs):
        self._readonly = False
        super(Packages, self).__init__()
        self.populate(*args, **kwargs)
        self._readonly = True

    def __setitem__(self, k, v):
        if self._readonly:
            raise NotImplementedError()
        return super(Packages, self).__setitem__(k, v)

    def pop(self, *args, **kwargs):
        raise NotImplementedError()

    setdefault = pop
    update = pop
    clear = pop
    __delitem__ = pop

    def _add_packages(self, path):
        if path.exists():
            for root_dir, dirs, files in path:
                for basename in files:
                    if basename.endswith(".py"):
                        fp = Filepath(basename)
                        name = fp.fileroot
                        self[name] = self.package_class(name, root_dir)

                for name in dirs:
                    fp = Filepath(root_dir, name, "__init__.py")
                    if fp.exists():
                        self[String(name)] = self.package_class(name, root_dir)
                break


class StandardPackages(Packages):
    def populate(self):
        for name in sys.builtin_module_names:
            self[String(name)] = None

        path = Dirpath(sysconfig.get_python_lib(standard_lib=True))
        self._add_packages(path)


class SitePackages(Packages):
    package_class = SitePackage
    def populate(self):
        for basedir in sys.path:
            infopaths = glob.glob(os.path.join(basedir, "*.dist-info"))
            for infopath in infopaths:
                p = SitePackage(infopath)
                for name in p.names():
                    self[name] = p


class LocalPackages(Packages):
    package_class = LocalPackage
    def populate(self):
        runtime_dir = "/{}".format(get_runtime())

        for basedir in sys.path:
            if runtime_dir in basedir: continue
            if glob.glob(os.path.join(basedir, "*.dist-info")): continue

            basedir = Dirpath(basedir)
            self._add_packages(basedir)


