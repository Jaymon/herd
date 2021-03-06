# -*- coding: utf-8 -*-
from __future__ import unicode_literals, division, print_function, absolute_import

from testdata import TestCase
import testdata

from herd.compat import *
from herd.reflection import (
    Imports,
    Dependencies,
    StandardPackages,
    Packages
)


class ImportsTest(TestCase):
    def test___init__(self):

        m = testdata.create_module(contents=[
            "import foo1",
            "from foo2 import bar",
            "from foo3 import bar as che",
            "import foo4 as boo",
            "import foo5.zoo",
            "from foo6 import *",
            "from . import foo7, foo8",
            "from .foo12 import foo13",
            "from foo9 import foo10, foo11",
            "from che1 import (",
            "    cheA,",
            "    cheB,",
            "    cheC,",
            ")",
            "import che2, che3",
            "",
            "def do():",
            "    import bar1",
            "    from bar2 import foo",
            "    from bar3 import che as baz",
        ])

        im = Imports(m.path)
        self.assertEqual(13, len(im))
        for x in range(1, 7):
            self.assertTrue("foo{}".format(x) in im)
        for x in range(1, 4):
            self.assertTrue("bar{}".format(x) in im)
        for x in range(1, 4):
            self.assertTrue("che{}".format(x) in im)

        m = testdata.create_module(contents=[
            "from .foo12 import foo13",
            "from foo14 import foo15",
        ])

        im = Imports(m.path)
        self.assertEqual(1, len(im))
        self.assertTrue("foo14" in im)


class PackagesTest(TestCase):
    def test___missing__(self):
        ps = Packages()

        p1 = ps["easy_install"]
        self.assertEqual(1, len(ps))

        p2 = ps["setuptools"]
        self.assertEqual(p1.infopath, p2.infopath)
        self.assertEqual(2, len(ps))

        p3 = ps["pkg_resources"]
        self.assertEqual(p3.infopath, p2.infopath)
        self.assertEqual(3, len(ps))

    def test_no_package(self):
        ps = Packages()

        with self.assertRaises(KeyError):
            ps["foo-bar-{}".format(testdata.get_ascii())]

    def test_readonly(self):
        ps = Packages()
        with self.assertRaises(NotImplementedError):
            ps["foobar"] = 1

    def test_different_pypi_and_module_names(self):
        ps = Packages()

        p = ps["python-dateutil"]
        self.assertEqual("dateutil", p)

    def test_requires(self):
        ps = Packages()

        p = ps["boto3"]
        r = p.requires()
        for name in ["botocore", "jmespath", "s3transfer"]:
            self.assertTrue(name in r)

    def test_standard(self):
        ps = Packages()

        p = ps["thread"]
        self.assertTrue(p.is_standard())

        p = ps["sys"]
        self.assertTrue(p.is_standard())

        # zlib is an .so file in lib-dynload
        p = ps["zlib"]
        self.assertTrue(p.is_standard())

    def test_modules_submodules(self):
        path = testdata.create_modules({
            "foo": [
                "import boto3",
            ],
            "foo.bar": [
                "import os",
                "import sys",
            ],
            "foo.che": [
                "from . import bar",
            ],
            "foo.bar2.che2": [
            ]
        })

        expected = set([
            "foo.che",
            "foo.bar",
            "foo.bar2",
            "foo.bar2.che2"
        ])

        ps = Packages()
        p = ps["foo"]

        sms = set([sm for sm in p.submodules()])
        self.assertEqual(expected, sms)

        sms = set([sm for sm in p.modules()])
        self.assertTrue("foo" in sms)

    def test_requires(self):
        path = testdata.create_modules({
            "foo": [
                "import boto3",
            ],
            "foo.bar": [
                "import os",
                "import sys",
            ],
            "foo.che": [
                "from . import bar",
            ],
            "foo.bar2.che2": [
                "from .. import bar"
            ]
        })

        ps = Packages()
        p = ps["foo"]
        expected = set(["boto3", "sys", "os"])
        self.assertEqual(expected, p.requires())

    def test_has_shared_library(self):
        modpath = testdata.create_package(contents=[])
        shared_library = testdata.create_file("foo.so", tmpdir=modpath.directory)

        ps = Packages()
        p = ps[modpath]
        self.assertTrue(p.has_shared_library())


class DependenciesTest(TestCase):
    def test_encoding(self):
        m = testdata.create_module(contents=[
            "# -*- coding: utf-8 -*-",
            "from __future__ import unicode_literals, division, print_function, absolute_import",
        ])

        d = Dependencies(m.path)

#     def test_stdlib(self):
#         for modpath in ["sys", "os", "os.path", "email"]:
#             d = Dependencies(modpath)
#             self.assertEqual(0, len(d))
# 
#     def test_site(self):
#         d = Dependencies("boto3")
#         self.assertLess(0, len(d))

    def test_local_module(self):

        m = testdata.create_module(contents=[
            "import boto3",
            "import os",
            "import sys",
        ])

        d = Dependencies(m.path)
        self.assertLess(0, len(d))

    def test_standard(self):
        """make sure standard modules are ignored"""
        m = testdata.create_module(contents=[
            "import json",
            "import os",
            "import base64",
        ])

        d = Dependencies(m.path)
        self.assertEqual(0, len(d))

    def test_ignore(self):
        m = testdata.create_module(contents=[
            "import os",
            "import json",
            "import boto3",
            "import base64",
            "from botocore.exceptions import ClientError",
        ])

        d = Dependencies(m.path, ["^boto3(?:\.|$)", "^botocore(?:\.|$)"])
        self.assertEqual(0, len(d))

    def test_local_package(self):
        path = testdata.create_modules({
            "foo": [
                "import boto3",
            ],
            "foo.bar": [
                "import os",
                "import sys",
            ],
            "foo.che": [
                "from . import bar",
            ],
            "foo.bar2.che2": [
            ]
        })

        d = Dependencies("foo")
        self.assertLess(0, len(d))

#     def test_different_toplevel_package_name(self):
#         d = Dependencies("dateutil")
#         d2 = Dependencies("python-dateutil")
#         self.assertEqual(d.name, d2.name)


class StandardPackagesTest(TestCase):
    def test___contains__(self):
        s = StandardPackages()

        for modpath in ["sys", "os", "email"]:
            self.assertTrue(modpath in s, modpath)

    def test_modules(self):
        """Make sure .py modules are found"""
        s = StandardPackages()
        p = s["json"]
        self.assertTrue(p is not None)


# class SitePackagesTest(TestCase):
#     def test_setuptools(self):
#         s = SitePackages()
#         p = s["setuptools"]
#         pout.v(p)
# 
# 
#     def test_print(self):
#         self.skip_test()
#         s1 = SitePackages()
#         #pout.v(s)
#         s2 = StandardPackages()
#         #pout.v(s)
# 
#         l = list(s1.keys()) + list(s2.keys())
#         l.sort()
#         pout.v(l)
# 
#     def test_create(self):
#         s = SitePackages()
# 
#         p = s["dateutil"]
#         self.assertEqual("dateutil", p)
# 
#         p = s["python-dateutil"]
#         self.assertEqual("dateutil", p)
# 
#         p = s["python_dateutil"]
#         self.assertEqual("dateutil", p)
# 
#     def test_requires(self):
#         s = SitePackages()
#         p = s["boto3"]
#         self.assertLess(0, len(p.requires()))


# class LocalPackagesTest(TestCase):
#     def test_create(self):
#         m = testdata.create_module(contents=[])
#         s = LocalPackages()
#         self.assertTrue(m in s)
# 
# 
#     def test_requires(self):
#         path = testdata.create_modules({
#             "foo": [
#                 "import boto3",
#             ],
#             "foo.bar": [
#                 "import os",
#                 "import sys",
#             ],
#             "foo.che": [
#                 "from . import bar",
#             ],
#             "foo.bar2.che2": [
#                 "from .. import bar"
#             ]
#         })
# 
#         s = LocalPackages()
#         p = s["foo"]
#         expected = set(["boto3", "sys", "os"])
#         self.assertEqual(expected, p.requires())
# 
