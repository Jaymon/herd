# -*- coding: utf-8 -*-
from __future__ import unicode_literals, division, print_function, absolute_import
import json
import runpy
import logging
import sys
import inspect
import os
import re
import tempfile
from zipfile import ZipFile

import boto3
from botocore.exceptions import ClientError


logger = logging.getLogger(__name__)



class AWS(object):

    @property
    def client_name(self):
        return self.__class__.__name__.lower()

    @property
    def client(self):
        return boto3.client(self.client_name)

    @property
    def region_name(self):
        # https://stackoverflow.com/a/55749807/5006
        return self.client.meta.region_name

    def exists(self):
        return self.load()

    def load(self):
        if getattr(self, "raw", None) is None:
            try:
                self.raw = self._load()

            except (ClientError, ValueError) as e:
                self.raw = {}

        return True if self.raw else False

    def delete(self):
        raise NotImplementedError()


class ApiGateway(AWS):

    @property
    def id(self):
        return self.raw["id"]

    @property
    def url(self):
        return 'https://{}.execute-api.{}.amazonaws.com/{}/'.format(
            self.id,
            self.region_name,
            self.stage,
        )

    @property
    def uri(self):
        return "arn:aws:apigateway:{}:lambda:path/2015-03-31/functions/{}/invocations".format(
            self.region_name,
            self.func.arn
        )

    @property
    def client(self):
        region_name = self.func.region_name or None
        return boto3.client(self.client_name, region_name=region_name)

    def __init__(self, func, stage="DEV"):
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
        res = client.get_rest_apis(limit=500)
        for raw in res["items"]:
            if raw["name"] == self.name:
                break

        if not raw:
            raise ValueError("Could not find API Gateway with name {}".format(self.name))

        #raw = client.get_rest_api(restApiId=self.name)
        #pout.v(raw)
        return raw

    def save(self):

        client = self.client

        if not self.exists():
            self.raw = client.create_rest_api(
                name=self.name,
                description=self.description,
                endpointConfiguration={"types": ["EDGE"]},
                apiKeySource="HEADER",
            )

        api = self.raw

        pout.v(api)

        # find the existing endpoint
        res2 = client.get_resources(restApiId=api["id"])
        pout.v(res2)

        resource = [d for d in res2["items"] if d["path"] == "/"][0]

        # resource will support any http method (eg, GET, POST)
        try:
            res4 = client.put_method(
                restApiId=api['id'],
                resourceId=resource['id'],
                httpMethod='ANY',
                authorizationType='NONE'
            )

            pout.v(res4)

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
        res5 = client.put_integration(
            restApiId=api['id'],
            resourceId=resource['id'],
            httpMethod='ANY',
            type='AWS_PROXY',
            integrationHttpMethod='POST',
            uri=self.uri,
            #passthroughBehavior="WHEN_NO_MATCH",
        )

        client.put_integration_response(
            restApiId=api["id"],
            resourceId=resource["id"],
            httpMethod='ANY',
            statusCode='200',
            responseTemplates={'application/json': ''}
        )



        pout.v(res5)

        res6 = client.create_deployment(
            restApiId=api["id"],
            stageName=self.stage.lower() or None
        )
        pout.v(res6)

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

            pout.v(res7)

        except func_client.exceptions.ResourceConflictException as e:
            pass



        return












        resource = {}
        for r in res2["items"]:
            if r["path"].endswith(self.name):
                resource = r
                break

        if resource:
            pass

        else:
            # find the parent resource
            parent_resource = [d for d in res2["items"] if d["path"] == "/"][0]

            # create the resource
            res3 = client.create_resource(
                restApiId=api['id'],
                parentId=parent_resource["id"],
                pathPart=self.func.name
            )

            # resource will support any http method (eg, GET, POST)
            res4 = client.put_method(
                restApiId=api['id'],
                resourceId=res3['id'],
                httpMethod='ANY',
                authorizationType='NONE'
            )

            pout.v(res4)


            # Add an integration method to the api resource
            res5 = client.put_integration(
                restApiId=api['id'],
                resourceId=res3['id'],
                httpMethod='POST',
                type='AWS_PROXY',
                integrationHttpMethod='POST',
                uri=self.uri,
                passthroughBehavior="WHEN_NO_MATCH",
            )

            pout.v(res5)
            pout.b()


        res2 = client.get_resources(restApiId=api["id"])
        pout.v(res2)

        resource = [d for d in res2["items"] if d["path"] == "/{}".format(self.name)][0]
        res3 = client.get_method(restApiId=api["id"], resourceId=resource["id"], httpMethod="ANY")
        pout.v(res3)

    def delete(self):
        if self.exists():
            ret = True
            api_id = self.raw["id"]
            client = self.client
            try:
                client.delete_rest_api(restApiId=api_id)

            except ClientError as e:
                logging.error(e)
                ret = False

            return ret







# client = boto3.client('apigateway', region_name="eu-west-1")
# #client = boto3.client('apigateway')
# 
# res = client.get_rest_apis()
# res2 = client.get_resources(restApiId=res["items"][0]["id"])
# pout.v(res2)
# 
# 
# res3 = client.get_method(restApiId=res["items"][0]["id"], resourceId=res2["items"][1]["id"], httpMethod="ANY")
# pout.v(res3)
# 
# 
# 
# 
# 
# 
# pout.x()





class Role(AWS):
    client_name = "iam"

    @property
    def account_id(self):
        return self.arn.split(":")[4]

    @property
    def arn(self):
        return self.raw["Role"]["Arn"]

    def __init__(self, name):
        self.name = name
        self.policy_documents = {}
        if not self.exists():
            self.save()

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
        self.raw = iam_client.create_role(
            RoleName=self.name,
            **{i[0]: json.dumps(i[1]) for i in self.policy_documents.items()}
        )

    def delete(self):
        """Delete the IAM role

        https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/iam.html#IAM.Client.delete_role
        """
        client = self.client
        client.delete_role(RoleName=self.name)


class Lambda(AWS):

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
#         if self.region_name:
#             return boto3.client('lambda', region_name=self.region_name)
#         else:
#             return boto3.client('lambda')

    def __init__(self, filepath, role, dependencies=None, name="", region_name=""):
        # TODO -- we could also do this with regex looking for def NAME(event, context):
        self.loaded = None
        self.filepath = filepath
        self.dependencies = dependencies
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

        self.module_name = os.path.splitext(os.path.basename(filepath))[0]

        # name can use only letters, numbers, hyphens, or underscores with no spaces
        if name:
            self.name = name

        else:
            self.name = self.module_name

        self.load()

    def _load(self):
        client = self.client
        return client.get_function(FunctionName=self.name)

        #self.loaded = self.raw["ResponseMetadata"]["HTTPStatusCode"] == 200

        #except client.exceptions.ResourceNotFoundException as e:
        #    self.loaded = False

        #return self.loaded

#     def create(self):
#         self.basedir = tempfile.mkdtemp(dir=tempfile.gettempdir())
#         self.zipfilepath = os.path.join(self.basedir, "lambda.zip")
# 
#         with ZipFile(self.zipfilepath, 'w') as z:
#             # TODO test with full filepath for filepath to make sure it still
#             # puts the file at the top level of the zipfile
#             z.write(filepath)
#
#        pout.v(self.zipfilepath, self.basedir)

    def save(self):
        client = self.client
        self.basedir = tempfile.mkdtemp(dir=tempfile.gettempdir())
        self.zipfilepath = os.path.join(self.basedir, "lambda.zip")
        role = self.role

        with ZipFile(self.zipfilepath, 'w') as z:
            # TODO test with full filepath for filepath to make sure it still
            # puts the file at the top level of the zipfile
            z.write(self.filepath)

        with open(self.zipfilepath, 'rb') as f:
            zipped_code = f.read()

        if self.exists():
            # update
            # https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/lambda.html#Lambda.Client.update_function_code
            res = client.update_function_code(
                FunctionName=self.name,
                ZipFile=zipped_code
            )

            #failed = False

            #if res["ResponseMetadata"]["HTTPStatusCode"] == 200:
            # /v1/documentation/api/latest/reference/services/lambda.html#Lambda.Client.update_function_configuration
            res = client.update_function_configuration(
                FunctionName=self.name,
                Runtime=self.runtime,
                Role=role.arn,
                Handler=self.handler,
                timeout=self.timeout,
                description=self.description,
            )
#             failed = res["ResponseMetadata"]["HTTPStatusCode"] != 200
# 
#             if failed:
#                 raise IOError("Failed to update Lambda function, response: {}".format(res))

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
            if res["ResponseMetadata"]["HTTPStatusCode"] != 200:
                raise IOError("Failed to create Lambda function, response: {}".format(res))

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
        pass


role = Role('LambdaApi')

# role.load()
# pout.v(role, role.client, role.client.get_account_summary())
# pout.x()



s = Lambda("aws_lambda.py", role=role, name="aws_lambda-lambda_handler")
#s.save()

#s.load()
#pout.v(s)
#pout.x()
#pout.v(s.client.meta.region_name)
#pout.v(s.client.meta)
#pout.x()

api = ApiGateway(s, "dev")
#api.delete() # there is a delay between delete being called and the api actually being deleted and not showing up in searches

#pout.v(api.exists())

#pout.v(api.uri)
#pout.x()



#pout.v(role.client_name, s.client_name, api.client_name)
#pout.x()
api.save()
pout.v(api.url)

pout.x()


role = Role('LambdaApi')
pout.v(role)





pout.x()





# create the needed IAM role for both lambda and api
iam_client = boto3.client('iam')

#pout.v(iam_client)

role = Role('handle-role-8wnl0v8t')
#role = Role('foo')
pout.v(role.exists(), role)

pout.x()




role = iam_client.get_role(RoleName='handle-role-8wnl0v8t')
pout.v(role)
pout.x()



for role in iam_client.list_roles()["Roles"]:
    pout.v(role["RoleName"])

pout.x()

pout.v(iam_client.list_roles())
#pout.v(iam_client.list_role_policies())



