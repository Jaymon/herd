# -*- coding: utf-8 -*-
from __future__ import unicode_literals, division, print_function, absolute_import


from .interface.aws import Role, Lambda, ApiGateway


class Serverless(object):
    def __init__(self, filepath, role_name, stage, region_name=""):

        role = Role(role_name)
        if not role.exists():
            role.save()

        func = Lambda(filepath, role=role, region_name=region_name)
        func.save()

        api = ApiGateway(func, stage=stage)
        api.save()


        # TODO -- get the dependencies by getting all the import statements from
        # filepath



