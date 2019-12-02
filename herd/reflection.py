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




#     def resolve3(self, path):
#         packages = Packages()
#         seen = set()
#         filepath = Filepath(path)
#         if filepath.exists():
#             self.update(self._resolve(filepath, packages, seen))
# 
#         else:
#             # do we have a module path?
#             try:
#                 p = packages[path]
#             except ValueError:
#                 raise ValueError("Could not resolve path {}".format(path))
# 
#             else:
#                 for sm in p.modules():
#                     self.update(self._resolve(sm.filepath, packages, seen))
# 
#     def _resolve3(self, filepath, packages, seen):
#         ret = set()
#         im = Imports(filepath)
#         for modulename in im:
#             try:
#                 p = packages[modulename]
# 
#             except KeyError as e:
#                 logger.debug("Missing dependency {} for {}".format(modulename, filepath))
# 
#             else:
#                 if p not in seen:
#                     seen.add(p)
#                     if not p.is_standard():
#                         ret.add(p)
#                         ret.update(self._resolve(p.filepath, packages, seen))
# 
#         return ret
# 
# 





#     def resolve2(self):
#         standard_modules = StandardPackages()
#         site_modules = SitePackages()
#         local_modules = LocalPackages()
# 
#         im = Imports(self.filepath)
#         seen = set()
#         for modulepath in im:
#             self.update(self._resolve(
#                 modulepath,
#                 seen,
#                 standard_modules,
#                 site_modules,
#                 local_modules
#             ))
# 
#     def _resolve2(self, modulepath, seen, standard_modules, site_modules, local_modules):
#         # we only want to resolve dependencies if this is not in the standard library
#         module_name = modulepath.split(".")[0]
#         ret = set()
#         if module_name not in seen:
#             if module_name not in self:
#                 if module_name not in standard_modules:
#                     name = ""
#                     if module_name in site_modules:
#                         name = site_modules[module_name]
#                     else:
#                         if module_name in local_modules:
#                             name = local_modules[module_name]
# 
#                     if name:
#                         ret.add(name)
#                         seen.add(module_name)
# 
#                         for require_modulepath in name.requires():
#                             #pout.v(name, require_modulepath, seen)
#                             ret.update(self._resolve(
#                                 require_modulepath,
#                                 seen,
#                                 standard_modules,
#                                 site_modules,
#                                 local_modules
#                             ))
# 
#         return ret
# 
# 



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
            for root_dir, files, dirs in basedir:
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






















class Package2(String):
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
        ret = getattr(self, "_requires_set", None)
        if ret is None:
            ret = self._requires()

            # remove itself as a dependency if present (I'm looking at you pycrypto)
            ret.discard(self)
            self._requires_set = ret

        return ret

    def _requires(self):
        ret = set()

        for m in self.modules():
            im = Imports(m.filepath)
            ret.update(im)

        return ret

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


class SitePackage(Package2):
    @classmethod
    def _get_toplevel_names(cls, infopath):
        """module_name (eg, python-dateutil) needs to read *.dist-info/top_level.txt
        to get the actual name (eg, dateutil)

        :param infopath: string, the directory path the the .dist-info folder
        :returns: the toplevel package name that scripts would import
        """
        ret = set()
        infopath = Path.create(infopath)
        if infopath.isfile():
            names = cls._get_pypi_names(infopath)
            for name in names:
                p = Dirpath(infopath.dirname, name)
                if p.exists():
                    ret.add(name)

                p = Filepath(infopath.dirname, name, ext="py")
                if p.exists():
                    ret.add(name)

        else:
            # https://setuptools.readthedocs.io/en/latest/formats.html#sources-txt-source-files-manifest
            filepath = Filepath(infopath, "top_level.txt")
            ret = set((line.strip() for line in filepath))

        return ret

    @classmethod
    def _get_pypi_names(cls, infopath):
        m = re.match("^([0-9a-zA-Z_]+)", Dirpath(infopath).basename)
        name = m.group(1)
        return set([name, name.replace("_", "-")])

    @classmethod
    def _get_semver_name(self, name):
        """removes things like the semver version

        :param name: string, the complete package name with things like semver
        :returns: the actual package name as pypi sees it
        """
        m = re.match("^([0-9a-zA-Z_-]+)", name.strip())
        return m.group(1)

    def __new__(cls, infopath):
        infopath = Path.create(infopath)
        basedir = infopath.dirname

        # find the actual real name of the package from all our options
        name = ""
        names = cls._get_toplevel_names(infopath)
        for name in names:
            p = cls._find_path(name, basedir)
            if p:
                break

        if not name:
            raise ValueError("{} does not correspond to a site package".format(infopath))

        instance = super(SitePackage, cls).__new__(cls, name, basedir)
        instance.infopath = infopath
        return instance

    def names(self):
        return self._get_toplevel_names(self.infopath) & self._get_pypi_names(self.infopath)

    def _requires(self):
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
            if self.infopath.isfile():
                txtpath = self.infopath
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

        ret.update(super(SitePackage, self)._requires())
        return ret


class LocalPackage(Package2):
    pass
#     def requires(self):
#         ret = set()
# 
#         for m in self.modules():
#             im = Imports(m.filepath)
#             ret.update(im)
# 
#         return ret


class Packages2(dict):
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
        ret = 0
        path = Dirpath(path)
        if path.exists():
            for root_dir, dirs, files in path:
                for basename in files:
                    if basename.endswith(".py"):
                        fp = Filepath(basename)
                        name = fp.fileroot
                        if name not in self:
                            self[name] = self.package_class(name, root_dir)
                            ret += 1

                for name in dirs:
                    fp = Filepath(root_dir, name, "__init__.py")
                    if fp.exists():
                        name = String(name)
                        if name not in self:
                            self[name] = self.package_class(name, root_dir)
                            ret += 1
                break

        return ret


class StandardPackages2(Packages2):
    """The packages that are part of the python distribution, the standard library

    https://stackoverflow.com/a/46441687/5006
    """
    def populate(self):
        # https://stackoverflow.com/a/4927129/5006
        for name in sys.builtin_module_names:
            self[String(name)] = None

        path = Dirpath(sysconfig.get_python_lib(standard_lib=True))
        count = self._add_packages(path)
        if count > 0:
            logger.debug("Standard packages found at: {}".format(path))


class SitePackages(Packages2):
    """The packages found in things like the site-packages directory

    https://stackoverflow.com/a/6464112/5006
    """
    package_class = SitePackage

    def populate(self):
        for basedir in sys.path:
            infopaths = glob.glob(os.path.join(basedir, "*.*-info"))
            if infopaths:
                logger.debug("Site packages found at: {}".format(basedir))
                for infopath in infopaths:
                    try:
                        p = SitePackage(infopath)
                        for name in p.names():
                            self[name] = p

                    except ValueError:
                        pass

                # pick up any straggling packages that don't have *-info
                # information directories (I'm looking at you pycrypto)
                package_class = self.package_class
                self.package_class = LocalPackage
                self._add_packages(basedir)
                self.package_class = package_class


class LocalPackages(Packages2):
    package_class = LocalPackage
    def populate(self):
        runtime_dir = "/{}".format(get_runtime())

        for basedir in sys.path:
            if runtime_dir in basedir: continue
            if glob.glob(os.path.join(basedir, "*.*-info")): continue

            basedir = Dirpath(basedir)
            count = self._add_packages(basedir)
            if count > 0:
                logger.debug("Local packages found at: {}".format(basedir))


