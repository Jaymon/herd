# -*- coding: utf-8 -*-
from __future__ import unicode_literals, division, print_function, absolute_import
from zipfile import ZipFile

import testdata

from herd.compat import *
from herd.serverless.interface.aws import (
    Role,
    Lambda,
    ApiGateway
)


class TestCase(testdata.TestCase):
    @classmethod
    def get_role(cls):
        desc = " ".join([
            "Autogenerated role for herd unit tests, this can be safely deleted",
            "but herd will re-create it if the unit tests are ran again",
        ])

        r = Role("herd-unittests", desc)
        #r.save()
        return r

    @classmethod
    def get_lambda(cls, name="herd_unittests", contents=None, environ=None):
        if not contents:
            contents = [
                "def handler(event, context):",
                "    '''Autogenerated lambda for herd unit tests, this can be safely deleted",
                "    but herd will re-create it if the unit tests are ran again'''",
                "    return {",
                "        'statusCode': 200,",
                "        'body': 1",
                "    }",
            ]

        filename = testdata.get_filename(name=name, ext="py")
        filepath = testdata.create_file(path=filename, contents=contents)

        r = cls.get_role()
        r.save()

        l = Lambda(filepath, role=r, environ=environ)
        l.save()
        return l

    @classmethod
    def get_api(cls):
        name = "herd-unittests"
        api = ApiGateway(name)
        api.save()
        return api


class ApiGatewayTest(TestCase):
    def test_crud(self):
        name = testdata.get_filename()

        api = ApiGateway(name)

        api.save()
        api_id = api.id
        api_name = api.name
        self.assertIsNotNone(api.id)

        api.save()
        self.assertEqual(api_id, api.id)
        self.assertEqual(api_name, api.name)

        api.delete()

    def test_add_lambda(self):
        api = self.get_api()
        func = self.get_lambda()

        url = api.add_lambda(func)

        res = testdata.fetch(url)
        self.assertEqual(200, res.code)
        self.assertEqual(1, int(res.body))

        api.delete()
        func.role.delete()
        func.delete()


class LambdaTest(TestCase):
    def test_bundle_dependencies(self):
        m = testdata.create_module(contents="import sys, os")

        filepath = testdata.create_file(testdata.get_filename("py"), contents=[
            "import boto3",
            "import {}".format(m),
            "import email",
            "",
            "def handler(event, context):",
            "    pass",
        ])

        l = Lambda(filepath, role=self.get_role())

        zip_path = l.bundle()
        with testdata.capture(True) as c:
            with ZipFile(zip_path, 'r') as z:
                z.printdir()

        self.assertTrue(filepath.basename in c)
        self.assertTrue(m in c)
        self.assertTrue("boto3" in c)

    def test_crud(self):
        """!!! This writes to AWS"""
        role = self.get_role()
        role.save()

        m = testdata.create_module(contents="import sys, os")
        filename = testdata.get_filename("py")
        contents = [
            "import testdata",
            "import json",
            "import {}".format(m),
            "",
            "def handler(event, context):",
            "    '''herd unit test function, this can be safely deleted'''",
            "    return {",
            "        'statusCode': 200,",
            "        'body': \"1\"",
            "    }",
        ]

        filepath = testdata.create_file(filename, contents=contents)

        l = Lambda(filepath, role=role)

        l.save()
        r = l.run()
        self.assertEqual(200, r["statusCode"])
        self.assertEqual("1", r["body"])

        contents[-2] = "        'body': \"2\""
        filepath.replace(contents)
        l.save()
        r = l.run()
        self.assertEqual(200, r["statusCode"])
        self.assertEqual("2", r["body"])

        l.delete()

    def test_environment(self):
        contents = [
            "import os",
            "#import pout",
            "def handler(event, context):",
            "    '''Autogenerated lambda for herd unit tests, this can be safely deleted",
            "    but herd will re-create it if the unit tests are ran again'''",
            "    #pout.v(os.environ)",
            "    #pout.v(context)",
            "    return {",
            "        'statusCode': 200,",
            "        'body': {'event': event, 'environ': {'foo': os.environ['FOO']}},",
            "    }",
        ]
        environ = {
            "FOO": 1,
            "BAR": 2,
        }

        l = self.get_lambda(contents=contents, environ=environ)

        r = l.run()
        self.assertEqual("1", r["body"]["environ"]["foo"])

