# -*- coding: utf-8 -*-
from __future__ import unicode_literals, division, print_function, absolute_import

from testdata import TestCase
import testdata

from herd.path import Filepath


class FilepathTest(TestCase):
    def test_ext(self):
        fp = Filepath("foo.so")
        self.assertEqual("so", fp.ext)

        fp = Filepath("foo.bar.txt")
        self.assertEqual("txt", fp.ext)

