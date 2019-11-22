# -*- coding: utf-8 -*-
from __future__ import unicode_literals, division, print_function, absolute_import

from testdata import TestCase
import testdata

from herd.utils import EnvironParser, Environ


class EnvironParserTest(TestCase):
    def test___init__(self):
        unknown_args = [
            b'--FOO=1',
            b'--BAR=2'
        ]

        e = EnvironParser(unknown_args)
        self.assertEqual("1", e["FOO"])
        self.assertEqual("2", e["BAR"])

        unknown_args = [
            b'--FOO=1',
            b'--FOO=2',
            b'--BAR=3'
        ]

        e = EnvironParser(unknown_args)
        self.assertEqual(["1", "2"], e["FOO"])
        self.assertEqual("3", e["BAR"])


class EnvironTest(TestCase):
    def test_normalize(self):
        e = Environ()
        e["FOO"] = 1
        self.assertEqual("1", e["foo"])
        self.assertTrue("foo" in e)

