# -*- coding: utf-8 -*-
from __future__ import unicode_literals, division, print_function, absolute_import
import json
import runpy
import logging
import sys
import inspect
import os
import re
from zipfile import ZipFile

import boto3
from botocore.exceptions import ClientError

from ...path import Tempdir, Filepath
from ...reflection import Dependencies


logger = logging.getLogger(__name__)


class AWS(object):
    """Base class that standardizes the interface for all the services"""

    @property
    def client_name(self):
        """returns the client_name, by default this will use the class name but this
        can be easily overidden in the child classes"""
        return self.__class__.__name__.lower()

    @property
    def client(self):
        """return a boto3 client for the service, uses self.client_name"""
        return boto3.client(self.client_name)

    @property
    def region_name(self):
        """Return the region name of the service"""
        # https://stackoverflow.com/a/55749807/5006
        return self.client.meta.region_name

    def exists(self):
        """Return True if the service exists

        :returns: boolean, True if the resource exists, False otherwise
        """
        return self.load()

    def load(self):
        """Load the information from AWS

        :returns: boolean, True if something was loaded, False otherwise
        """
        if getattr(self, "raw", None) is None:
            try:
                self.raw = self._load()

            except (ClientError, ValueError) as e:
                self.raw = {}

        return True if self.raw else False

    def delete(self):
        """delete the resource"""
        raise NotImplementedError()


class ApiGateway(AWS):
    """The API Gateway resource

    An instance of this class will represent an API Gateway on AWS, this will allow
    a lambda function to be tied to a public url so you can call the lambda function
    from a webhook or the like

    https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/apigateway.html

    This uses v1 of the API Gateway since v2 deals with websockets
    """
    @property
    def id(self):
        """returns the api unique id that is returned from AWS"""
        return self.raw["id"]

    @property
    def url(self):
        """Returns the public url of this api gateway"""
        return 'https://{}.execute-api.{}.amazonaws.com/{}/'.format(
            self.id,
            self.region_name,
            self.stage,
        )

    @property
    def uri(self):
        """The api gateway uri that is used to connect lambda to the api, this is
        needed internally and probably not needed externally, if you want the public
        api use self.url"""
        return "arn:aws:apigateway:{}:lambda:path/2015-03-31/functions/{}/invocations".format(
            self.region_name,
            self.func.arn
        )

    @property
    def client(self):
        region_name = self.func.region_name or None
        return boto3.client(self.client_name, region_name=region_name)

    def __init__(self, func, stage="DEV"):
        """Create an instance of the api for func in the stage environment

        :param func: Lambda, a lambda function resource
        :param stage: string, the environment name (eg, DEV, PROD, STAGE, TEST)
        """
        self.name = func.name
        self.description = "API Gateway for {} lambda function {}".format(func.region_name, func.name)
        self.func = func
        self.stage=stage

    def _load(self):
        client = self.client
        # this isn't ideal but names aren't unique for the apis and so we have
        # to get all the apis and then work through them to find the right api,
        # and lambda resources don't have a unique id either so we can't use
        # that, so we are assuming name will be unique and the lambda and api
        # resources will share the same name
        # https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/apigateway.html#APIGateway.Client.get_rest_apis
        raw = None
        # TODO -- this tops out at 500, we should keep paginating 500 at a time
        # but that seems like overkill at this time
        res = client.get_rest_apis(limit=500)
        for raw in res["items"]:
            if raw["name"] == self.name:
                break

        if not raw:
            raise ValueError("Could not find API Gateway with name {}".format(self.name))

        return raw

    def save(self):
        """Actually create/update the api endpoint and hook it into lambda"""
        client = self.client

        if not self.exists():
            self.raw = client.create_rest_api(
                name=self.name,
                description=self.description,
                endpointConfiguration={"types": ["EDGE"]},
                apiKeySource="HEADER",
            )

        api = self.raw

        # find the existing endpoint
        res2 = client.get_resources(restApiId=api["id"])
        resource = [d for d in res2["items"] if d["path"] == "/"][0]

        # resource will support any http method (eg, GET, POST)
        try:
            res4 = client.put_method(
                restApiId=api['id'],
                resourceId=resource['id'],
                httpMethod='ANY',
                authorizationType='NONE'
            )

        except client.exceptions.ConflictException as e:
            pass

        else:
            client.put_method_response(
                restApiId=api["id"],
                resourceId=resource["id"],
                httpMethod='ANY',
                statusCode='200',
                responseModels={'application/json': 'Empty'}
            )

#         client.delete_integration(
#             restApiId=api['id'],
#             resourceId=resource['id'],
#             httpMethod='ANY',
#         )

        # Add an integration method to the api resource
        # !!! Not sure why this doesn't need to be conflict gated
        client.put_integration(
            restApiId=api['id'],
            resourceId=resource['id'],
            httpMethod='ANY',
            type='AWS_PROXY',
            integrationHttpMethod='POST',
            uri=self.uri,
        )
        client.put_integration_response(
            restApiId=api["id"],
            resourceId=resource["id"],
            httpMethod='ANY',
            statusCode='200',
            responseTemplates={'application/json': ''}
        )

        res6 = client.create_deployment(
            restApiId=api["id"],
            stageName=self.stage.lower() or None
        )

        # add the lambda permission so this api can invoke it
        func_client = self.func.client
        try:
            perm_arn = 'arn:aws:execute-api:{}:{}:{}/*/*/'.format(
                self.region_name,
                self.func.role.account_id,
                api["id"],
            )
            res7 = func_client.add_permission(
                FunctionName=self.func.name,
                StatementId='{}-invoke'.format(self.func.name),
                Action='lambda:InvokeFunction',
                Principal='apigateway.amazonaws.com',
                SourceArn=perm_arn
            )

        except func_client.exceptions.ResourceConflictException as e:
            pass

    def delete(self):
        if self.exists():
            ret = True
            api_id = self.raw["id"]
            client = self.client
            try:
                # ??? Does deleting the rest api delete all the methods and
                # integrations? It does not delete the role or the permission
                # I'll bet
                client.delete_rest_api(restApiId=api_id)

            except ClientError as e:
                logging.error(e)
                ret = False

            return ret


class Role(AWS):
    """Represent an AWS IAM role

    https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/iam.html
    """
    client_name = "iam"

    @property
    def account_id(self):
        """get the AWS account id"""
        # sadly, I couldn't find a better way to find this
        return self.arn.split(":")[4]

    @property
    def arn(self):
        return self.raw["Role"]["Arn"]

    def __init__(self, name, description=""):
        """create a representation of the role at name

        :param name: string, the roles name
        """
        self.name = name
        self.policy_documents = {}
        self.description = description
#         if not self.exists():
#             self.save()

    def _load(self):
        return self.client.get_role(RoleName=self.name)

    def save(self):
        self.policy_documents["AssumeRolePolicyDocument"] = {
            "Version": "2012-10-17",
            "Statement": [
                {
                "Effect": "Allow",
                "Principal": {
                    "Service": [
                        "lambda.amazonaws.com",
                        "apigateway.amazonaws.com"
                    ]
                },
                "Action": "sts:AssumeRole"
                }
            ]
        }

        iam_client = self.client
        # https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/iam.html#IAM.Client.create_role
        self.raw = iam_client.create_role(
            RoleName=self.name,
            Description=self.description,
            **{i[0]: json.dumps(i[1]) for i in self.policy_documents.items()}
        )

    def delete(self):
        """Delete the IAM role

        https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/iam.html#IAM.Client.delete_role
        """
        client = self.client
        client.delete_role(RoleName=self.name)


class Lambda(AWS):
    """Represents a lambda function"""

    timeout = 300 # Maximum allowable timeout

    @property
    def arn(self):
        # ARN format="arn:aws:lambda:REGION:ACCOUNT_ID:function:FUNCTION_NAME"
        return self.raw["Configuration"]["FunctionArn"]

    @property
    def runtime(self):
        info = sys.version_info
        return "python{}.{}".format(info.major, info.minor)
        #return os.path.basename(sys.executable)

    @property
    def handler(self):
        return "{}.{}".format(self.module_name, self.function_name)

    @property
    def client(self):
        region_name = self._region_name or None
        return boto3.client(self.client_name, region_name=region_name)

    def __init__(self, filepath, role, name="", region_name=""):
        """create a representation of the lambda function that will run filepath

        :param filepath: string, the file path to a python file that will uploaded
            to lambda, this file should have a function that matches the definition:
                NAME(event, context)
            which is what lambda will invoke when ran
        :param role: Role, the role to use for this lambda function
        :param name: string, if you want to give the lambda function a different
            name than the basename of the filepath
        :param region_name: if you want to use a different region name then the 
            default defined in aws config or AWS_DEFAULT_REGION
        """
        # ??? -- we could also do this with regex looking for def NAME(event, context):
        # but that would make getting the description harder
        self.filepath = Filepath(filepath)
        self._region_name = region_name
        self.role = role

        module = runpy.run_path(filepath)
        for n, v in module.items():
            if inspect.isfunction(v):
                # !!! py2 only
                #pout.v(inspect.signature(v))
                s = inspect.getargspec(v)
                if len(s[0]) == 2 and s[0][0] == "event" and s[0][1] == "context":
                    self.function_name = n
                    self.description = inspect.getdoc(v)
                    break

        self.module_name = self.filepath.fileroot

        # name can use only letters, numbers, hyphens, or underscores with no spaces
        if name:
            self.name = name

        else:
            self.name = self.module_name

    def _load(self):
        client = self.client
        return client.get_function(FunctionName=self.name)

    def bundle(self):
        self.basedir = Tempdir()
        self.zipfilepath = os.path.join(self.basedir, "lambda.zip")

        d = Dependencies(self.filepath)
        pout.v(d)
        return

        with ZipFile(self.zipfilepath, 'w') as z:
            # TODO test with full filepath for filepath to make sure it still
            # puts the file at the top level of the zipfile
            z.write(self.filepath)

    def save(self):
        client = self.client
        self.basedir = tempfile.mkdtemp(dir=tempfile.gettempdir())
        self.zipfilepath = os.path.join(self.basedir, "lambda.zip")
        role = self.role


        with open(self.zipfilepath, 'rb') as f:
            zipped_code = f.read()

        if self.exists():
            # update
            # https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/lambda.html#Lambda.Client.update_function_code
            res = client.update_function_code(
                FunctionName=self.name,
                ZipFile=zipped_code
            )

            # /v1/documentation/api/latest/reference/services/lambda.html#Lambda.Client.update_function_configuration
            res = client.update_function_configuration(
                FunctionName=self.name,
                Runtime=self.runtime,
                Role=role.arn,
                Handler=self.handler,
                timeout=self.timeout,
                description=self.description,
            )

        else:
            # create
            # https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/lambda.html#Lambda.Client.create_function
            res = client.create_function(
                FunctionName=self.name,
                Runtime=self.runtime,
                Role=role.arn,
                Handler=self.handler,
                Code={
                    "ZipFile": zipped_code
                },
                Timeout=self.timeout,
                description=self.description,
                #Environment=dict(Variables=env_variables),
            )

            self.raw = res

    def run(self, **kwargs):
        client = self.client
        return client.invoke(
            FunctionName=self.name,
            InvocationType='Event',
            Payload=json.dumps(kwargs),
        )

    def delete(self):
        """delete the lambda function

        https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/lambda.html#Lambda.Client.delete_function
        """
        self.client.delete_function(FunctionName=self.name)


