# -*- coding: utf-8 -*-
from __future__ import unicode_literals, division, print_function, absolute_import

from .interface.aws_test import TestCase
#from testdata import TestCase
import testdata


class Client(testdata.ModuleCommand):
    name = "herd"


class InfoTest(TestCase):
    def test_info(self):
        c = Client()
        r = c.run("info")
        self.assertTrue("Available Regions" in r)

