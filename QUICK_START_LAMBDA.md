# Quick Start: Deploy to AWS Lambda

## Prerequisites
```bash
# Install AWS SAM CLI
pip install aws-sam-cli

# Verify Docker is running
docker --version
```

## Deploy in 3 Steps

### 1. Configure Environment
Edit `samconfig.toml` with your values:
```toml
parameter_overrides = [
    "GoogleClientId=YOUR_GOOGLE_CLIENT_ID",
    "GoogleClientSecret=YOUR_GOOGLE_CLIENT_SECRET",
    "SecretKey=YOUR_SECRET_KEY_HERE",
    "WhitelistedEmails=your-email@example.com",
    "BedrockModelId=us.anthropic.claude-sonnet-4-20250514-v1:0"
]
```

### 2. Deploy
```bash
chmod +x deploy.sh
./deploy.sh
```

### 3. Update Google OAuth
After deployment, update your Google Cloud Console OAuth redirect URI with:
```
https://YOUR_API_ID.execute-api.us-east-1.amazonaws.com/auth/callback
```

## Invoke from Another Lambda

```python
import boto3
import json

lambda_client = boto3.client('lambda')

response = lambda_client.invoke(
    FunctionName='fresenius-ai-assistant',
    InvocationType='RequestResponse',
    Payload=json.dumps({
        'httpMethod': 'GET',
        'path': '/api/config',
        'headers': {'Content-Type': 'application/json'}
    })
)

result = json.loads(response['Payload'].read())
print(result)
```

## Test Your Deployment

```bash
# Get your API URL from SAM output
API_URL="https://YOUR_API_ID.execute-api.us-east-1.amazonaws.com"

# Test the API
curl $API_URL/
```

## View Logs

```bash
sam logs -n FreseiniusFunction --tail
```

## Update Deployment

```bash
sam build --use-container
sam deploy
```

## Delete Stack

```bash
sam delete
```

---

For detailed documentation, see [LAMBDA_DEPLOYMENT.md](./LAMBDA_DEPLOYMENT.md)