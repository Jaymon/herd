# Herd

Quickly and easily create [AWS lambda](https://aws.amazon.com/lambda/) python functions and make them available from a url.

## 1 Minute getting started

### Install herd

    $ pip install herd
    

### Create a lambda file

Create a python file:

    $ touch foo.py
    
and then edit `foo.py` to add a lambda function:

```python
# foo.py

import json

def handler(event, context):
    """This is the description of the lambda function that will show up in AWS console"""
    return {
        'statusCode': 200,
        'body': json.dumps({'query_string': event["queryStringParameters"]}),
    }
```

### Set your amazon environment

You should set a few environment variables:

```
export AWS_ACCESS_KEY_ID=...
export AWS_SECRET_ACCESS_KEY=...
export AWS_DEFAULT_REGION="us-west-1"
```

### Upload your function using herd

    $ herd function-add foo.py
    Function foo available at url: https://XXXXXXXXXXX.execute-api.us-west-1.amazonaws.com/herd-lambda-api/foo
    

### Verify your function is available

    $ curl "https://XXXXXXXXXXX.execute-api.us-west-1.amazonaws.com/herd-lambda-api/foo?foo=1&bar=2"
    {"query_string": {"foo": "1", "bar": "2"}}
    
That's it!

----------------------------------------------

Herd is still in an alpha state and as we start using it for some of our infrastructure I'm sure it will change here and there. We also have more functionality planned for it in the future.