"""
Example: How to invoke Fresenius AI Assistant Lambda from another AWS service

This demonstrates various ways to call the Lambda function programmatically.
"""

import boto3
import json


class FreseniusLambdaClient:
    """Client for invoking Fresenius AI Assistant Lambda function"""

    def __init__(self, function_name='fresenius-ai-assistant', region='us-east-1'):
        self.function_name = function_name
        self.lambda_client = boto3.client('lambda', region_name=region)

    def invoke_api_endpoint(self, method, path, headers=None, body=None):
        """
        Invoke Lambda as if it were an HTTP API endpoint

        Args:
            method: HTTP method (GET, POST, etc.)
            path: API path (e.g., '/api/config')
            headers: Optional request headers
            body: Optional request body (will be JSON encoded)

        Returns:
            Response from the Lambda function
        """
        payload = {
            'httpMethod': method,
            'path': path,
            'headers': headers or {'Content-Type': 'application/json'},
        }

        if body:
            payload['body'] = json.dumps(body)

        response = self.lambda_client.invoke(
            FunctionName=self.function_name,
            InvocationType='RequestResponse',  # Synchronous
            Payload=json.dumps(payload)
        )

        result = json.loads(response['Payload'].read())
        return result

    def invoke_async(self, method, path, headers=None, body=None):
        """Invoke Lambda asynchronously (fire and forget)"""
        payload = {
            'httpMethod': method,
            'path': path,
            'headers': headers or {'Content-Type': 'application/json'},
        }

        if body:
            payload['body'] = json.dumps(body)

        response = self.lambda_client.invoke(
            FunctionName=self.function_name,
            InvocationType='Event',  # Asynchronous
            Payload=json.dumps(payload)
        )

        return {'status': 'invoked', 'statusCode': response['StatusCode']}


# Example 1: Get API configuration
def example_get_config():
    """Get API configuration (requires authentication)"""
    client = FreseniusLambdaClient()

    response = client.invoke_api_endpoint(
        method='GET',
        path='/api/config',
        headers={
            'Content-Type': 'application/json',
            'Cookie': 'access_token=YOUR_JWT_TOKEN_HERE'
        }
    )

    print("Config Response:", response)


# Example 2: Update AWS credentials
def example_update_aws_credentials():
    """Update AWS credentials for Bedrock access"""
    client = FreseniusLambdaClient()

    response = client.invoke_api_endpoint(
        method='POST',
        path='/api/aws-credentials',
        headers={
            'Content-Type': 'application/json',
            'Cookie': 'access_token=YOUR_JWT_TOKEN_HERE'
        },
        body={
            'access_key_id': 'ASIA...',
            'secret_access_key': 'secret...',
            'session_token': 'token...'
        }
    )

    print("Credentials Update Response:", response)


# Example 3: Check AWS credentials status
def example_check_credentials_status():
    """Check if AWS credentials are set"""
    client = FreseniusLambdaClient()

    response = client.invoke_api_endpoint(
        method='GET',
        path='/api/aws-credentials/status',
        headers={
            'Content-Type': 'application/json',
            'Cookie': 'access_token=YOUR_JWT_TOKEN_HERE'
        }
    )

    print("Credentials Status:", response)


# Example 4: Invoke from Step Functions
def create_step_function_definition():
    """
    Example Step Functions definition that invokes Fresenius Lambda

    Deploy this with AWS Step Functions to orchestrate workflows
    """
    return {
        "Comment": "Orchestrate Fresenius AI Assistant workflow",
        "StartAt": "GetConfig",
        "States": {
            "GetConfig": {
                "Type": "Task",
                "Resource": "arn:aws:states:::lambda:invoke",
                "Parameters": {
                    "FunctionName": "fresenius-ai-assistant",
                    "Payload": {
                        "httpMethod": "GET",
                        "path": "/api/config",
                        "headers": {
                            "Content-Type": "application/json"
                        }
                    }
                },
                "Next": "ProcessConfig"
            },
            "ProcessConfig": {
                "Type": "Pass",
                "Result": "Config processed",
                "End": True
            }
        }
    }


# Example 5: Invoke from EventBridge
def create_eventbridge_rule():
    """
    Create EventBridge rule that triggers Lambda on schedule or events

    This is useful for periodic tasks like credential refresh reminders
    """
    events_client = boto3.client('events')

    # Create a rule that runs every 6 hours
    rule_response = events_client.put_rule(
        Name='fresenius-credential-reminder',
        ScheduleExpression='rate(6 hours)',
        State='ENABLED',
        Description='Remind users to refresh AWS credentials'
    )

    # Add Lambda as target
    events_client.put_targets(
        Rule='fresenius-credential-reminder',
        Targets=[
            {
                'Id': '1',
                'Arn': 'arn:aws:lambda:us-east-1:ACCOUNT_ID:function:fresenius-ai-assistant',
                'Input': json.dumps({
                    'httpMethod': 'POST',
                    'path': '/internal/credential-check',
                    'body': json.dumps({'action': 'check_expiry'})
                })
            }
        ]
    )

    print("EventBridge rule created:", rule_response)


# Example 6: Invoke from S3 event
def lambda_handler_for_s3_trigger(event, context):
    """
    Example Lambda that triggers Fresenius on S3 file upload

    Use case: Process patient data files uploaded to S3
    """
    client = FreseniusLambdaClient()

    for record in event['Records']:
        bucket = record['s3']['bucket']['name']
        key = record['s3']['object']['key']

        print(f"Processing file: s3://{bucket}/{key}")

        # You could download and process the file, then invoke Fresenius API
        response = client.invoke_api_endpoint(
            method='POST',
            path='/internal/process-upload',
            body={
                'bucket': bucket,
                'key': key,
                'action': 'import_patient_data'
            }
        )

        print("Processing response:", response)


# Example 7: Invoke from API Gateway (another Lambda)
def lambda_handler_api_proxy(event, context):
    """
    Example Lambda that acts as a proxy to Fresenius Lambda

    Use case: Add custom authentication or rate limiting
    """
    client = FreseniusLambdaClient()

    # Extract request details from API Gateway event
    method = event['httpMethod']
    path = event['path']
    headers = event.get('headers', {})
    body = event.get('body')

    # Add custom logic here (authentication, rate limiting, etc.)
    if not validate_custom_auth(headers):
        return {
            'statusCode': 401,
            'body': json.dumps({'error': 'Unauthorized'})
        }

    # Forward to Fresenius Lambda
    response = client.invoke_api_endpoint(
        method=method,
        path=path,
        headers=headers,
        body=json.loads(body) if body else None
    )

    return response


def validate_custom_auth(headers):
    """Custom authentication logic"""
    # Implement your custom auth here
    return True


# Example 8: Batch invocation for multiple requests
def batch_invoke_example():
    """Process multiple requests in parallel"""
    import concurrent.futures

    client = FreseniusLambdaClient()

    # List of requests to process
    requests = [
        {'method': 'GET', 'path': '/api/config'},
        {'method': 'GET', 'path': '/api/user'},
        {'method': 'GET', 'path': '/api/aws-credentials/status'},
    ]

    def invoke_request(req):
        return client.invoke_api_endpoint(
            method=req['method'],
            path=req['path'],
            headers={'Cookie': 'access_token=YOUR_JWT_TOKEN'}
        )

    # Execute requests in parallel
    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
        results = list(executor.map(invoke_request, requests))

    for i, result in enumerate(results):
        print(f"Request {i+1} result:", result)


# Example 9: Integration with SQS
def process_sqs_messages_and_invoke_lambda():
    """
    Poll SQS queue and invoke Lambda for each message

    Use case: Queue-based processing of chat requests
    """
    sqs_client = boto3.client('sqs')
    lambda_client = FreseniusLambdaClient()

    queue_url = 'https://sqs.us-east-1.amazonaws.com/ACCOUNT_ID/fresenius-queue'

    while True:
        response = sqs_client.receive_message(
            QueueUrl=queue_url,
            MaxNumberOfMessages=10,
            WaitTimeSeconds=20
        )

        messages = response.get('Messages', [])
        if not messages:
            break

        for message in messages:
            body = json.loads(message['Body'])

            # Invoke Lambda with message data
            result = lambda_client.invoke_api_endpoint(
                method=body['method'],
                path=body['path'],
                headers=body.get('headers', {}),
                body=body.get('body')
            )

            print(f"Processed message: {message['MessageId']}, Result: {result}")

            # Delete message from queue
            sqs_client.delete_message(
                QueueUrl=queue_url,
                ReceiptHandle=message['ReceiptHandle']
            )


if __name__ == '__main__':
    print("Fresenius Lambda Client Examples")
    print("=" * 50)

    # Run examples (comment out as needed)
    # example_get_config()
    # example_update_aws_credentials()
    # example_check_credentials_status()

    # Print Step Functions definition
    print("\nStep Functions Definition:")
    print(json.dumps(create_step_function_definition(), indent=2))