# -*- coding: utf-8 -*-
from __future__ import unicode_literals, division, print_function, absolute_import


from testdata import TestCase
import testdata


from herd.reflection import (
    Imports,
    Dependencies,
    StdlibPackages,
    SitePackages,
    LocalPackages
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
            "",
            "def do():",
            "    import bar1",
            "    from bar2 import foo",
            "    from bar3 import che as baz",
        ])

        im = Imports(m.path)
        self.assertEqual(10, len(im))
        for x in range(1, 7):
            self.assertTrue("foo{}".format(x) in im)
        for x in range(1, 4):
            self.assertTrue("bar{}".format(x) in im)

        m = testdata.create_module(contents=[
            "from .foo12 import foo13",
            "from foo14 import foo15",
        ])

        im = Imports(m.path)
        self.assertEqual(1, len(im))
        self.assertTrue("foo14" in im)


class DependenciesTest(TestCase):
    def test_stdlib(self):
        for modpath in ["sys", "os", "os.path", "email"]:
            d = Dependencies(modpath)
            self.assertEqual(0, len(d))

    def test_site(self):
        d = Dependencies("boto3")
        self.assertLess(0, len(d))

    def test_local_module(self):
        m = testdata.create_module(contents=[
            "import boto3",
            "import os",
            "import sys",
        ])

        d = Dependencies(m)
        self.assertLess(0, len(d))

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

    def test_different_toplevel_package_name(self):
        d = Dependencies("dateutil")
        d2 = Dependencies("python-dateutil")
        self.assertEqual(d.name, d2.name)


class StdlibPackagesTest(TestCase):
    def test_create(self):
        s = StdlibPackages()

        for modpath in ["sys", "os", "email"]:
            self.assertTrue(modpath in s, modpath)


class SitePackagesTest(TestCase):
    def test_print(self):
        self.skip_test()
        s1 = SitePackages()
        #pout.v(s)
        s2 = StdlibPackages()
        #pout.v(s)

        l = list(s1.keys()) + list(s2.keys())
        l.sort()
        pout.v(l)

    def test_create(self):
        s = SitePackages()

        p = s["dateutil"]
        self.assertEqual("dateutil", p)

        p = s["python-dateutil"]
        self.assertEqual("dateutil", p)

        p = s["python_dateutil"]
        self.assertEqual("dateutil", p)

    def test_requires(self):
        s = SitePackages()
        p = s["boto3"]
        self.assertLess(0, len(p.requires()))


class LocalPackagesTest(TestCase):
    def test_create(self):
        m = testdata.create_module(contents=[])
        s = LocalPackages()
        self.assertTrue(m in s)


    def test_submodules(self):
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

        s = LocalPackages()
        p = s["foo"]

        sms = set([sm for sm in p.submodules()])
        self.assertEqual(expected, sms)

        sms = set([sm for sm in p.modules()])
        pout.v(sms)
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

        s = LocalPackages()
        p = s["foo"]
        expected = set(["boto3", "sys", "os"])
        self.assertEqual(expected, p.requires())

