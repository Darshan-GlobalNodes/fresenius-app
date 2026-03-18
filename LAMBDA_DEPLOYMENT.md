# AWS Lambda Deployment Guide

This guide explains how to deploy the Fresenius AI Assistant as AWS Lambda functions.

## Architecture

The application is split into two Lambda functions:

1. **Main API Function** (`lambda_handler.py`) - Handles HTTP requests via API Gateway HTTP API
2. **WebSocket Function** (`websocket_handler.py`) - Handles WebSocket connections via API Gateway WebSocket API

## Prerequisites

1. **AWS Account** with appropriate permissions
2. **AWS CLI** configured with credentials
3. **Python 3.11+** installed locally
4. **Docker** installed and running (for building dependencies)
5. Choose one deployment method:
   - **AWS SAM CLI**: `pip install aws-sam-cli`
   - **Serverless Framework**: `npm install -g serverless serverless-python-requirements`

## Deployment Options

### Option 1: AWS SAM (Recommended)

AWS SAM provides native AWS integration and is easier for AWS-centric deployments.

#### Steps:

1. **Install AWS SAM CLI**
   ```bash
   pip install aws-sam-cli
   ```

2. **Configure parameters** in `samconfig.toml`:
   ```toml
   parameter_overrides = [
       "GoogleClientId=YOUR_GOOGLE_CLIENT_ID",
       "GoogleClientSecret=YOUR_GOOGLE_CLIENT_SECRET",
       "SecretKey=YOUR_SECRET_KEY",
       "WhitelistedEmails=email1@example.com,email2@example.com",
       "BedrockModelId=us.anthropic.claude-sonnet-4-20250514-v1:0"
   ]
   ```

3. **Deploy**
   ```bash
   chmod +x deploy.sh
   ./deploy.sh
   ```

   Or manually:
   ```bash
   sam build --use-container
   sam deploy --guided
   ```

4. **Note the outputs** - API Gateway URLs will be displayed

### Option 2: Serverless Framework

Serverless Framework provides better plugin ecosystem and multi-cloud support.

#### Steps:

1. **Install Serverless Framework**
   ```bash
   npm install -g serverless
   npm install --save-dev serverless-python-requirements
   ```

2. **Set environment variables** in `.env`:
   ```bash
   cp .env.lambda .env
   # Edit .env with your values
   ```

3. **Deploy**
   ```bash
   serverless deploy
   ```

4. **Note the endpoints** displayed in output

### Option 3: Manual Lambda Deployment

For direct Lambda deployment without infrastructure-as-code:

1. **Create deployment package**
   ```bash
   pip install -r requirements.txt -t package/
   cp -r app package/
   cp lambda_handler.py package/
   cp websocket_handler.py package/
   cp -r data package/
   cd package
   zip -r ../lambda-package.zip .
   cd ..
   ```

2. **Create Lambda functions** in AWS Console:
   - Runtime: Python 3.11
   - Memory: 2048 MB
   - Timeout: 900 seconds (15 minutes)
   - Upload `lambda-package.zip`

3. **Set environment variables** in Lambda console (see `.env.lambda`)

4. **Create API Gateway HTTP API** and connect to main Lambda

5. **Create API Gateway WebSocket API** and connect to WebSocket Lambda

6. **Add IAM permissions**:
   ```json
   {
     "Effect": "Allow",
     "Action": [
       "bedrock:InvokeModel",
       "bedrock:InvokeModelWithResponseStream",
       "execute-api:ManageConnections"
     ],
     "Resource": "*"
   }
   ```

## Post-Deployment Configuration

### 1. Update Google OAuth Redirect URI

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Navigate to APIs & Services > Credentials
3. Edit your OAuth 2.0 Client ID
4. Add authorized redirect URI:
   ```
   https://YOUR_API_GATEWAY_ID.execute-api.us-east-1.amazonaws.com/auth/callback
   ```

### 2. Test the API

```bash
# Get API URL from deployment output
API_URL="https://YOUR_API_GATEWAY_ID.execute-api.us-east-1.amazonaws.com"

# Test health endpoint
curl $API_URL/

# Test user endpoint (requires authentication)
curl -X GET $API_URL/api/user \
  -H "Cookie: access_token=YOUR_JWT_TOKEN"
```

### 3. Update Frontend Configuration

If you have a separate frontend, update the API endpoints:

```javascript
// Next.js .env.local or frontend config
NEXT_PUBLIC_API_URL=https://YOUR_API_GATEWAY_ID.execute-api.us-east-1.amazonaws.com
NEXT_PUBLIC_WS_URL=wss://YOUR_WEBSOCKET_API_ID.execute-api.us-east-1.amazonaws.com/prod
```

## Invoking Lambda from Other Services

### From Another Lambda Function

```python
import boto3
import json

lambda_client = boto3.client('lambda')

# Invoke the API Lambda directly
response = lambda_client.invoke(
    FunctionName='fresenius-ai-assistant',
    InvocationType='RequestResponse',  # or 'Event' for async
    Payload=json.dumps({
        'httpMethod': 'POST',
        'path': '/api/aws-credentials',
        'headers': {
            'Content-Type': 'application/json',
            'Cookie': 'access_token=YOUR_JWT_TOKEN'
        },
        'body': json.dumps({
            'access_key_id': 'ASIA...',
            'secret_access_key': 'secret...',
            'session_token': 'token...'
        })
    })
)

result = json.loads(response['Payload'].read())
print(result)
```

### From Step Functions

```json
{
  "Comment": "Invoke Fresenius AI Assistant",
  "StartAt": "InvokeFresenius",
  "States": {
    "InvokeFresenius": {
      "Type": "Task",
      "Resource": "arn:aws:states:::lambda:invoke",
      "Parameters": {
        "FunctionName": "fresenius-ai-assistant",
        "Payload": {
          "httpMethod": "GET",
          "path": "/api/config"
        }
      },
      "End": true
    }
  }
}
```

### From API Gateway (HTTP Request)

```bash
curl -X POST https://YOUR_API_GATEWAY_URL/api/aws-credentials \
  -H "Content-Type: application/json" \
  -H "Cookie: access_token=YOUR_JWT_TOKEN" \
  -d '{
    "access_key_id": "ASIA...",
    "secret_access_key": "secret...",
    "session_token": "token..."
  }'
```

### From EventBridge

Create an EventBridge rule that triggers the Lambda:

```json
{
  "source": ["custom.app"],
  "detail-type": ["Fresenius Request"],
  "detail": {
    "action": ["process"]
  }
}
```

Target: Lambda function `fresenius-ai-assistant`

### From S3 Events

Configure S3 bucket to trigger Lambda on file upload:

```python
# The Lambda will receive S3 event
def lambda_handler(event, context):
    for record in event['Records']:
        bucket = record['s3']['bucket']['name']
        key = record['s3']['object']['key']
        # Process file and invoke Fresenius API
        # ...
```

## Cost Optimization

1. **Lambda configuration**:
   - Use 2048 MB memory for AI workloads
   - Set appropriate timeout (900s max)
   - Enable Lambda SnapStart for faster cold starts (Java only, not Python)

2. **Bedrock optimization**:
   - Cache responses when possible
   - Use streaming for long responses
   - Monitor token usage

3. **Database optimization**:
   - For production, use Amazon RDS or DynamoDB instead of SQLite
   - SQLite file stored in `/tmp` is lost after Lambda execution

## Monitoring

### CloudWatch Logs

```bash
# View logs
aws logs tail /aws/lambda/fresenius-ai-assistant --follow

# WebSocket logs
aws logs tail /aws/lambda/fresenius-websocket-handler --follow
```

### CloudWatch Metrics

Monitor:
- Invocations
- Duration
- Errors
- Throttles
- Concurrent executions

### X-Ray Tracing

Enable X-Ray in SAM template or Serverless config for distributed tracing.

## Troubleshooting

### Cold Start Issues

**Problem**: First request is slow (5-10 seconds)

**Solutions**:
- Increase memory allocation (reduces cold start time)
- Use Lambda Provisioned Concurrency (costs more)
- Implement warming ping from CloudWatch Events
- Move database initialization outside handler

### Database Not Found

**Problem**: `fresenius.db not found` error

**Solutions**:
- Package the Excel file in the deployment
- Use S3 to store the database file
- Switch to RDS/DynamoDB for production

### WebSocket Connection Issues

**Problem**: WebSocket connections fail or disconnect

**Solutions**:
- Verify API Gateway WebSocket route configuration
- Check Lambda execution role has `execute-api:ManageConnections` permission
- Ensure connection_id is properly tracked
- Use DynamoDB for production to persist connection state

### Timeout Errors

**Problem**: Lambda times out after 900 seconds

**Solutions**:
- Break long-running tasks into smaller chunks
- Use Step Functions for orchestration
- Implement async processing with SQS

### Memory Issues

**Problem**: Lambda runs out of memory

**Solutions**:
- Increase memory allocation (up to 10 GB)
- Optimize pandas/numpy operations
- Use streaming for large responses

## Production Considerations

1. **Database**: Migrate from SQLite to Amazon RDS or DynamoDB
2. **Secrets**: Use AWS Secrets Manager instead of environment variables
3. **Monitoring**: Set up CloudWatch alarms for errors and latency
4. **Scaling**: Configure reserved concurrency to prevent runaway costs
5. **VPC**: Place Lambda in VPC if accessing private resources
6. **WAF**: Add AWS WAF to API Gateway for security
7. **Caching**: Use CloudFront CDN in front of API Gateway

## Cleanup

To remove all resources:

### SAM:
```bash
sam delete
```

### Serverless:
```bash
serverless remove
```

### Manual:
1. Delete Lambda functions
2. Delete API Gateway APIs
3. Delete CloudWatch Log Groups
4. Delete IAM roles

## Support

For issues or questions:
1. Check CloudWatch Logs
2. Review API Gateway execution logs
3. Test locally with SAM CLI: `sam local start-api`