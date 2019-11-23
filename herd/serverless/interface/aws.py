# -*- coding: utf-8 -*-
from __future__ import unicode_literals, division, print_function, absolute_import
import json
import runpy
import logging
import sys
import inspect
import os
import re

import boto3
from botocore.exceptions import ClientError

from ...compat import *
from ...path import Tempdir, Filepath, Path
from ...reflection import Dependencies
from ...utils import Environ


logger = logging.getLogger(__name__)


class Description(String):
    def __new__(cls, val="", encoding="UTF-8"):
        val = String(val)
        # 'description' failed to satisfy constraint: Member must have length less than or equal to 256
        if len(val) > 256:
            val = val[:252] + "..."

        return super(Description, cls).__new__(cls, val, encoding=encoding)


class AWS(object):
    """Base class that standardizes the interface for all the services"""

    @property
    def session(self):
        return boto3.Session()

    @property
    def client_name(self):
        """returns the client_name, by default this will use the class name but this
        can be easily overidden in the child classes"""
        return self.__class__.__name__.lower()

    @property
    def client(self):
        """return a boto3 client for the service, uses self.client_name"""
        region_name = getattr(self, "_region_name", None) or None
        return boto3.client(self.client_name, region_name=region_name)

    @property
    def region_name(self):
        """Return the region name of the service"""
        # https://stackoverflow.com/a/55749807/5006
        return self.session.region_name
        #return self.client.meta.region_name

    @property
    def region_names(self):
        return self.session.get_available_regions(self.client_name)

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


class Region(String):
    def __new__(cls, region_name):
        if not region_name:
            session = boto3.Session()
            region_name = session.region_name
            if not region_name:
                raise ValueError("No region name found")

        return super(Region, cls).__new__(cls, region_name)

    @classmethod
    def names(cls):
        session = boto3.Session()
        return session.get_available_regions("ec2")


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
        # https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/iam.html#IAM.Client.get_role
        return self.client.get_role(RoleName=self.name)

    def save(self):
        if not self.exists():
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

#     @property
#     def client(self):
#         region_name = self.func.region_name or None
#         return boto3.client(self.client_name, region_name=region_name)

    def __init__(self, name, description="", region_name=""):
        """Create an instance of the api for func in the stage environment
        """
        self.name = name
        self.description = description or "API Gateway for herd lambda functions"
        self._region_name = region_name

    def _load(self):
        client = self.client
        # this isn't ideal but names aren't unique for the apis and so we have
        # to get all the apis and then work through them to find the right api,
        # and lambda resources don't have a unique id either so we can't use
        # that, so we are assuming name will be unique and the lambda and api
        # resources will share the same name
        raw = None

        try:

            # https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/apigateway.html#APIGateway.Client.get_rest_api
            raw = client.get_rest_api(restApiId=self.name)

        except ClientError:
            # TODO -- this tops out at 500, we should keep paginating 500 at a time
            # but that seems like overkill right now
            # https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/apigateway.html#APIGateway.Client.get_rest_apis
            res = client.get_rest_apis(limit=500)
            for raw in res["items"]:
                if raw["name"] == self.name:
                    self.name = raw["name"]
                    self.description = raw["description"]
                    break

        if not raw:
            raise ValueError("Could not find API Gateway with name {}".format(self.name))

        return raw

    def save(self):
        """Actually create/update the api endpoint and hook it into lambda"""
        client = self.client

        # https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/apigateway.html#APIGateway.Client.create_rest_api
        if not self.exists():
            self.raw = client.create_rest_api(
                name=self.name,
                description=self.description,
                endpointConfiguration={"types": ["EDGE"]},
                apiKeySource="HEADER",
            )

        return

    def add_lambda(self, func, stage="DEV"):
        """

        :param stage: string, the environment name (eg, DEV, PROD, STAGE, TEST)
        """
        client = self.client
        region_name = self.region_name
        stage = stage.lower() or None

        self.save()
        api = self.raw

        # find the existing endpoint
        res2 = client.get_resources(restApiId=api["id"])

        resource = {}
        for r in res2["items"]:
            if r.get("pathPart", "") == func.name:
                resource = r
                break

        if not resource:
            parent_resource = [d for d in res2["items"] if d["path"] == "/"][0]

            resource = client.create_resource(
                restApiId=api['id'],
                parentId=parent_resource['id'],
                pathPart=func.name
            )

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

        """The api gateway uri that is used to connect lambda to the api"""
        lambda_uri = "arn:aws:apigateway:{}:lambda:path/2015-03-31/functions/{}/invocations".format(
            region_name,
            func.arn
        )

        # !!! Not sure why this doesn't need to be conflict gated
        client.put_integration(
            restApiId=api['id'],
            resourceId=resource['id'],
            httpMethod='ANY',
            type='AWS_PROXY',
            integrationHttpMethod='POST',
            uri=lambda_uri,
        )
        client.put_integration_response(
            restApiId=api["id"],
            resourceId=resource["id"],
            httpMethod='ANY',
            statusCode='200',
            responseTemplates={'application/json': ''}
        )

        # https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/apigateway.html#APIGateway.Client.create_deployment
        res6 = client.create_deployment(
            restApiId=api["id"],
            stageName=stage
        )

        # add the lambda permission so this api can invoke it
        func_client = func.client
        try:
            perm_arn = 'arn:aws:execute-api:{}:{}:{}/*/*/{}'.format(
                region_name,
                func.role.account_id,
                api["id"],
                resource["pathPart"],
            )
            res7 = func_client.add_permission(
                FunctionName=func.name,
                StatementId='{}-invoke'.format(func.name),
                Action='lambda:InvokeFunction',
                Principal='apigateway.amazonaws.com',
                SourceArn=perm_arn
            )

        except func_client.exceptions.ResourceConflictException as e:
            pass

        return 'https://{}.execute-api.{}.amazonaws.com/{}/{}'.format(
            api["id"],
            region_name,
            stage or "default",
            resource["pathPart"],
        )


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


class Lambda(AWS):
    """Represents a lambda function

    https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/lambda.html
    """

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

    def __init__(self, filepath, role, environ=None, name="", region_name=""):
        """create a representation of the lambda function that will run filepath

        :param filepath: string, the file path to a python file that will uploaded
            to lambda, this file should have a function that matches the definition:
                NAME(event, context)
            which is what lambda will invoke when ran
        :param role: Role, the role to use for this lambda function
        :param environ: dict, the environment variables this lambda will use
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
        self.environ = Environ(environ or {})

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
        # https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/lambda.html#Lambda.Client.get_function
        return client.get_function(FunctionName=self.name)

    def bundle(self):
        basedir = Tempdir("lambda")
        #zip_filepath = os.path.join(basedir, "lambda.zip")
        bundle_dir = Tempdir("bundle", dir=basedir)

        self.filepath.copy_to(Path(bundle_dir, self.filepath.basename))

        d = Dependencies(self.filepath)
        for p in d:
            p.path.copy_to(Path(bundle_dir, p.path.basename))

        logger.debug("Bundled lambda function to {}".format(bundle_dir))
        return bundle_dir.zip_to(Filepath(basedir, "lambda.zip"))

    def save(self):
        role = self.role
        client = self.client

        zipfilepath = self.bundle()
        with open(zipfilepath, 'rb') as f:
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
                Timeout=self.timeout,
                Description=Description(self.description),
                Environment={"Variables": self.environ},
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
                Description=Description(self.description),
                Environment={"Variables": self.environ},
            )

            self.raw = res

    def run(self, **kwargs):
        ret = {}

        client = self.client
        res = client.invoke(
            FunctionName=self.name,
            InvocationType='RequestResponse',
            Payload=json.dumps(kwargs),
        )

        # https://stackoverflow.com/a/39456752/5006
        if res["ResponseMetadata"]["HTTPStatusCode"] == 200:
            ret = json.load(res["Payload"])

        return ret


    def delete(self):
        """delete the lambda function

        https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/lambda.html#Lambda.Client.delete_function
        """
        self.client.delete_function(FunctionName=self.name)


