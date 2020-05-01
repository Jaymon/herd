# -*- coding: utf-8 -*-
from __future__ import unicode_literals, division, print_function, absolute_import


from .interface.aws import Role, Lambda, ApiGateway, Region


class Function(object):
    def __init__(
        self,
        filepath,
        environ=None,
        role_name="herd-lambda-role",
        api_name="herd-lambda-api",
        stage="DEFAULT",
        region_name="",
        **options
    ):

        region_name = Region(region_name)

        role = Role(role_name)
        role.save()

        # TODO -- we might have to delay until the IAM role propogates if it
        # creates the role, the first time running this I got this error:
        # botocore.errorfactory.InvalidParameterValueException: An error occurred
        # (InvalidParameterValueException) when calling the CreateFunction operation:
        # The role defined for the function cannot be assumed by Lambda
        #
        # but it worked the second time it was ran

        func = Lambda(filepath, role=role, environ=environ, region_name=region_name)
        func.save()

        api = ApiGateway(api_name, region_name=region_name)
        api.save()

        self.url = api.add_lambda(func, stage=stage, **options)
        self.api = api
        self.func = func
        self.role = role

