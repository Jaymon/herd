# Amazon Web Services (AWS) Troubleshooting

## IAM Roles

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
    
    ```python
    import boto3

    iam = boto3.client("iam")

    for role in 
    pout.v(iam.list_roles())
