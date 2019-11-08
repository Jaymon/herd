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



