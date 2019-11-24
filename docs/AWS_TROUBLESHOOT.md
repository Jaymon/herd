# Amazon Web Services (AWS) Troubleshooting

## Permissions and Policies

### IAM Roles

Herd will attempt to create a role if one doesn't exist, that might fail with an error like this:

> botocore.exceptions.ClientError: An error occurred (AccessDenied) when calling the CreateRole operation: User: arn:aws:iam::NNNN:user/XXXXXXX is not authorized to perform: iam:CreateRole on resource: arn:aws:iam::NNNN:role/ROLE-NAME


You can get around this error in two ways:

1. You create the role in the [IAM console](https://console.aws.amazon.com/iam/home) and give it the correct policy, something like:

    ```
    {
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
    ```

    Then make sure your IAM user has the permission: `IAMReadOnlyAccess`.
    
2. Give your user whose `AWS_ACCESS_KEY_ID` and `AWS_SECRET_ACCESS_KEY` you're using write permission to IAM, something like: `IAMFullAccess`.

    You can verify your [boto3](https://github.com/boto/boto3) user can see your role by doing something like:
    
    ```
    $ herd info-roles
    ```


### Lambda permissions

If you get an error when herd attempts to create the lambda function:

> botocore.exceptions.ClientError: An error occurred (AccessDeniedException) when calling the CreateFunction operation: User: arn:aws:iam::NNNN:user/XXXXXXX is not authorized to perform: lambda:CreateFunction on resource: arn:aws:lambda:REGION:NNNN:function:FUNCTION-NAME

You can solve this by giving your IAM user the policy: `AWSLambdaFullAccess`.


### API Gateway Permissions

If you get this error when attempting to give your lambda function API Gateway access:

> botocore.exceptions.ClientError: An error occurred (AccessDeniedException) when calling the CreateRestApi operation: User: arn:aws:iam::NNNN:user/XXXXXXX is not authorized to perform: apigateway:POST on resource: arn:aws:apigateway:REGION::/restapis

You can solve this by giving your IAM user the policy: `AmazonAPIGatewayAdministrator`.